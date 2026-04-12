import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from short_term_memory import MemoryTurn


SUPPORTED_UNITIZATION_MODES = {"fact_sentence", "sentence", "dialogue_turn", "paragraph", "example", "chunk"}


@dataclass
class UnitizationDecision:
    mode: str
    confidence: float
    reason: str
    router_type: str
    raw_response: str = ""
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "confidence": self.confidence,
            "reason": self.reason,
            "router_type": self.router_type,
            "raw_response": self.raw_response,
            "fallback_used": self.fallback_used,
        }


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in router response: {text[:200]}")
    return json.loads(match.group(0))


class AgenticUnitizationRouter:
    def __init__(
        self,
        llm_controller,
        preview_chars: int = 4000,
        default_mode: str = "chunk",
        fail_on_error: bool = True,
    ):
        self.llm_controller = llm_controller
        self.preview_chars = preview_chars
        self.default_mode = default_mode
        self.fail_on_error = fail_on_error

    def _build_preview(self, turns: Sequence[MemoryTurn]) -> str:
        chunks = []
        for turn in turns:
            chunks.append(f"[{turn.turn_id}]\n{turn.formatted_turn}")
        preview = "\n\n".join(chunks)
        if len(preview) > self.preview_chars:
            preview = preview[: self.preview_chars] + "\n...[truncated]"
        return preview

    def decide(self, window_id: str, turns: Sequence[MemoryTurn], source: str = "") -> UnitizationDecision:
        preview = self._build_preview(turns)
        prompt = f"""You are routing an incoming memory buffer window to a local unitization strategy before archival memory construction.

Choose exactly one unitization_mode:
- fact_sentence: use when the content is a list of independent atomic facts, often numbered facts.
- dialogue_turn: use when the content is a conversation or chat history with user/assistant/system turns.
- paragraph: use when the content is prose, book excerpts, articles, documents, narratives, or paragraphs.
- example: use when the content is a list of training/demo examples such as utterance-label or question-label pairs.
- chunk: use only when the format is ambiguous or the whole chunk should remain intact.

Do not optimize for benchmark score. Choose the natural local memory unit implied by the input format.

Dataset/source hint: {source or "unknown"}
Window id: {window_id}

Memory window preview:
{preview}

Return only a JSON object with this schema:
{{
  "unitization_mode": "fact_sentence|dialogue_turn|paragraph|example|chunk",
  "confidence": 0.0,
  "reason": "brief reason"
}}"""
        try:
            raw_response = self.llm_controller.llm.get_completion(prompt, temperature=0.0)
            parsed = _extract_json_object(raw_response)
            mode = str(parsed.get("unitization_mode", "")).strip()
            if mode == "sentence":
                mode = "fact_sentence"
            if mode not in SUPPORTED_UNITIZATION_MODES:
                raise ValueError(f"Unsupported unitization mode from router: {mode}")
            confidence = float(parsed.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))
            reason = str(parsed.get("reason", "")).strip()
            return UnitizationDecision(
                mode=mode,
                confidence=confidence,
                reason=reason,
                router_type="agentic",
                raw_response=raw_response,
                fallback_used=False,
            )
        except Exception as exc:
            if self.fail_on_error:
                raise
            return UnitizationDecision(
                mode=self.default_mode,
                confidence=0.0,
                reason=f"Router failed; used default mode. Error: {exc}",
                router_type="agentic",
                raw_response="",
                fallback_used=True,
            )
