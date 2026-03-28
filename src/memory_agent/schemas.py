from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class FactStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    UNCERTAIN = "uncertain"


@dataclass
class Fact:
    fact_id: str
    entity: str
    relation: str
    value: str
    turn_id: int
    source_text: str
    status: FactStatus = FactStatus.ACTIVE
    confidence: float = 1.0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConflictDecision:
    decision: str
    previous_fact_id: Optional[str]
    rationale: str


@dataclass
class MemoryTrace:
    ingested_fact_ids: List[str] = field(default_factory=list)
    superseded_fact_ids: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class MemoryTurn:
    turn_id: str
    phase: str
    turn_index: int
    fact_index: int
    raw_text: str
    fact_text: str
    role: str = "user"
    operation: str = "add_fact"


@dataclass
class QueryTurn:
    turn_id: str
    phase: str
    turn_index: int
    query_index: int
    qa_pair_id: str
    question: str
    gold_answers: List[str]
    role: str = "user"


@dataclass
class BenchmarkEpisode:
    episode_id: str
    benchmark_split: str
    source: str
    difficulty: str
    context_size: str
    raw_context: str
    memory_turns: List[MemoryTurn]
    query_turns: List[QueryTurn]
