import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from nltk.tokenize import sent_tokenize
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
class RegroupUnit:
    chunk_id: str
    local_idx: int
    global_idx: int
    text: str
    unit_type: str


@dataclass
class TopicGroup:
    topic_id: str
    source_chunk_ids: List[str]
    unit_indices: List[int]
    text: str


@dataclass
class ClusteringResult:
    clusters: List[List[RegroupUnit]]
    timings: Dict[str, float]
    selected_candidate: Dict[str, Any]
    candidate_scores: List[Dict[str, Any]]


@dataclass
class PartitionCandidate:
    alpha: Optional[float]
    top_m: int
    clusters: List[List[int]]
    score: float
    metrics: Dict[str, float]


class TopicRegrouper:
    def __init__(
        self,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        similarity_threshold: float = 0.42,
        min_cluster_size: int = 2,
        reciprocal_top_k: int = 5,
        unitization_mode: str = "fact_sentence",
        trace_path: Optional[str] = None,
    ):
        self.embedding_model = embedding_model
        self.model = build_embedding_model(embedding_model)
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.reciprocal_top_k = reciprocal_top_k
        self.unitization_mode = unitization_mode
        self.partition_candidates = [
            (None, reciprocal_top_k),
            (0.0, 5),
            (0.0, 3),
            (0.5, 3),
            (1.0, 3),
            (0.5, 2),
            (1.0, 2),
        ]
        self.trace_logger = GroupTraceLogger(trace_path)

    def _normalize_sentence_units(self, text: str) -> List[str]:
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

    def _paragraph_units(self, text: str) -> List[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        return paragraphs or [text.strip()]

    def _chunk_units(self, text: str) -> List[str]:
        stripped = text.strip()
        return [stripped] if stripped else []

    def _item_to_unit_texts(self, item: RecentMemoryItem) -> tuple[str, List[str]]:
        if self.unitization_mode in {"fact_sentence", "sentence"}:
            return "fact_sentence", self._normalize_sentence_units(item.raw_text)
        if self.unitization_mode == "paragraph":
            return "paragraph", self._paragraph_units(item.raw_text)
        if self.unitization_mode == "chunk":
            return "chunk", self._chunk_units(item.raw_text)
        raise ValueError(
            f"Unknown unitization_mode '{self.unitization_mode}'. "
            "Supported modes: fact_sentence, sentence, paragraph, chunk."
        )

    def _to_units(self, items: Sequence[RecentMemoryItem]) -> List[RegroupUnit]:
        units: List[RegroupUnit] = []
        global_idx = 0
        for item in items:
            unit_type, unit_texts = self._item_to_unit_texts(item)
            for local_idx, unit_text in enumerate(unit_texts):
                units.append(
                    RegroupUnit(
                        chunk_id=item.chunk_id,
                        local_idx=local_idx,
                        global_idx=global_idx,
                        text=unit_text,
                        unit_type=unit_type,
                    )
                )
                global_idx += 1
        return units

    def _connected_components(self, adjacency: Dict[int, set[int]], units: List[RegroupUnit]) -> List[List[int]]:
        visited = set()
        clusters: List[List[int]] = []
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
            clusters.append(sorted(component, key=lambda x: units[x].global_idx))
        return clusters

    def _build_candidate_partition(
        self,
        sim: np.ndarray,
        units: List[RegroupUnit],
        base_neighbor_lists: List[List[int]],
        alpha: Optional[float],
        top_m: int,
    ) -> List[List[int]]:
        directed_neighbors: List[set[int]] = []
        for i, candidates in enumerate(base_neighbor_lists):
            if not candidates:
                directed_neighbors.append(set())
                continue
            if alpha is None:
                kept = candidates
            else:
                scores = np.array([sim[i, idx] for idx in candidates], dtype=np.float32)
                local_threshold = float(scores.mean() + alpha * scores.std())
                kept = [idx for idx in candidates if sim[i, idx] >= local_threshold]
            directed_neighbors.append(set(kept[:top_m]))

        adjacency = {idx: {idx} for idx in range(len(units))}
        for i in range(len(units)):
            for j in directed_neighbors[i]:
                if i < j and i in directed_neighbors[j]:
                    adjacency[i].add(j)
                    adjacency[j].add(i)
        return self._connected_components(adjacency, units)

    def _cluster_cohesion(self, cluster: List[int], embeddings: np.ndarray) -> float:
        if len(cluster) < self.min_cluster_size:
            return 0.0
        cluster_embeddings = embeddings[cluster]
        centroid = cluster_embeddings.mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm == 0:
            return 0.0
        centroid = centroid / norm
        embedding_norms = np.linalg.norm(cluster_embeddings, axis=1)
        valid = embedding_norms > 0
        if not np.any(valid):
            return 0.0
        normalized_embeddings = cluster_embeddings[valid] / embedding_norms[valid][:, None]
        return float(np.mean(normalized_embeddings @ centroid))

    def _score_partition(self, clusters: List[List[int]], embeddings: np.ndarray) -> Dict[str, float]:
        n_units = len(embeddings)
        k_clusters = max(1, len(clusters))
        sizes = [len(cluster) for cluster in clusters]
        non_tiny = [cluster for cluster in clusters if len(cluster) >= self.min_cluster_size]

        if non_tiny:
            weighted_cohesion = sum(
                len(cluster) * self._cluster_cohesion(cluster, embeddings)
                for cluster in non_tiny
            )
            semantics_score = weighted_cohesion / sum(len(cluster) for cluster in non_tiny)
        else:
            semantics_score = 0.0

        size_square_sum = sum(size * size for size in sizes) or 1
        balance_score = (n_units * n_units) / (k_clusters * size_square_sum)
        singleton_ratio = sum(1 for size in sizes if size == 1) / k_clusters
        tiny_cluster_ratio = sum(1 for size in sizes if size < self.min_cluster_size) / k_clusters
        fragmentation_penalty = singleton_ratio + 0.5 * tiny_cluster_ratio
        giant_penalty = (max(sizes) / n_units) if sizes and n_units else 0.0
        avg_cluster_size = n_units / k_clusters
        target_avg_cluster_size = 8.0
        avg_size_score = float(np.exp(-abs(np.log(max(avg_cluster_size, 1e-6) / target_avg_cluster_size))))
        score = (
            1.0 * semantics_score
            + 0.25 * balance_score
            + 0.75 * avg_size_score
            - 1.5 * fragmentation_penalty
            - 0.7 * giant_penalty
        )
        return {
            "score": float(score),
            "semantics_score": float(semantics_score),
            "balance_score": float(balance_score),
            "avg_size_score": float(avg_size_score),
            "avg_cluster_size": float(avg_cluster_size),
            "fragmentation_penalty": float(fragmentation_penalty),
            "giant_penalty": float(giant_penalty),
            "singleton_ratio": float(singleton_ratio),
            "tiny_cluster_ratio": float(tiny_cluster_ratio),
            "cluster_count": float(k_clusters),
            "max_cluster_size": float(max(sizes) if sizes else 0),
        }

    def _cluster_centroid(self, cluster: List[int], embeddings: np.ndarray) -> np.ndarray:
        centroid = embeddings[cluster].mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm == 0:
            return centroid
        return centroid / norm

    def _attach_tiny_clusters(self, clusters: List[List[int]], embeddings: np.ndarray) -> List[List[int]]:
        large_clusters = [list(cluster) for cluster in clusters if len(cluster) >= self.min_cluster_size]
        tiny_clusters = [list(cluster) for cluster in clusters if len(cluster) < self.min_cluster_size]
        if not large_clusters or not tiny_clusters:
            return [sorted(cluster) for cluster in clusters]

        centroids = [self._cluster_centroid(cluster, embeddings) for cluster in large_clusters]
        for tiny_cluster in tiny_clusters:
            tiny_centroid = self._cluster_centroid(tiny_cluster, embeddings)
            similarities = [float(tiny_centroid @ centroid) for centroid in centroids]
            best_idx = int(np.argmax(similarities))
            large_clusters[best_idx].extend(tiny_cluster)
            large_clusters[best_idx].sort()
            centroids[best_idx] = self._cluster_centroid(large_clusters[best_idx], embeddings)
        return [sorted(cluster) for cluster in large_clusters]

    def _select_partition(
        self,
        sim: np.ndarray,
        embeddings: np.ndarray,
        units: List[RegroupUnit],
    ) -> tuple[List[List[int]], Dict[str, Any], List[Dict[str, Any]]]:
        base_neighbor_lists: List[List[int]] = []
        for i in range(len(units)):
            ranked = np.argsort(sim[i])[::-1]
            filtered = [idx for idx in ranked if idx != i and sim[i, idx] >= self.similarity_threshold]
            base_neighbor_lists.append(filtered[: self.reciprocal_top_k])

        candidates: List[PartitionCandidate] = []
        for alpha, top_m in self.partition_candidates:
            raw_clusters = self._build_candidate_partition(sim, units, base_neighbor_lists, alpha, top_m)
            clusters = self._attach_tiny_clusters(raw_clusters, embeddings)
            metrics = self._score_partition(clusters, embeddings)
            candidates.append(
                PartitionCandidate(
                    alpha=alpha,
                    top_m=top_m,
                    clusters=clusters,
                    score=metrics["score"],
                    metrics=metrics,
                )
            )

        selected = max(candidates, key=lambda candidate: candidate.score)
        candidate_scores = []
        for candidate in candidates:
            sizes = [len(cluster) for cluster in candidate.clusters]
            candidate_scores.append(
                {
                    "alpha": candidate.alpha,
                    "top_m": candidate.top_m,
                    "score": candidate.score,
                    "cluster_count": len(candidate.clusters),
                    "max_cluster_size": max(sizes) if sizes else 0,
                    "cluster_sizes": sizes,
                    **candidate.metrics,
                }
            )
        selected_payload = {
            "alpha": selected.alpha,
            "top_m": selected.top_m,
            "score": selected.score,
            "cluster_count": len(selected.clusters),
            "max_cluster_size": max(len(cluster) for cluster in selected.clusters) if selected.clusters else 0,
        }
        return selected.clusters, selected_payload, candidate_scores

    def _cluster_units(self, units: List[RegroupUnit]) -> ClusteringResult:
        timings = {
            "embedding_seconds": 0.0,
            "similarity_seconds": 0.0,
            "partition_selection_seconds": 0.0,
        }
        if len(units) <= 1:
            start_time = time.perf_counter()
            embeddings = np.array(self.model.encode([unit.text for unit in units]), dtype=np.float32)
            timings["embedding_seconds"] = time.perf_counter() - start_time
            selected_candidate = {"alpha": None, "top_m": None, "score": 0.0, "cluster_count": len(units)}
            return ClusteringResult([units], timings, selected_candidate, [])

        start_time = time.perf_counter()
        embeddings = np.array(self.model.encode([unit.text for unit in units]), dtype=np.float32)
        timings["embedding_seconds"] = time.perf_counter() - start_time

        start_time = time.perf_counter()
        sim = cosine_similarity(embeddings)
        timings["similarity_seconds"] = time.perf_counter() - start_time

        start_time = time.perf_counter()
        selected_clusters, selected_candidate, candidate_scores = self._select_partition(sim, embeddings, units)
        timings["partition_selection_seconds"] = time.perf_counter() - start_time

        clusters = [
            [units[i] for i in sorted(cluster, key=lambda x: units[x].global_idx)]
            for cluster in selected_clusters
        ]
        return ClusteringResult(clusters, timings, selected_candidate, candidate_scores)

    def regroup(self, window_id: str, items: Sequence[RecentMemoryItem]) -> List[TopicGroup]:
        total_start_time = time.perf_counter()
        unit_start_time = time.perf_counter()
        units = self._to_units(items)
        unitization_seconds = time.perf_counter() - unit_start_time
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
                    unit_indices=[unit.global_idx for unit in cluster],
                    text=text,
                )
            )
            cluster_payload.append(
                {
                    "topic_id": f"{window_id}_topic_{idx:02d}",
                    "source_chunk_ids": source_chunk_ids,
                    "unit_indices": [unit.global_idx for unit in cluster],
                    "sentence_indices": [unit.global_idx for unit in cluster],
                    "unit_count": len(cluster),
                    "sentence_count": len(cluster),
                    "unit_type": cluster[0].unit_type if cluster else self.unitization_mode,
                    "content_preview": _preview_text(text),
                }
            )

        timing_seconds = {
            "unitization_seconds": unitization_seconds,
            "sentence_split_seconds": unitization_seconds,
            **clustering_result.timings,
        }
        timing_seconds["total_seconds"] = time.perf_counter() - total_start_time
        self.trace_logger.log(
            "topic_regrouping_complete",
            {
                "window_id": window_id,
                "input_chunk_ids": [item.chunk_id for item in items],
                "input_chunk_count": len(items),
                "unitization_mode": self.unitization_mode,
                "unit_count": len(units),
                "sentence_count": len(units),
                "cluster_count": len(groups),
                "clustering_strategy": "edge_pruning_connected_components",
                "similarity_threshold": self.similarity_threshold,
                "reciprocal_top_k": self.reciprocal_top_k,
                "selected_candidate": clustering_result.selected_candidate,
                "candidate_scores": clustering_result.candidate_scores,
                "timing_seconds": timing_seconds,
                "clusters": cluster_payload,
            },
        )
        return groups
