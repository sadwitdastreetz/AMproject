import json
import re
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


class TopicRegrouper:
    def __init__(
        self,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        similarity_threshold: float = 0.42,
        min_cluster_size: int = 2,
        trace_path: Optional[str] = None,
    ):
        self.embedding_model = embedding_model
        self.model = build_embedding_model(embedding_model)
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.trace_logger = GroupTraceLogger(trace_path)

    def _to_sentence_units(self, items: Sequence[RecentMemoryItem]) -> List[SentenceUnit]:
        units: List[SentenceUnit] = []
        global_idx = 0
        for item in items:
            sentences = [s.strip() for s in sent_tokenize(item.raw_text) if s.strip()]
            if not sentences:
                sentences = [item.raw_text.strip()]
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

    def _cluster_units(self, units: List[SentenceUnit]) -> List[List[SentenceUnit]]:
        if len(units) <= 1:
            return [units]

        embeddings = np.array(self.model.encode([unit.text for unit in units]), dtype=np.float32)
        sim = cosine_similarity(embeddings)
        adjacency = {idx: set() for idx in range(len(units))}
        for i in range(len(units)):
            adjacency[i].add(i)
            for j in range(i + 1, len(units)):
                if sim[i, j] >= self.similarity_threshold:
                    adjacency[i].add(j)
                    adjacency[j].add(i)

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

        large_clusters = [cluster for cluster in clusters if len(cluster) >= self.min_cluster_size]
        small_clusters = [cluster for cluster in clusters if len(cluster) < self.min_cluster_size]

        if not large_clusters:
            return [sorted(units, key=lambda unit: unit.global_idx)]

        for cluster in small_clusters:
            large_clusters[0].extend(cluster)
            large_clusters[0].sort(key=lambda unit: unit.global_idx)
        return large_clusters

    def regroup(self, window_id: str, items: Sequence[RecentMemoryItem]) -> List[TopicGroup]:
        units = self._to_sentence_units(items)
        if not units:
            return []

        clusters = self._cluster_units(units)
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

        self.trace_logger.log(
            "topic_regrouping_complete",
            {
                "window_id": window_id,
                "input_chunk_ids": [item.chunk_id for item in items],
                "input_chunk_count": len(items),
                "sentence_count": len(units),
                "cluster_count": len(groups),
                "clusters": cluster_payload,
            },
        )
        return groups
