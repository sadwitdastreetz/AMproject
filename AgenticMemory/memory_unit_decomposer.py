import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from short_term_memory import MemoryTurn


def _preview_text(text: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, list):
        raise ValueError("Memory unit decomposition must return a JSON array.")
    return [item for item in parsed if isinstance(item, dict)]


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _as_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


class MemoryUnitTraceLogger:
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
            handle.write(json.dumps(_json_safe(event), ensure_ascii=False) + "\n")


@dataclass
class MemoryUnit:
    unit_id: str
    content: str
    keywords: List[str]
    timestamp: Optional[str]
    location: Optional[str]
    persons: List[str]
    entities: List[str]
    topic: Optional[str]
    source_turn_ids: List[str]
    source_turn_id: str
    source_timestamp: str
    confidence: Optional[float] = None


class MemoryUnitDecomposer:
    def __init__(self, llm_controller, trace_path: Optional[str] = None):
        self.llm_controller = llm_controller
        self.trace_logger = MemoryUnitTraceLogger(trace_path)

    def _format_turns(self, turns: Sequence[MemoryTurn]) -> str:
        formatted = []
        for turn in turns:
            formatted.append(
                f"[{turn.timestamp}] {turn.turn_id} ({turn.source})\n{turn.raw_context}"
            )
        return "\n\n".join(formatted)

    def _build_window_prompt(self, turns: Sequence[MemoryTurn]) -> str:
        turn_text = self._format_turns(turns)
        source_turn_ids = [turn.turn_id for turn in turns]
        timestamp_hint = turns[0].timestamp if turns else None
        return f"""You transform a window of dialogue turns into self-contained memory units.

Rules:
- Return a JSON array only. Do not add markdown or commentary.
- A turn window may contain zero, one, or many memory units.
- Extract every useful stable fact, preference, event, constraint, relationship, plan, or state change.
- Ignore pure greetings, acknowledgements, and empty boilerplate.
- Each memory unit must be independently understandable without pronouns like "it", "this", "he", "she", or "they" unless the referent is explicit.
- Preserve benchmark facts exactly when the input is a numbered fact list. Do not correct facts using real-world knowledge.
- Use the provided timestamp/source when no better time is stated.
- This follows the SimpleMem MemoryEntry idea: lossless, self-contained restatements with keywords and symbolic metadata.

Return each object with this schema:
{{
  "lossless_restatement": "self-contained factual memory sentence",
  "keywords": ["keyword"],
  "timestamp": "{timestamp_hint}",
  "location": null,
  "persons": [],
  "entities": [],
  "topic": null,
  "source_turn_ids": ["turn id"],
  "confidence": 0.0
}}

Source turn ids: {json.dumps(source_turn_ids, ensure_ascii=False)}

Current window turns:
{turn_text}
"""

    def _build_prompt(self, turn: MemoryTurn) -> str:
        return self._build_window_prompt([turn])

    def decompose(self, turn: MemoryTurn, window_id: str = "") -> List[MemoryUnit]:
        return self.decompose_window(window_id=window_id, turns=[turn])

    def decompose_window(self, window_id: str, turns: Sequence[MemoryTurn]) -> List[MemoryUnit]:
        prompt = self._build_window_prompt(turns)
        start_time = time.perf_counter()
        raw_response = ""
        source_turn_ids = [turn.turn_id for turn in turns]
        source_timestamp = turns[0].timestamp if turns else ""
        turn_by_id = {turn.turn_id: turn for turn in turns}
        try:
            raw_response = self.llm_controller.llm.get_completion(prompt, temperature=0.0)
            parsed_items = _extract_json_array(raw_response)
            units: List[MemoryUnit] = []
            for idx, item in enumerate(parsed_items):
                content = _as_optional_str(item.get("content") or item.get("lossless_restatement"))
                if not content:
                    continue
                item_source_turn_ids = _as_list(item.get("source_turn_ids")) or source_turn_ids
                item_source_turn_ids = [turn_id for turn_id in item_source_turn_ids if turn_id in turn_by_id] or source_turn_ids
                primary_source_turn_id = item_source_turn_ids[0] if item_source_turn_ids else (source_turn_ids[0] if source_turn_ids else "")
                primary_turn = turn_by_id.get(primary_source_turn_id)
                unit_id = f"{window_id or primary_source_turn_id}_unit_{idx:02d}"
                units.append(
                    MemoryUnit(
                        unit_id=unit_id,
                        content=content,
                        keywords=_as_list(item.get("keywords")),
                        timestamp=_as_optional_str(item.get("timestamp")) or (primary_turn.timestamp if primary_turn else source_timestamp),
                        location=_as_optional_str(item.get("location")),
                        persons=_as_list(item.get("persons")),
                        entities=_as_list(item.get("entities")),
                        topic=_as_optional_str(item.get("topic")),
                        source_turn_ids=item_source_turn_ids,
                        source_turn_id=primary_source_turn_id,
                        source_timestamp=primary_turn.timestamp if primary_turn else source_timestamp,
                        confidence=_as_optional_float(item.get("confidence")),
                    )
                )
            self.trace_logger.log(
                "memory_unit_decomposition_complete",
                {
                    "window_id": window_id,
                    "source_turn_ids": source_turn_ids,
                    "turn_count": len(turns),
                    "window_token_count": sum(turn.token_count for turn in turns),
                    "source": turns[0].source if turns else "",
                    "timestamp": source_timestamp,
                    "raw_context_preview": _preview_text(self._format_turns(turns)),
                    "raw_response_preview": _preview_text(raw_response),
                    "parse_success": True,
                    "memory_unit_count": len(units),
                    "latency_seconds": time.perf_counter() - start_time,
                    "memory_units": [unit.__dict__ for unit in units],
                },
            )
            return units
        except Exception as exc:
            self.trace_logger.log(
                "memory_unit_decomposition_failed",
                {
                    "window_id": window_id,
                    "source_turn_ids": source_turn_ids,
                    "turn_count": len(turns),
                    "window_token_count": sum(turn.token_count for turn in turns),
                    "source": turns[0].source if turns else "",
                    "timestamp": source_timestamp,
                    "raw_context_preview": _preview_text(self._format_turns(turns)),
                    "raw_response_preview": _preview_text(raw_response),
                    "parse_success": False,
                    "error": str(exc),
                    "latency_seconds": time.perf_counter() - start_time,
                    "memory_unit_count": 0,
                },
            )
            return []
