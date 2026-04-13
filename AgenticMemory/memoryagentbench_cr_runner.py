import argparse
import json
import os
import sys
from pathlib import Path

from datasets import load_dataset

from memory_layer import DEFAULT_EMBEDDING_MODEL
from memory_layer_robust import RobustAgenticMemorySystem, RobustLLMController
from memory_unit_decomposer import MemoryUnitDecomposer
from memory_window_buffers import MemoryUnitPingPongBuffer, RawMemoryTurnWindowBuffer
from short_term_memory import ShortTermMemoryBuffer
from test_advanced_robust import parse_plain_text_answer
from topic_regrouper import TopicRegrouper


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCH_ROOT = PROJECT_ROOT / "MemoryAgentBench"
if not BENCH_ROOT.exists():
    BENCH_ROOT = Path(r"C:\Users\ddger\Documents\AMproject\MemoryAgentBench")
BENCH_UTILS = BENCH_ROOT / "utils"
for path in (BENCH_ROOT, BENCH_UTILS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from eval_other_utils import calculate_metrics, chunk_text_into_sentences, parse_output
from templates import get_template


class AMemConflictResolutionAgent:
    def __init__(
        self,
        model: str,
        backend: str,
        retrieve_k: int,
        embedding_model: str,
        trace_path: str | None = None,
        recent_trace_path: str | None = None,
        group_trace_path: str | None = None,
        unit_trace_path: str | None = None,
        window_trace_path: str | None = None,
        recent_token_budget: int = 4096,
        raw_window_size: int = 40,
        raw_window_token_budget: int = 4096,
        raw_window_overlap_size: int = 2,
        memory_unit_token_budget: int = 4096,
        recent_k: int = 5,
        enable_topic_regrouping: bool = False,
        regroup_similarity_threshold: float = 0.42,
        regroup_min_cluster_size: int = 2,
    ):
        self.memory_system = RobustAgenticMemorySystem(
            model_name=embedding_model,
            llm_backend=backend,
            llm_model=model,
            update_trace_path=trace_path,
        )
        self.retriever_llm = RobustLLMController(
            backend=backend,
            model=model,
            api_key=None,
        )
        self.answer_llm = self.memory_system.llm_controller
        self.retrieve_k = retrieve_k
        self.recent_k = recent_k
        self.memorize_template = get_template("factconsolidation_sh_6k", "memorize", "Agentic_memory")
        self.query_template = get_template("factconsolidation_sh_6k", "query", "Agentic_memory")
        self.recent_memory = ShortTermMemoryBuffer(
            token_budget=recent_token_budget,
            embedding_model=embedding_model,
            trace_path=recent_trace_path,
        )
        self.raw_turn_window = RawMemoryTurnWindowBuffer(
            window_size=raw_window_size,
            token_budget=raw_window_token_budget,
            overlap_size=raw_window_overlap_size,
            trace_path=window_trace_path,
        )
        self.memory_unit_buffer = MemoryUnitPingPongBuffer(
            token_budget=memory_unit_token_budget,
            trace_path=window_trace_path,
        )
        self.enable_topic_regrouping = enable_topic_regrouping
        self.topic_regrouper = TopicRegrouper(
            embedding_model=embedding_model,
            similarity_threshold=regroup_similarity_threshold,
            min_cluster_size=regroup_min_cluster_size,
            trace_path=group_trace_path,
        )
        self.memory_unit_decomposer = MemoryUnitDecomposer(
            llm_controller=self.retriever_llm,
            trace_path=unit_trace_path,
        )
        self.embedding_model = embedding_model
        self.source_name = ""
        self.archived_chunk_ids: list[str] = []
        self.flush_history: list[dict] = []
        self.raw_window_history: list[dict] = []

    def _format_chunk(self, chunk_text: str, chunk_id: str) -> str:
        return self.memorize_template.format(
            context=chunk_text,
            time_stamp=chunk_id,
        )

    def _archive_raw_chunk(self, chunk_id: str, raw_chunk: str):
        formatted_chunk = self._format_chunk(raw_chunk, chunk_id)
        self.memory_system.add_note(formatted_chunk, time=chunk_id)
        self.archived_chunk_ids.append(chunk_id)

    def _archive_topic_groups(self, window_id: str, groups):
        for group in groups:
            formatted_chunk = self._format_chunk(group.text, group.topic_id)
            self.memory_system.add_note(formatted_chunk, time=group.topic_id)
            self.archived_chunk_ids.append(group.topic_id)

    def _archive_memory_unit_window(self, window_id: str, memory_units):
        if not memory_units:
            return
        flush_record = {
            "window_id": window_id,
            "source_turn_ids": sorted({turn_id for unit in memory_units for turn_id in unit.source_turn_ids}),
            "source_chunk_ids": sorted({turn_id for unit in memory_units for turn_id in unit.source_turn_ids}),
            "flushed_tokens": sum(self.memory_unit_buffer.token_counter.count(unit.content) for unit in memory_units),
            "region_size": self.memory_unit_buffer.region_size,
            "active_region_after_flush": self.memory_unit_buffer.active_region,
            "region_tokens_after_flush": list(self.memory_unit_buffer.region_tokens),
            "retained_memory_unit_ids": [unit.unit_id for unit in self.memory_unit_buffer.units],
            "retained_buffer_tokens": self.memory_unit_buffer.total_tokens,
            "mode": "topic_regrouping" if self.enable_topic_regrouping else "memory_unit_archive",
            "topic_ids": [],
            "memory_unit_ids": [unit.unit_id for unit in memory_units],
            "memory_unit_count": len(memory_units),
        }
        if self.enable_topic_regrouping:
            groups = self.topic_regrouper.regroup_units(window_id, memory_units)
            if groups:
                self._archive_topic_groups(window_id, groups)
                flush_record["topic_ids"] = [group.topic_id for group in groups]
        else:
            for unit in memory_units:
                self._archive_raw_chunk(unit.unit_id, unit.content)
        self.flush_history.append(flush_record)

    def _flush_memory_unit_window(self):
        window_id, memory_units = self.memory_unit_buffer.flush_window()
        self._archive_memory_unit_window(window_id, memory_units)

    def _process_raw_turn_windows(self):
        while self.raw_turn_window.should_process():
            raw_window = self.raw_turn_window.pop_window()
            memory_units = self.memory_unit_decomposer.decompose_window(
                window_id=raw_window.window_id,
                turns=raw_window.turns,
            )
            self.raw_window_history.append(
                {
                    "window_id": raw_window.window_id,
                    "source_turn_ids": [turn.turn_id for turn in raw_window.turns],
                    "window_turn_count": len(raw_window.turns),
                    "window_token_count": raw_window.token_count,
                    "memory_unit_ids": [unit.unit_id for unit in memory_units],
                    "memory_unit_count": len(memory_units),
                }
            )
            self.memory_unit_buffer.add_units(memory_units)
            while self.memory_unit_buffer.should_flush():
                self._flush_memory_unit_window()

    def _process_remaining_windows(self):
        if self.raw_turn_window.turns:
            raw_window = self.raw_turn_window.pop_remaining()
            memory_units = self.memory_unit_decomposer.decompose_window(
                window_id=raw_window.window_id,
                turns=raw_window.turns,
            )
            self.raw_window_history.append(
                {
                    "window_id": raw_window.window_id,
                    "source_turn_ids": [turn.turn_id for turn in raw_window.turns],
                    "window_turn_count": len(raw_window.turns),
                    "window_token_count": raw_window.token_count,
                    "memory_unit_ids": [unit.unit_id for unit in memory_units],
                    "memory_unit_count": len(memory_units),
                    "remaining": True,
                }
            )
            self.memory_unit_buffer.add_units(memory_units)
        window_id, memory_units = self.memory_unit_buffer.flush_remaining()
        self._archive_memory_unit_window(window_id, memory_units)

    def ingest_chunks(self, context: str, chunk_size: int):
        chunks = chunk_text_into_sentences(context, chunk_size=chunk_size)
        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"chunk_{chunk_idx:04d}"
            formatted_chunk = self._format_chunk(chunk, chunk_id)
            turn = self.recent_memory.add_turn(
                turn_id=chunk_id,
                raw_context=chunk,
                formatted_turn=formatted_chunk,
                source=self.source_name or "Conflict_Resolution",
                timestamp=chunk_id,
            )
            if self.recent_memory.should_flush():
                self.recent_memory.flush_window()
            self.raw_turn_window.add_turn(turn)
            self._process_raw_turn_windows()
        self._process_remaining_windows()
        return chunks

    def generate_query_terms(self, question: str) -> str:
        prompt = f"""Given the following question, generate several keywords separated by commas.

Question: {question}

Keywords:"""
        response = self.retriever_llm.llm.get_completion(prompt)
        return response.strip() or question

    def answer(self, question: str):
        query_terms = self.generate_query_terms(question)
        recent_turns = self.recent_memory.retrieve(query_terms, k=self.recent_k)
        recent_context = self.recent_memory.format_for_prompt(recent_turns)
        raw_context, _ = self.memory_system.find_related_memories(query_terms, k=self.retrieve_k)
        user_prompt = self.query_template.format(question=question)
        priority_instruction = (
            "Use the Recent Memory section as the primary source of truth. "
            "If Recent Memory and Archival Memory conflict, prefer the newer fact from Recent Memory. "
            "If Recent Memory is insufficient, then use Archival Memory. "
            "Do not use real-world knowledge outside the provided memory."
        )
        full_prompt = (
            f"{user_prompt}\n\n"
            f"{priority_instruction}\n\n"
            f"Recent Memory:\n{recent_context}\n\n"
            f"Archival Memory:\n{raw_context}"
        )
        response = self.answer_llm.llm.get_completion(full_prompt)
        return response, recent_context, raw_context, query_terms, full_prompt


def evaluate_predictions(prediction: str, answers):
    parsed = parse_output(prediction) or parse_plain_text_answer(prediction)
    raw_metrics = calculate_metrics(prediction, answers)
    parsed_metrics = calculate_metrics(parsed, answers) if parsed else raw_metrics
    merged_metrics = {
        key: max(raw_metrics.get(key, 0), parsed_metrics.get(key, 0))
        for key in raw_metrics.keys()
    }
    return parsed, merged_metrics


def load_conflict_resolution_row(source_name: str):
    dataset = load_dataset("ai-hyz/MemoryAgentBench", split="Conflict_Resolution")
    for row in dataset:
        if row.get("metadata", {}).get("source") == source_name:
            return row
    raise ValueError(f"Could not find source '{source_name}' in Conflict_Resolution split.")


def main():
    parser = argparse.ArgumentParser(description="Run A-Mem on MemoryAgentBench Conflict_Resolution.")
    parser.add_argument("--source", default="factconsolidation_sh_6k")
    parser.add_argument("--backend", default="openai")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    )
    parser.add_argument("--chunk-size", type=int, default=4096)
    parser.add_argument("--retrieve-k", type=int, default=10)
    parser.add_argument("--max-questions", type=int, default=10)
    parser.add_argument("--output", default="memoryagentbench_cr_results.json")
    parser.add_argument("--trace-path", default=None)
    parser.add_argument("--recent-trace-path", default=None)
    parser.add_argument("--group-trace-path", default=None)
    parser.add_argument("--unit-trace-path", default=None)
    parser.add_argument("--window-trace-path", default=None)
    parser.add_argument("--recent-token-budget", type=int, default=4096)
    parser.add_argument("--raw-window-size", type=int, default=40)
    parser.add_argument("--raw-window-token-budget", type=int, default=4096)
    parser.add_argument("--raw-window-overlap-size", type=int, default=2)
    parser.add_argument("--memory-unit-token-budget", type=int, default=4096)
    parser.add_argument("--recent-k", type=int, default=5)
    parser.add_argument("--enable-topic-regrouping", action="store_true")
    parser.add_argument("--regroup-similarity-threshold", type=float, default=0.42)
    parser.add_argument("--regroup-min-cluster-size", type=int, default=2)
    args = parser.parse_args()

    row = load_conflict_resolution_row(args.source)
    agent = AMemConflictResolutionAgent(
        model=args.model,
        backend=args.backend,
        retrieve_k=args.retrieve_k,
        embedding_model=args.embedding_model,
        trace_path=args.trace_path,
        recent_trace_path=args.recent_trace_path,
        group_trace_path=args.group_trace_path,
        unit_trace_path=args.unit_trace_path,
        window_trace_path=args.window_trace_path,
        recent_token_budget=args.recent_token_budget,
        raw_window_size=args.raw_window_size,
        raw_window_token_budget=args.raw_window_token_budget,
        raw_window_overlap_size=args.raw_window_overlap_size,
        memory_unit_token_budget=args.memory_unit_token_budget,
        recent_k=args.recent_k,
        enable_topic_regrouping=args.enable_topic_regrouping,
        regroup_similarity_threshold=args.regroup_similarity_threshold,
        regroup_min_cluster_size=args.regroup_min_cluster_size,
    )
    agent.source_name = args.source
    chunks = agent.ingest_chunks(row["context"], chunk_size=args.chunk_size)

    results = []
    metric_totals = {}
    for idx, (question, answers, qa_pair_id) in enumerate(
        zip(
            row["questions"][: args.max_questions],
            row["answers"][: args.max_questions],
            row["metadata"].get("qa_pair_ids", [])[: args.max_questions],
        )
    ):
        prediction, recent_context, raw_context, query_terms, full_prompt = agent.answer(question)
        parsed_prediction, metrics = evaluate_predictions(prediction, answers)
        for key, value in metrics.items():
            metric_totals.setdefault(key, []).append(float(value))

        results.append(
            {
                "index": idx,
                "qa_pair_id": qa_pair_id,
                "question": question,
                "answers": answers,
                "prediction_raw": prediction,
                "prediction_parsed": parsed_prediction,
                "query_terms": query_terms,
                "recent_context": recent_context,
                "raw_context": raw_context,
                "metrics": metrics,
                "prompt": full_prompt,
            }
        )

    summary = {
        key: (sum(values) / len(values) if values else 0.0)
        for key, values in metric_totals.items()
    }
    payload = {
        "source": args.source,
        "embedding_model": agent.embedding_model,
        "backend": args.backend,
        "model": args.model,
        "chunk_size": args.chunk_size,
        "retrieve_k": args.retrieve_k,
        "recent_k": args.recent_k,
        "recent_token_budget": args.recent_token_budget,
        "recent_region_size": agent.recent_memory.region_size,
        "raw_window_size": args.raw_window_size,
        "raw_window_token_budget": args.raw_window_token_budget,
        "raw_window_overlap_size": args.raw_window_overlap_size,
        "memory_unit_token_budget": args.memory_unit_token_budget,
        "memory_unit_region_size": agent.memory_unit_buffer.region_size,
        "topic_regrouping_enabled": args.enable_topic_regrouping,
        "trace_path": args.trace_path,
        "recent_trace_path": args.recent_trace_path,
        "group_trace_path": args.group_trace_path,
        "unit_trace_path": args.unit_trace_path,
        "window_trace_path": args.window_trace_path,
        "chunks_ingested": len(chunks),
        "archived_units": len(agent.archived_chunk_ids),
        "archived_ids": agent.archived_chunk_ids,
        "raw_window_history": agent.raw_window_history,
        "flush_history": agent.flush_history,
        "recent_buffer_size": len(agent.recent_memory.turns),
        "recent_buffer_tokens": agent.recent_memory.total_tokens,
        "raw_turn_window_buffer_size": len(agent.raw_turn_window.turns),
        "raw_turn_window_buffer_tokens": agent.raw_turn_window.token_count,
        "memory_unit_buffer_size": len(agent.memory_unit_buffer.units),
        "memory_unit_buffer_tokens": agent.memory_unit_buffer.total_tokens,
        "max_questions": args.max_questions,
        "summary": summary,
        "results": results,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved results to {output_path.resolve()}")
    print(f"Source: {args.source}")
    print(f"Chunks ingested: {len(chunks)}")
    print(f"Questions evaluated: {len(results)}")
    if args.trace_path:
        print(f"Trace log: {Path(args.trace_path).resolve()}")
    if args.recent_trace_path:
        print(f"Recent trace log: {Path(args.recent_trace_path).resolve()}")
    if args.group_trace_path:
        print(f"Group trace log: {Path(args.group_trace_path).resolve()}")
    if args.unit_trace_path:
        print(f"Unit trace log: {Path(args.unit_trace_path).resolve()}")
    if args.window_trace_path:
        print(f"Window trace log: {Path(args.window_trace_path).resolve()}")
    for metric_name, metric_value in summary.items():
        print(f"{metric_name}: {metric_value:.4f}")


if __name__ == "__main__":
    main()
