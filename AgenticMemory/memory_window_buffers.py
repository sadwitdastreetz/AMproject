import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory_layer import DEFAULT_EMBEDDING_MODEL, SimpleEmbeddingRetriever
from memory_unit_decomposer import MemoryUnit
from short_term_memory import MemoryTurn, TokenCounter


def _preview_text(text: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


class WindowTraceLogger:
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
class RawMemoryTurnWindow:
    window_id: str
    turns: List[MemoryTurn]
    token_count: int


class RawMemoryTurnWindowBuffer:
    """SimpleMem-aligned raw turn window buffer with an added token budget trigger."""

    def __init__(
        self,
        window_size: int = 40,
        token_budget: int = 4096,
        overlap_size: int = 2,
        trace_path: Optional[str] = None,
    ):
        self.window_size = window_size
        self.token_budget = token_budget
        self.overlap_size = max(0, overlap_size)
        self.step_size = max(1, window_size - self.overlap_size)
        self.turns: List[MemoryTurn] = []
        self.token_counter = TokenCounter()
        self.token_count = 0
        self.window_counter = 0
        self.trace_logger = WindowTraceLogger(trace_path)

    def _refresh_tokens(self):
        self.token_count = sum(turn.token_count for turn in self.turns)

    def add_turn(self, turn: MemoryTurn):
        self.turns.append(turn)
        self.token_count += turn.token_count
        self.trace_logger.log(
            "raw_turn_window_added",
            {
                "turn_id": turn.turn_id,
                "token_count": turn.token_count,
                "buffer_turn_count": len(self.turns),
                "buffer_token_count": self.token_count,
                "window_size": self.window_size,
                "token_budget": self.token_budget,
                "overlap_size": self.overlap_size,
                "content_preview": _preview_text(turn.raw_context),
            },
        )

    def should_process(self) -> bool:
        return len(self.turns) >= self.window_size or self.token_count >= self.token_budget

    def pop_window(self) -> RawMemoryTurnWindow:
        window_id = f"raw_window_{self.window_counter:04d}"
        if len(self.turns) >= self.window_size:
            window_turns = list(self.turns[: self.window_size])
            step_size = self.step_size
            trigger = "turn_count"
        else:
            window_turns = list(self.turns)
            step_size = max(1, len(window_turns) - self.overlap_size)
            trigger = "token_budget"

        window_token_count = sum(turn.token_count for turn in window_turns)
        self.turns = self.turns[step_size:]
        self._refresh_tokens()
        self.window_counter += 1
        self.trace_logger.log(
            "raw_turn_window_popped",
            {
                "window_id": window_id,
                "trigger": trigger,
                "source_turn_ids": [turn.turn_id for turn in window_turns],
                "window_turn_count": len(window_turns),
                "window_token_count": window_token_count,
                "step_size": step_size,
                "retained_turn_ids": [turn.turn_id for turn in self.turns],
                "retained_turn_count": len(self.turns),
                "retained_token_count": self.token_count,
            },
        )
        return RawMemoryTurnWindow(window_id, window_turns, window_token_count)

    def pop_remaining(self) -> RawMemoryTurnWindow:
        window_id = f"raw_window_{self.window_counter:04d}_remaining"
        window_turns = list(self.turns)
        window_token_count = sum(turn.token_count for turn in window_turns)
        self.turns = []
        self._refresh_tokens()
        self.window_counter += 1
        self.trace_logger.log(
            "raw_turn_window_remaining_popped",
            {
                "window_id": window_id,
                "source_turn_ids": [turn.turn_id for turn in window_turns],
                "window_turn_count": len(window_turns),
                "window_token_count": window_token_count,
                "retained_turn_ids": [],
                "retained_turn_count": 0,
                "retained_token_count": self.token_count,
            },
        )
        return RawMemoryTurnWindow(window_id, window_turns, window_token_count)


class MemoryUnitPingPongBuffer:
    def __init__(
        self,
        token_budget: int = 4096,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        trace_path: Optional[str] = None,
    ):
        self.token_budget = token_budget
        self.region_size = max(1, token_budget // 2)
        self.token_counter = TokenCounter()
        self.trace_logger = WindowTraceLogger(trace_path)
        self.embedding_model = embedding_model
        self.regions: List[List[MemoryUnit]] = [[], []]
        self.region_tokens = [0, 0]
        self.region_full = [False, False]
        self.active_region = 0
        self.pending_flush_region: Optional[int] = None
        self.units: List[MemoryUnit] = []
        self.total_tokens = 0
        self.window_counter = 0
        self.retriever = SimpleEmbeddingRetriever(embedding_model)

    def _unit_tokens(self, unit: MemoryUnit) -> int:
        return self.token_counter.count(unit.content)

    def _refresh_units(self):
        self.units = self.regions[0] + self.regions[1]
        self.total_tokens = sum(self.region_tokens)

    def _rebuild_retriever(self):
        self.retriever = SimpleEmbeddingRetriever(self.embedding_model)
        if self.units:
            self.retriever.add_documents([unit.content for unit in self.units])

    def add_units(self, units: List[MemoryUnit]):
        for unit in units:
            token_count = self._unit_tokens(unit)
            region_id = self.active_region
            self.regions[region_id].append(unit)
            self.region_tokens[region_id] += token_count
            if self.region_tokens[region_id] >= self.region_size:
                self.region_full[region_id] = True
                other_region = 1 - region_id
                if self.region_full[other_region]:
                    self.pending_flush_region = other_region
                else:
                    self.active_region = other_region
            self._refresh_units()
            self.trace_logger.log(
                "memory_unit_added",
                {
                    "unit_id": unit.unit_id,
                    "source_turn_ids": unit.source_turn_ids,
                    "token_count": token_count,
                    "region_id": region_id,
                    "active_region": self.active_region,
                    "region_size": self.region_size,
                    "region_tokens": list(self.region_tokens),
                    "region_full": list(self.region_full),
                    "pending_flush_region": self.pending_flush_region,
                    "buffer_unit_count": len(self.units),
                    "buffer_token_count": self.total_tokens,
                    "content_preview": _preview_text(unit.content),
                },
            )
        self._rebuild_retriever()

    def should_flush(self) -> bool:
        return self.pending_flush_region is not None

    def flush_window(self) -> tuple[str, List[MemoryUnit]]:
        window_id = f"unit_window_{self.window_counter:04d}"
        if self.pending_flush_region is None:
            return window_id, []
        flush_region = self.pending_flush_region
        flush_units = list(self.regions[flush_region])
        self.trace_logger.log(
            "memory_unit_flush_started",
            {
                "window_id": window_id,
                "flush_region": flush_region,
                "flush_unit_ids": [unit.unit_id for unit in flush_units],
                "flush_unit_count": len(flush_units),
                "flush_token_count": self.region_tokens[flush_region],
                "region_tokens": list(self.region_tokens),
                "region_full": list(self.region_full),
            },
        )
        self.regions[flush_region] = []
        self.region_tokens[flush_region] = 0
        self.region_full[flush_region] = False
        self.pending_flush_region = None
        self.active_region = flush_region
        self._refresh_units()
        self._rebuild_retriever()
        self.window_counter += 1
        self.trace_logger.log(
            "memory_unit_flush_region_cleared",
            {
                "window_id": window_id,
                "cleared_region": flush_region,
                "active_region": self.active_region,
                "retained_unit_ids": [unit.unit_id for unit in self.units],
                "region_tokens_after_clear": list(self.region_tokens),
                "buffer_token_count_after_clear": self.total_tokens,
            },
        )
        return window_id, flush_units

    def flush_remaining(self) -> tuple[str, List[MemoryUnit]]:
        window_id = f"unit_window_{self.window_counter:04d}_remaining"
        flush_units = list(self.units)
        if not flush_units:
            return window_id, []
        self.trace_logger.log(
            "memory_unit_flush_remaining_started",
            {
                "window_id": window_id,
                "flush_unit_ids": [unit.unit_id for unit in flush_units],
                "flush_unit_count": len(flush_units),
                "flush_token_count": self.total_tokens,
                "region_tokens": list(self.region_tokens),
                "region_full": list(self.region_full),
            },
        )
        self.regions = [[], []]
        self.region_tokens = [0, 0]
        self.region_full = [False, False]
        self.active_region = 0
        self.pending_flush_region = None
        self._refresh_units()
        self._rebuild_retriever()
        self.window_counter += 1
        self.trace_logger.log(
            "memory_unit_flush_remaining_cleared",
            {
                "window_id": window_id,
                "retained_unit_ids": [],
                "buffer_token_count_after_clear": self.total_tokens,
            },
        )
        return window_id, flush_units

    def retrieve(self, query: str, k: int = 5) -> List[MemoryUnit]:
        if not self.units:
            return []
        indices = self.retriever.search(query, k=min(k, len(self.units)))
        return [self.units[idx] for idx in indices]

    def format_for_prompt(self, units: List[MemoryUnit]) -> str:
        if not units:
            return "No structured working memory available."
        lines = []
        for unit in units:
            source_turn_ids = ", ".join(unit.source_turn_ids)
            metadata = []
            if unit.topic:
                metadata.append(f"topic={unit.topic}")
            if unit.keywords:
                metadata.append(f"keywords={', '.join(unit.keywords)}")
            if unit.entities:
                metadata.append(f"entities={', '.join(unit.entities)}")
            metadata_text = f"\nmetadata: {'; '.join(metadata)}" if metadata else ""
            lines.append(
                f"memory unit id:{unit.unit_id}\n"
                f"source turn ids:{source_turn_ids}\n"
                f"memory unit content:\n{unit.content}"
                f"{metadata_text}"
            )
        return "\n\n".join(lines)
