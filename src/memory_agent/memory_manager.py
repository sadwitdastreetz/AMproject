from __future__ import annotations

from uuid import uuid4

from memory_agent.conflict.resolver import ConflictResolver
from memory_agent.forgetting.selective_forgetting import SelectiveForgetting
from memory_agent.schemas import Fact, MemoryTrace
from memory_agent.storage.memory_store import MemoryStore


class MemoryManager:
    """Coordinates fact ingestion, conflict detection, and soft forgetting."""

    def __init__(self) -> None:
        self.store = MemoryStore()
        self.resolver = ConflictResolver()
        self.forgetting = SelectiveForgetting()

    def ingest_fact(
        self,
        *,
        entity: str,
        relation: str,
        value: str,
        source_text: str,
        turn_id: int,
    ) -> MemoryTrace:
        trace = MemoryTrace()
        fact = Fact(
            fact_id=str(uuid4()),
            entity=entity,
            relation=relation,
            value=value,
            source_text=source_text,
            turn_id=turn_id,
        )
        existing = self.store.get_slot_facts(entity, relation)
        decision = self.resolver.resolve(fact, existing)
        self.forgetting.apply(self.store, decision, trace)
        self.store.add_fact(fact)
        trace.ingested_fact_ids.append(fact.fact_id)
        trace.notes.append(decision.rationale)
        return trace
