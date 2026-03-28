from memory_agent.storage.memory_store import MemoryStore


class Reasoner:
    """Placeholder reasoner that only returns active slot facts.

    Replace this with hop-aware path construction for real experiments.
    """

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def retrieve_active(self, entity: str, relation: str) -> list[str]:
        return [
            fact.value
            for fact in self.store.get_slot_facts(entity, relation)
            if fact.status.value == "active"
        ]
