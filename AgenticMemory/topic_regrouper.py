import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from nltk.tokenize import sent_tokenize
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from memory_layer import DEFAULT_EMBEDDING_MODEL, build_embedding_model
from short_term_memory import RecentMemoryItem


def _preview_text(text: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


class GroupTraceLogger:
    def __init__(self, trace_path: Optional[str] = None):
        self.trace_path = Path(trace_path) if trace_path else None
        if self.trace_path:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, payload: Dict[str, Any]):
        if not self.trace_path:
            return
        event = {
            "ts": datetime.now().isoformat(),
            "event": event_type,
            **payload,
        }
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


@dataclass
class SentenceUnit:
    chunk_id: str
    sentence_idx: int
    global_idx: int
    text: str


@dataclass
class TopicGroup:
    topic_id: str
    source_chunk_ids: List[str]
    sentence_indices: List[int]
    text: str


@dataclass
class ClusteringResult:
    clusters: List[List[SentenceUnit]]
    timings: Dict[str, float]


class TopicRegrouper:
    def __init__(
        self,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        similarity_threshold: float = 0.42,
        min_cluster_size: int = 2,
        reciprocal_top_k: int = 5,
        max_cluster_sentences: int = 40,
        trace_path: Optional[str] = None,
    ):
        self.embedding_model = embedding_model
        self.model = build_embedding_model(embedding_model)
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.reciprocal_top_k = reciprocal_top_k
        self.max_cluster_sentences = max_cluster_sentences
        self.trace_logger = GroupTraceLogger(trace_path)

    def _normalize_sentences(self, text: str) -> List[str]:
        raw_sentences = [s.strip() for s in sent_tokenize(text) if s.strip()]
        if not raw_sentences:
            return [text.strip()]

        merged: List[str] = []
        pending_prefix = ""
        for sentence in raw_sentences:
            alpha_count = sum(ch.isalpha() for ch in sentence)
            is_fragment = alpha_count < 5
            if is_fragment:
                pending_prefix = f"{pending_prefix} {sentence}".strip()
                continue
            if pending_prefix:
                sentence = f"{pending_prefix} {sentence}".strip()
                pending_prefix = ""
            merged.append(sentence)

        if pending_prefix:
            if merged:
                merged[-1] = f"{merged[-1]} {pending_prefix}".strip()
            else:
                merged.append(pending_prefix)
        return merged or [text.strip()]

    def _to_sentence_units(self, items: Sequence[RecentMemoryItem]) -> List[SentenceUnit]:
        units: List[SentenceUnit] = []
        global_idx = 0
        for item in items:
            sentences = self._normalize_sentences(item.raw_text)
            for sentence_idx, sentence in enumerate(sentences):
                units.append(
                    SentenceUnit(
                        chunk_id=item.chunk_id,
                        sentence_idx=sentence_idx,
                        global_idx=global_idx,
                        text=sentence,
                    )
                )
                global_idx += 1
        return units

    def _split_oversized_cluster(
        self,
        cluster: List[SentenceUnit],
        embeddings: np.ndarray,
    ) -> tuple[List[List[SentenceUnit]], float]:
        if len(cluster) <= self.max_cluster_sentences:
            return [sorted(cluster, key=lambda unit: unit.global_idx)], 0.0

        n_clusters = int(np.ceil(len(cluster) / self.max_cluster_sentences))
        if n_clusters <= 1:
            return [sorted(cluster, key=lambda unit: unit.global_idx)], 0.0

        start_time = time.perf_counter()
        kmeans = KMeans(n_clusters=n_clusters, random_state=0, n_init=10)
        labels = kmeans.fit_predict(embeddings)
        elapsed = time.perf_counter() - start_time
        split_clusters: List[List[SentenceUnit]] = []
        for label in sorted(set(labels)):
            subgroup = [cluster[idx] for idx, assigned in enumerate(labels) if assigned == label]
            subgroup = sorted(subgroup, key=lambda unit: unit.global_idx)
            split_clusters.append(subgroup)
        return split_clusters, elapsed

    def _cluster_units(self, units: List[SentenceUnit]) -> ClusteringResult:
        timings = {
            "embedding_seconds": 0.0,
            "similarity_seconds": 0.0,
            "graph_build_seconds": 0.0,
            "connected_components_seconds": 0.0,
            "kmeans_split_seconds": 0.0,
        }
        if len(units) <= 1:
            start_time = time.perf_counter()
            embeddings = np.array(self.model.encode([unit.text for unit in units]), dtype=np.float32)
            timings["embedding_seconds"] = time.perf_counter() - start_time
            return ClusteringResult([units], timings)

        start_time = time.perf_counter()
        embeddings = np.array(self.model.encode([unit.text for unit in units]), dtype=np.float32)
        timings["embedding_seconds"] = time.perf_counter() - start_time

        start_time = time.perf_counter()
        sim = cosine_similarity(embeddings)
        timings["similarity_seconds"] = time.perf_counter() - start_time

        start_time = time.perf_counter()
        adjacency = {idx: set() for idx in range(len(units))}
        neighbor_sets: List[set[int]] = []
        for i in range(len(units)):
            ranked = np.argsort(sim[i])[::-1]
            filtered = [idx for idx in ranked if idx != i and sim[i, idx] >= self.similarity_threshold]
            neighbor_sets.append(set(filtered[: self.reciprocal_top_k]))
        for i in range(len(units)):
            adjacency[i].add(i)
            for j in range(i + 1, len(units)):
                if sim[i, j] >= self.similarity_threshold and i in neighbor_sets[j] and j in neighbor_sets[i]:
                    adjacency[i].add(j)
                    adjacency[j].add(i)
        timings["graph_build_seconds"] = time.perf_counter() - start_time

        start_time = time.perf_counter()
        visited = set()
        clusters: List[List[SentenceUnit]] = []
        for idx in range(len(units)):
            if idx in visited:
                continue
            stack = [idx]
            component = []
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                stack.extend(adjacency[node] - visited)
            cluster_units = [units[i] for i in sorted(component, key=lambda x: units[x].global_idx)]
            clusters.append(cluster_units)
        timings["connected_components_seconds"] = time.perf_counter() - start_time

        large_clusters = [cluster for cluster in clusters if len(cluster) >= self.min_cluster_size]
        small_clusters = [cluster for cluster in clusters if len(cluster) < self.min_cluster_size]

        if not large_clusters:
            return ClusteringResult([sorted(units, key=lambda unit: unit.global_idx)], timings)

        for cluster in small_clusters:
            large_clusters[0].extend(cluster)
            large_clusters[0].sort(key=lambda unit: unit.global_idx)
        split_clusters: List[List[SentenceUnit]] = []
        for cluster in large_clusters:
            cluster_indices = [unit.global_idx for unit in cluster]
            cluster_embeddings = embeddings[cluster_indices]
            split_result, split_elapsed = self._split_oversized_cluster(cluster, cluster_embeddings)
            timings["kmeans_split_seconds"] += split_elapsed
            split_clusters.extend(split_result)
        return ClusteringResult(split_clusters, timings)

    def regroup(self, window_id: str, items: Sequence[RecentMemoryItem]) -> List[TopicGroup]:
        total_start_time = time.perf_counter()
        sentence_start_time = time.perf_counter()
        units = self._to_sentence_units(items)
        sentence_seconds = time.perf_counter() - sentence_start_time
        if not units:
            return []

        clustering_result = self._cluster_units(units)
        clusters = clustering_result.clusters
        groups: List[TopicGroup] = []
        cluster_payload = []
        for idx, cluster in enumerate(clusters):
            cluster = sorted(cluster, key=lambda unit: unit.global_idx)
            source_chunk_ids = []
            seen_chunk_ids = set()
            for unit in cluster:
                if unit.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(unit.chunk_id)
                    source_chunk_ids.append(unit.chunk_id)
            text = " ".join(unit.text for unit in cluster)
            groups.append(
                TopicGroup(
                    topic_id=f"{window_id}_topic_{idx:02d}",
                    source_chunk_ids=source_chunk_ids,
                    sentence_indices=[unit.global_idx for unit in cluster],
                    text=text,
                )
            )
            cluster_payload.append(
                {
                    "topic_id": f"{window_id}_topic_{idx:02d}",
                    "source_chunk_ids": source_chunk_ids,
                    "sentence_indices": [unit.global_idx for unit in cluster],
                    "sentence_count": len(cluster),
                    "content_preview": _preview_text(text),
                }
            )

        timing_seconds = {
            "sentence_split_seconds": sentence_seconds,
            **clustering_result.timings,
        }
        timing_seconds["total_seconds"] = time.perf_counter() - total_start_time
        self.trace_logger.log(
            "topic_regrouping_complete",
            {
                "window_id": window_id,
                "input_chunk_ids": [item.chunk_id for item in items],
                "input_chunk_count": len(items),
                "sentence_count": len(units),
                "cluster_count": len(groups),
                "similarity_threshold": self.similarity_threshold,
                "reciprocal_top_k": self.reciprocal_top_k,
                "max_cluster_sentences": self.max_cluster_sentences,
                "timing_seconds": timing_seconds,
                "clusters": cluster_payload,
            },
        )
        return groups
