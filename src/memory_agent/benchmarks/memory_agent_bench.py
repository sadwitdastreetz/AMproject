import re
from typing import Iterable

from datasets import load_dataset

from memory_agent.schemas import BenchmarkEpisode, MemoryTurn, QueryTurn


FACT_LINE_RE = re.compile(r"^(?P<fact_index>\d+)\.\s+(?P<fact_text>.+)$")


def parse_context_into_memory_turns(context: str, episode_id: str) -> list[MemoryTurn]:
    memory_turns: list[MemoryTurn] = []

    for line in context.splitlines():
        match = FACT_LINE_RE.match(line.strip())
        if not match:
            continue

        turn_index = len(memory_turns)
        fact_index = int(match.group("fact_index"))
        fact_text = match.group("fact_text").strip()
        memory_turns.append(
            MemoryTurn(
                turn_id=f"{episode_id}::mem::{turn_index}",
                phase="memory",
                turn_index=turn_index,
                fact_index=fact_index,
                raw_text=line.strip(),
                fact_text=fact_text,
            )
        )

    return memory_turns


def build_query_turns(
    *,
    questions: Iterable[str],
    answers: Iterable[list[str]],
    qa_pair_ids: Iterable[str],
    episode_id: str,
) -> list[QueryTurn]:
    query_turns: list[QueryTurn] = []

    for turn_index, (question, gold_answers, qa_pair_id) in enumerate(
        zip(questions, answers, qa_pair_ids)
    ):
        query_turns.append(
            QueryTurn(
                turn_id=f"{episode_id}::query::{turn_index}",
                phase="query",
                turn_index=turn_index,
                query_index=turn_index,
                qa_pair_id=qa_pair_id,
                question=question,
                gold_answers=list(gold_answers),
            )
        )

    return query_turns


def parse_source_metadata(source: str) -> tuple[str, str]:
    difficulty = "multi_hop" if "_mh_" in source else "single_hop"
    size_match = re.search(r"_(\d+k)$", source)
    if not size_match:
        raise ValueError(f"Unable to parse context size from source: {source}")
    context_size = size_match.group(1)
    return difficulty, context_size


def adapt_conflict_resolution_row(row: dict) -> BenchmarkEpisode:
    metadata = row["metadata"]
    source = metadata["source"]
    difficulty, context_size = parse_source_metadata(source)
    memory_turns = parse_context_into_memory_turns(row["context"], source)
    query_turns = build_query_turns(
        questions=row["questions"],
        answers=row["answers"],
        qa_pair_ids=metadata["qa_pair_ids"],
        episode_id=source,
    )

    if len(row["questions"]) != len(row["answers"]):
        raise ValueError("Questions and answers are not aligned.")
    if len(query_turns) != len(metadata["qa_pair_ids"]):
        raise ValueError("Questions and qa_pair_ids are not aligned.")

    return BenchmarkEpisode(
        episode_id=source,
        benchmark_split="Conflict_Resolution",
        source=source,
        difficulty=difficulty,
        context_size=context_size,
        raw_context=row["context"],
        memory_turns=memory_turns,
        query_turns=query_turns,
    )


def load_conflict_resolution_split():
    dataset = load_dataset("ai-hyz/MemoryAgentBench")
    return dataset["Conflict_Resolution"]


def load_conflict_resolution_episodes() -> list[BenchmarkEpisode]:
    split = load_conflict_resolution_split()
    return [adapt_conflict_resolution_row(row) for row in split]
