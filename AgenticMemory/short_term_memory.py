import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory_layer import DEFAULT_EMBEDDING_MODEL, SimpleEmbeddingRetriever


def _preview_text(text: str, limit: int = 180) -> str:
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


class RecentTraceLogger:
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


class TokenCounter:
    def __init__(self):
        self._encoding = None
        try:
            import tiktoken

            self._encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._encoding = None

    def count(self, text: str) -> int:
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return max(1, len(text.split()))


@dataclass
class MemoryTurn:
    turn_id: str
    raw_context: str
    formatted_turn: str
    source: str
    timestamp: str
    token_count: int
    ingest_index: int
    unitization_decision: Optional[Dict[str, Any]] = None


class ShortTermMemoryBuffer:
    def __init__(
        self,
        token_budget: int = 4096,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        trace_path: Optional[str] = None,
    ):
        self.token_budget = token_budget
        self.region_size = max(1, token_budget // 2)
        self.token_counter = TokenCounter()
        self.trace_logger = RecentTraceLogger(trace_path)
        self.embedding_model = embedding_model
        self.regions: List[List[MemoryTurn]] = [[], []]
        self.region_tokens = [0, 0]
        self.region_full = [False, False]
        self.active_region = 0
        self.pending_flush_region: Optional[int] = None
        self.turns: List[MemoryTurn] = []
        self.total_tokens = 0
        self.window_counter = 0
        self.ingest_counter = 0
        self.retriever = SimpleEmbeddingRetriever(embedding_model)

    def _refresh_items(self):
        self.turns = sorted(
            self.regions[0] + self.regions[1],
            key=lambda turn: turn.ingest_index,
        )
        self.total_tokens = sum(self.region_tokens)

    def _rebuild_retriever(self):
        self.retriever = SimpleEmbeddingRetriever(self.embedding_model)
        if self.turns:
            self.retriever.add_documents([turn.raw_context for turn in self.turns])

    def add_turn(
        self,
        turn_id: str,
        raw_context: str,
        formatted_turn: str,
        source: str,
        timestamp: str,
        unitization_decision: Optional[Dict[str, Any]] = None,
    ) -> MemoryTurn:
        token_count = self.token_counter.count(raw_context)
        turn = MemoryTurn(
            turn_id=turn_id,
            raw_context=raw_context,
            formatted_turn=formatted_turn,
            source=source,
            timestamp=timestamp,
            token_count=token_count,
            ingest_index=self.ingest_counter,
            unitization_decision=unitization_decision,
        )
        self.ingest_counter += 1
        region_id = self.active_region
        self.regions[region_id].append(turn)
        self.region_tokens[region_id] += token_count
        if self.region_tokens[region_id] >= self.region_size:
            self.region_full[region_id] = True
            other_region = 1 - region_id
            if self.region_full[other_region]:
                self.pending_flush_region = other_region
            else:
                self.active_region = other_region
        self._refresh_items()
        self._rebuild_retriever()
        self.trace_logger.log(
            "recent_item_added",
            {
                "turn_id": turn_id,
                "source": source,
                "timestamp": timestamp,
                "token_count": token_count,
                "region_id": region_id,
                "active_region": self.active_region,
                "region_size": self.region_size,
                "region_tokens": list(self.region_tokens),
                "region_full": list(self.region_full),
                "pending_flush_region": self.pending_flush_region,
                "buffer_size": len(self.turns),
                "buffer_tokens": self.total_tokens,
                "unitization_decision": unitization_decision,
                "content_preview": _preview_text(raw_context),
            },
        )
        return turn

    def should_flush(self) -> bool:
        return self.pending_flush_region is not None

    def snapshot_turns(self) -> List[MemoryTurn]:
        return list(self.turns)

    def flush_window(self) -> tuple[str, List[MemoryTurn]]:
        window_id = f"window_{self.window_counter:04d}"
        buffer_turns = self.snapshot_turns()
        if self.pending_flush_region is None:
            return window_id, []
        flush_region = self.pending_flush_region
        flush_turns = list(self.regions[flush_region])
        self.trace_logger.log(
            "recent_flush_started",
            {
                "window_id": window_id,
                "flush_region": flush_region,
                "buffer_turn_count": len(buffer_turns),
                "flush_turn_count": len(flush_turns),
                "buffer_item_count": len(buffer_turns),
                "flush_item_count": len(flush_turns),
                "buffer_tokens": self.total_tokens,
                "region_size": self.region_size,
                "region_tokens": list(self.region_tokens),
                "region_full": list(self.region_full),
                "buffer_turn_ids": [turn.turn_id for turn in buffer_turns],
                "flush_turn_ids": [turn.turn_id for turn in flush_turns],
                "buffer_chunk_ids": [turn.turn_id for turn in buffer_turns],
                "flush_chunk_ids": [turn.turn_id for turn in flush_turns],
            },
        )
        self.regions[flush_region] = []
        self.region_tokens[flush_region] = 0
        self.region_full[flush_region] = False
        self.pending_flush_region = None
        self.active_region = flush_region
        self._refresh_items()
        self.window_counter += 1
        self._rebuild_retriever()
        self.trace_logger.log(
            "recent_flush_region_cleared",
            {
                "window_id": window_id,
                "cleared_region": flush_region,
                "active_region": self.active_region,
                "retained_turn_ids": [turn.turn_id for turn in self.turns],
                "retained_chunk_ids": [turn.turn_id for turn in self.turns],
                "region_tokens_after_clear": list(self.region_tokens),
                "region_full_after_clear": list(self.region_full),
                "buffer_tokens_after_clear": self.total_tokens,
                "buffer_size_after_clear": len(self.turns),
            },
        )
        return window_id, flush_turns

    def retrieve(self, query: str, k: int = 5) -> List[MemoryTurn]:
        if not self.turns:
            return []
        indices = self.retriever.search(query, k=min(k, len(self.turns)))
        return [self.turns[idx] for idx in indices]

    def format_for_prompt(self, turns: List[MemoryTurn]) -> str:
        if not turns:
            return "No recent memory available."
        lines = []
        for turn in turns:
            lines.append(
                f"recent turn id:{turn.turn_id}\nrecent content:\n{turn.formatted_turn}"
            )
        return "\n\n".join(lines)
