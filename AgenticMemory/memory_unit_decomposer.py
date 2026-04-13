import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    def _build_prompt(self, turn: MemoryTurn) -> str:
        return f"""You transform one memory turn into self-contained memory units.

Rules:
- Return a JSON array only. Do not add markdown or commentary.
- A single turn may contain zero, one, or many memory units.
- Extract every useful stable fact, preference, event, constraint, relationship, plan, or state change.
- Ignore pure greetings, acknowledgements, and empty boilerplate.
- Each memory unit must be independently understandable without pronouns like "it", "this", "he", "she", or "they" unless the referent is explicit.
- Preserve benchmark facts exactly when the input is a numbered fact list. Do not correct facts using real-world knowledge.
- Use the provided timestamp/source when no better time is stated.

Return each object with this schema:
{{
  "content": "self-contained factual memory sentence",
  "keywords": ["keyword"],
  "timestamp": "{turn.timestamp}",
  "location": null,
  "persons": [],
  "entities": [],
  "topic": null,
  "confidence": 0.0
}}

Turn id: {turn.turn_id}
Source: {turn.source}
Timestamp: {turn.timestamp}

Raw turn content:
{turn.raw_context}
"""

    def decompose(self, turn: MemoryTurn, window_id: str = "") -> List[MemoryUnit]:
        prompt = self._build_prompt(turn)
        start_time = time.perf_counter()
        raw_response = ""
        try:
            raw_response = self.llm_controller.llm.get_completion(prompt, temperature=0.0)
            parsed_items = _extract_json_array(raw_response)
            units: List[MemoryUnit] = []
            for idx, item in enumerate(parsed_items):
                content = _as_optional_str(item.get("content") or item.get("lossless_restatement"))
                if not content:
                    continue
                unit_id = f"{turn.turn_id}_unit_{idx:02d}"
                units.append(
                    MemoryUnit(
                        unit_id=unit_id,
                        content=content,
                        keywords=_as_list(item.get("keywords")),
                        timestamp=_as_optional_str(item.get("timestamp")) or turn.timestamp,
                        location=_as_optional_str(item.get("location")),
                        persons=_as_list(item.get("persons")),
                        entities=_as_list(item.get("entities")),
                        topic=_as_optional_str(item.get("topic")),
                        source_turn_ids=[turn.turn_id],
                        source_turn_id=turn.turn_id,
                        source_timestamp=turn.timestamp,
                        confidence=_as_optional_float(item.get("confidence")),
                    )
                )
            self.trace_logger.log(
                "memory_unit_decomposition_complete",
                {
                    "window_id": window_id,
                    "turn_id": turn.turn_id,
                    "source": turn.source,
                    "timestamp": turn.timestamp,
                    "raw_context_preview": _preview_text(turn.raw_context),
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
                    "turn_id": turn.turn_id,
                    "source": turn.source,
                    "timestamp": turn.timestamp,
                    "raw_context_preview": _preview_text(turn.raw_context),
                    "raw_response_preview": _preview_text(raw_response),
                    "parse_success": False,
                    "error": str(exc),
                    "latency_seconds": time.perf_counter() - start_time,
                    "memory_unit_count": 0,
                },
            )
            return []
