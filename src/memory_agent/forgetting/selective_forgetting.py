from memory_agent.schemas import ConflictDecision, MemoryTrace
from memory_agent.storage.memory_store import MemoryStore


class SelectiveForgetting:
    """Applies soft forgetting through supersession."""

    def apply(self, store: MemoryStore, decision: ConflictDecision, trace: MemoryTrace) -> None:
        if decision.decision == "contradict" and decision.previous_fact_id:
            store.mark_superseded(decision.previous_fact_id)
            trace.superseded_fact_ids.append(decision.previous_fact_id)
            trace.notes.append("Marked previous fact as superseded.")
