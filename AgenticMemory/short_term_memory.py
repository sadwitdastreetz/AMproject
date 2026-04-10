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
class RecentMemoryItem:
    chunk_id: str
    raw_text: str
    formatted_text: str
    token_count: int
    ingest_index: int


class ShortTermMemoryBuffer:
    def __init__(
        self,
        token_budget: int = 4096,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        trace_path: Optional[str] = None,
    ):
        self.token_budget = token_budget
        self.token_counter = TokenCounter()
        self.trace_logger = RecentTraceLogger(trace_path)
        self.embedding_model = embedding_model
        self.items: List[RecentMemoryItem] = []
        self.total_tokens = 0
        self.window_counter = 0
        self.ingest_counter = 0
        self.retriever = SimpleEmbeddingRetriever(embedding_model)

    def _rebuild_retriever(self):
        self.retriever = SimpleEmbeddingRetriever(self.embedding_model)
        if self.items:
            self.retriever.add_documents([item.raw_text for item in self.items])

    def add_item(self, chunk_id: str, raw_text: str, formatted_text: str) -> RecentMemoryItem:
        token_count = self.token_counter.count(raw_text)
        item = RecentMemoryItem(
            chunk_id=chunk_id,
            raw_text=raw_text,
            formatted_text=formatted_text,
            token_count=token_count,
            ingest_index=self.ingest_counter,
        )
        self.ingest_counter += 1
        self.items.append(item)
        self.total_tokens += token_count
        self._rebuild_retriever()
        self.trace_logger.log(
            "recent_item_added",
            {
                "chunk_id": chunk_id,
                "token_count": token_count,
                "buffer_size": len(self.items),
                "buffer_tokens": self.total_tokens,
                "content_preview": _preview_text(raw_text),
            },
        )
        return item

    def should_flush(self) -> bool:
        return self.total_tokens >= self.token_budget and bool(self.items)

    def snapshot_items(self) -> List[RecentMemoryItem]:
        return list(self.items)

    def flush_window(self) -> tuple[str, List[RecentMemoryItem]]:
        window_id = f"window_{self.window_counter:04d}"
        items = self.snapshot_items()
        self.trace_logger.log(
            "recent_flush_started",
            {
                "window_id": window_id,
                "item_count": len(items),
                "buffer_tokens": self.total_tokens,
                "chunk_ids": [item.chunk_id for item in items],
            },
        )
        self.items = []
        self.total_tokens = 0
        self.window_counter += 1
        self._rebuild_retriever()
        self.trace_logger.log(
            "recent_flush_cleared",
            {
                "window_id": window_id,
                "buffer_tokens_after_clear": self.total_tokens,
                "buffer_size_after_clear": len(self.items),
            },
        )
        return window_id, items

    def retrieve(self, query: str, k: int = 5) -> List[RecentMemoryItem]:
        if not self.items:
            return []
        indices = self.retriever.search(query, k=min(k, len(self.items)))
        return [self.items[idx] for idx in indices]

    def format_for_prompt(self, items: List[RecentMemoryItem]) -> str:
        if not items:
            return "No recent memory available."
        lines = []
        for item in items:
            lines.append(
                f"recent chunk id:{item.chunk_id}\nrecent content:\n{item.raw_text}"
            )
        return "\n\n".join(lines)
