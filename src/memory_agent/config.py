from dataclasses import dataclass


@dataclass
class RetrievalConfig:
    top_k: int = 5
    include_superseded_for_debug: bool = False


@dataclass
class ReasoningConfig:
    max_hops: int = 3
    reject_superseded_paths: bool = True
