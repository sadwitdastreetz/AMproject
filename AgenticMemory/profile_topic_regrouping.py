import argparse
import json
import os
import sys
from pathlib import Path

from datasets import load_dataset

from memory_layer import DEFAULT_EMBEDDING_MODEL
from short_term_memory import RecentMemoryItem, TokenCounter
from topic_regrouper import TopicRegrouper
from unitization_router import SUPPORTED_UNITIZATION_MODES


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCH_ROOT = PROJECT_ROOT / "MemoryAgentBench"
if not BENCH_ROOT.exists():
    BENCH_ROOT = Path(r"C:\Users\ddger\Documents\AMproject\MemoryAgentBench")
BENCH_UTILS = BENCH_ROOT / "utils"
for path in (BENCH_ROOT, BENCH_UTILS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from eval_other_utils import chunk_text_into_sentences
from templates import get_template


def load_conflict_resolution_row(source_name: str):
    dataset = load_dataset("ai-hyz/MemoryAgentBench", split="Conflict_Resolution")
    for row in dataset:
        if row.get("metadata", {}).get("source") == source_name:
            return row
    raise ValueError(f"Could not find source '{source_name}' in Conflict_Resolution split.")


def main():
    parser = argparse.ArgumentParser(
        description="Profile one short-term buffer window topic regrouping call without A-Mem writes."
    )
    parser.add_argument("--source", default="factconsolidation_sh_32k")
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--recent-token-budget", type=int, default=4096)
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    )
    parser.add_argument("--regroup-similarity-threshold", type=float, default=0.42)
    parser.add_argument("--regroup-min-cluster-size", type=int, default=2)
    parser.add_argument(
        "--regroup-unitization-mode",
        default="fact_sentence",
        choices=sorted(SUPPORTED_UNITIZATION_MODES),
    )
    parser.add_argument("--trace-path", default="profile_topic_regrouping_trace.jsonl")
    parser.add_argument("--output", default="profile_topic_regrouping_result.json")
    args = parser.parse_args()

    row = load_conflict_resolution_row(args.source)
    chunks = chunk_text_into_sentences(row["context"], chunk_size=args.chunk_size)
    memorize_template = get_template("factconsolidation_sh_6k", "memorize", "Agentic_memory")

    token_counter = TokenCounter()
    items = []
    selected_chunks = []
    total_tokens = 0
    for chunk_idx, chunk in enumerate(chunks):
        chunk_id = f"chunk_{chunk_idx:04d}"
        formatted_chunk = memorize_template.format(context=chunk, time_stamp=chunk_id)
        token_count = token_counter.count(chunk)
        items.append(
            RecentMemoryItem(
                chunk_id=chunk_id,
                raw_text=chunk,
                formatted_text=formatted_chunk,
                token_count=token_count,
                ingest_index=chunk_idx,
            )
        )
        selected_chunks.append(chunk_id)
        total_tokens += token_count
        if total_tokens >= args.recent_token_budget:
            break

    window_id = "window_0000"
    regrouper = TopicRegrouper(
        embedding_model=args.embedding_model,
        similarity_threshold=args.regroup_similarity_threshold,
        min_cluster_size=args.regroup_min_cluster_size,
        unitization_mode=args.regroup_unitization_mode,
        trace_path=args.trace_path,
    )
    groups = regrouper.regroup(window_id, items)

    trace_events = []
    trace_path = Path(args.trace_path)
    if trace_path.exists():
        trace_events = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    timing_seconds = trace_events[-1].get("timing_seconds", {}) if trace_events else {}
    payload = {
        "source": args.source,
        "embedding_model": args.embedding_model,
        "chunk_size": args.chunk_size,
        "recent_token_budget": args.recent_token_budget,
        "regroup_unitization_mode": args.regroup_unitization_mode,
        "window_id": window_id,
        "selected_chunk_ids": selected_chunks,
        "window_total_tokens": total_tokens,
        "window_item_count": len(items),
        "groups_count": len(groups),
        "group_unit_counts": [len(group.unit_indices) for group in groups],
        "group_sentence_counts": [len(group.unit_indices) for group in groups],
        "timing_seconds": timing_seconds,
    }
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
