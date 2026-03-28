from memory_agent.benchmarks.memory_agent_bench import (
    adapt_conflict_resolution_row,
    parse_context_into_memory_turns,
    parse_source_metadata,
)


def test_parse_source_metadata_for_multi_hop_episode():
    difficulty, context_size = parse_source_metadata("factconsolidation_mh_32k")
    assert difficulty == "multi_hop"
    assert context_size == "32k"


def test_parse_context_into_memory_turns_extracts_numbered_facts():
    context = (
        "Here is a list of facts:\n"
        "0. Alice works at CompanyA.\n"
        "1. Bob lives in Paris.\n"
        "Ignored footer line."
    )

    turns = parse_context_into_memory_turns(context, "episode_x")

    assert len(turns) == 2
    assert turns[0].turn_id == "episode_x::mem::0"
    assert turns[0].fact_index == 0
    assert turns[0].fact_text == "Alice works at CompanyA."
    assert turns[1].fact_index == 1
    assert turns[1].raw_text == "1. Bob lives in Paris."


def test_adapt_conflict_resolution_row_builds_episode_with_aligned_queries():
    row = {
        "context": (
            "Here is a list of facts:\n"
            "0. Alice works at CompanyA.\n"
            "1. Alice works at CompanyB.\n"
        ),
        "questions": ["Where does Alice work?"],
        "answers": [["CompanyB"]],
        "metadata": {
            "source": "factconsolidation_sh_6k",
            "qa_pair_ids": ["factconsolidation_sh_6k_no0"],
        },
    }

    episode = adapt_conflict_resolution_row(row)

    assert episode.episode_id == "factconsolidation_sh_6k"
    assert episode.benchmark_split == "Conflict_Resolution"
    assert episode.difficulty == "single_hop"
    assert episode.context_size == "6k"
    assert len(episode.memory_turns) == 2
    assert len(episode.query_turns) == 1
    assert episode.query_turns[0].qa_pair_id == "factconsolidation_sh_6k_no0"
    assert episode.query_turns[0].gold_answers == ["CompanyB"]
