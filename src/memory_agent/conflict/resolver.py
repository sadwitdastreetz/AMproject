from memory_agent.schemas import ConflictDecision, Fact


class ConflictResolver:
    """MVP contradiction resolver.

    The initial version uses a simple slot-based rule:
    same entity + relation but different value => contradiction/update.
    """

    def resolve(self, incoming: Fact, existing: list[Fact]) -> ConflictDecision:
        for fact in reversed(existing):
            if fact.value.strip().lower() != incoming.value.strip().lower():
                return ConflictDecision(
                    decision="contradict",
                    previous_fact_id=fact.fact_id,
                    rationale="Same entity-relation slot with a different value.",
                )
        return ConflictDecision(
            decision="support",
            previous_fact_id=None,
            rationale="No contradictory value found in the same slot.",
        )
