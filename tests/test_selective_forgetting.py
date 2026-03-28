from memory_agent.memory_manager import MemoryManager


def test_conflicting_fact_is_soft_superseded():
    manager = MemoryManager()
    manager.ingest_fact(
        entity="Alice",
        relation="works_at",
        value="CompanyA",
        source_text="Alice works at CompanyA.",
        turn_id=1,
    )
    manager.ingest_fact(
        entity="Alice",
        relation="works_at",
        value="CompanyB",
        source_text="Alice moved to CompanyB.",
        turn_id=2,
    )

    facts = manager.store.get_slot_facts("Alice", "works_at")
    statuses = [fact.status.value for fact in facts]
    assert statuses.count("active") == 1
    assert statuses.count("superseded") == 1
