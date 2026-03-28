from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from memory_agent.schemas import Fact, FactStatus


class MemoryStore:
    """Minimal in-memory fact store with relation-slot lookup."""

    def __init__(self) -> None:
        self.facts: Dict[str, Fact] = {}
        self.by_slot: Dict[str, List[str]] = defaultdict(list)

    @staticmethod
    def _slot(entity: str, relation: str) -> str:
        return f"{entity.strip().lower()}::{relation.strip().lower()}"

    def add_fact(self, fact: Fact) -> None:
        self.facts[fact.fact_id] = fact
        self.by_slot[self._slot(fact.entity, fact.relation)].append(fact.fact_id)

    def get_slot_facts(self, entity: str, relation: str) -> List[Fact]:
        ids = self.by_slot.get(self._slot(entity, relation), [])
        return [self.facts[fid] for fid in ids]

    def get_active_facts(self) -> List[Fact]:
        return [fact for fact in self.facts.values() if fact.status == FactStatus.ACTIVE]

    def mark_superseded(self, fact_id: str) -> None:
        self.facts[fact_id].status = FactStatus.SUPERSEDED
