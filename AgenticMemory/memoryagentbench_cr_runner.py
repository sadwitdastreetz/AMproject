import argparse
import json
import os
import sys
from datetime import datetime
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


def _write_trace_event(trace_path: str | None, event_type: str, payload: dict):
    if not trace_path:
        return
    path = Path(trace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now().isoformat(),
        "event": event_type,
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _trace_paths_from_args(args) -> dict:
    return {
        "amem_update_trace_path": args.trace_path,
        "recent_trace_path": args.recent_trace_path,
        "group_trace_path": args.group_trace_path,
        "unit_trace_path": args.unit_trace_path,
        "window_trace_path": args.window_trace_path,
    }


def _build_run_config(args, output_path: Path, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "source": args.source,
        "benchmark": "MemoryAgentBench/Conflict_Resolution",
        "agent": "A-Mem SimpleMem-window MemoryUnit pipeline",
        "memory_lifecycle": [
            "MemoryTurn",
            "RawMemoryTurnWindowBuffer",
            "MemoryUnitDecomposer",
            "MemoryUnitPingPongBuffer",
            "TopicRegrouper (main path; direct MemoryUnit archival is ablation/debug only)",
            "A-Mem Archival Memory",
            "Recent + Verbatim Source + Structured Working + Archival retrieval",
        ],
        "backend": args.backend,
        "model": args.model,
        "embedding_model": args.embedding_model,
        "openai_base_url": os.getenv("OPENAI_BASE_URL", ""),
        "chunk_size": args.chunk_size,
        "retrieve_k": args.retrieve_k,
        "recent_k": args.recent_k,
        "max_questions": args.max_questions,
        "recent_token_budget": args.recent_token_budget,
        "raw_window_size": args.raw_window_size,
        "raw_window_token_budget": args.raw_window_token_budget,
        "raw_window_overlap_size": args.raw_window_overlap_size,
        "memory_unit_token_budget": args.memory_unit_token_budget,
        "memory_unit_max_output_tokens": args.memory_unit_max_output_tokens,
        "memory_unit_repair_output_tokens": args.memory_unit_repair_output_tokens,
        "topic_regrouping_enabled": args.enable_topic_regrouping,
        "regroup_similarity_threshold": args.regroup_similarity_threshold,
        "regroup_min_cluster_size": args.regroup_min_cluster_size,
        "memorize_template_key": "factconsolidation_sh_6k/memorize/Agentic_memory",
        "query_template_key": "factconsolidation_sh_6k/query/Agentic_memory",
        "output_path": str(output_path),
        "trace_paths": _trace_paths_from_args(args),
    }


def _write_run_metadata_traces(run_config: dict):
    trace_paths = run_config["trace_paths"]
    for trace_name, trace_path in trace_paths.items():
        _write_trace_event(
            trace_path,
            "run_metadata",
            {
                "trace_name": trace_name,
                "run_id": run_config["run_id"],
                "run_config": run_config,
            },
        )


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
        memory_unit_max_output_tokens: int = 12000,
        memory_unit_repair_output_tokens: int = 12000,
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
            embedding_model=embedding_model,
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
            max_output_tokens=memory_unit_max_output_tokens,
            repair_max_output_tokens=memory_unit_repair_output_tokens,
        )
        self.embedding_model = embedding_model
        self.source_name = ""
        self.archived_chunk_ids: list[str] = []
        self.flush_history: list[dict] = []
        self.raw_window_history: list[dict] = []
        self.turn_store = {}
        self.memory_unit_store = {}
        self.archival_note_unit_ids = {}

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
            self.archival_note_unit_ids[group.topic_id] = list(group.memory_unit_ids)

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
                self.archival_note_unit_ids[unit.unit_id] = [unit.unit_id]
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
            self._store_memory_units(memory_units)
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

    def _process_remaining_raw_turn_window(self):
        if self.raw_turn_window.turns:
            raw_window = self.raw_turn_window.pop_remaining()
            memory_units = self.memory_unit_decomposer.decompose_window(
                window_id=raw_window.window_id,
                turns=raw_window.turns,
            )
            self._store_memory_units(memory_units)
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
            while self.memory_unit_buffer.should_flush():
                self._flush_memory_unit_window()

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
            self.turn_store[turn.turn_id] = turn
            if self.recent_memory.should_flush():
                self.recent_memory.flush_window()
            self.raw_turn_window.add_turn(turn)
            self._process_raw_turn_windows()
        self._process_remaining_raw_turn_window()
        return chunks

    def _store_memory_units(self, memory_units):
        for unit in memory_units:
            self.memory_unit_store[unit.unit_id] = unit

    def _format_verbatim_source_memory(self, source_turn_ids):
        ordered_turn_ids = []
        seen = set()
        for turn_id in source_turn_ids:
            if turn_id in seen:
                continue
            seen.add(turn_id)
            ordered_turn_ids.append(turn_id)
        if not ordered_turn_ids:
            return "No verbatim source memory required."

        blocks = []
        missing_turn_ids = []
        for turn_id in ordered_turn_ids:
            turn = self.turn_store.get(turn_id)
            if not turn:
                missing_turn_ids.append(turn_id)
                continue
            blocks.append(
                f"source turn id:{turn.turn_id}\n"
                f"source:{turn.source}\n"
                f"timestamp:{turn.timestamp}\n"
                f"verbatim content:\n{turn.formatted_turn}"
            )
        if missing_turn_ids:
            blocks.append(
                "Missing verbatim source turns:\n" + ", ".join(missing_turn_ids)
            )
        return "\n\n".join(blocks) if blocks else "No verbatim source memory available."

    def _verbatim_turn_ids_from_units(self, units):
        turn_ids = []
        seen = set()
        for unit in units:
            if unit.fidelity_mode != "verbatim_required":
                continue
            for turn_id in unit.source_turn_ids:
                if turn_id in seen:
                    continue
                seen.add(turn_id)
                turn_ids.append(turn_id)
        return turn_ids

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
        working_units = self.memory_unit_buffer.retrieve(query_terms, k=self.recent_k)
        working_unit_context = self.memory_unit_buffer.format_for_prompt(working_units)
        raw_context, archival_indices = self.memory_system.find_related_memories(query_terms, k=self.retrieve_k)
        all_archival_memories = list(self.memory_system.memories.values())
        archival_hits = []
        archival_units = []
        for memory_index in archival_indices:
            if 0 <= memory_index < len(all_archival_memories):
                memory = all_archival_memories[memory_index]
                memory_unit_ids = self.archival_note_unit_ids.get(memory.timestamp, [])
                hit_units = [
                    self.memory_unit_store[unit_id]
                    for unit_id in memory_unit_ids
                    if unit_id in self.memory_unit_store
                ]
                archival_units.extend(hit_units)
                archival_hits.append(
                    {
                        "index": memory_index,
                        "note_id": memory.id,
                        "timestamp": memory.timestamp,
                        "memory_unit_ids": memory_unit_ids,
                        "verbatim_required_unit_ids": [
                            unit.unit_id
                            for unit in hit_units
                            if unit.fidelity_mode == "verbatim_required"
                        ],
                        "content_preview": memory.content[:240],
                    }
                )
        verbatim_source_turn_ids = self._verbatim_turn_ids_from_units(working_units + archival_units)
        verbatim_source_context = self._format_verbatim_source_memory(verbatim_source_turn_ids)
        user_prompt = self.query_template.format(question=question)
        priority_instruction = (
            "Use the Recent Turn Memory section as the primary source of truth. "
            "Use Verbatim Source Memory whenever exact wording, order, symbols, formatting, code, logs, formulas, tables, or quoted text may matter. "
            "If Structured Working Memory says fidelity_mode=verbatim_required, treat it as an index and rely on Verbatim Source Memory for exact details. "
            "If Recent Turn Memory and Verbatim Source Memory are insufficient, use Structured Working Memory. "
            "If these recent/working layers are insufficient, use Archival Memory. "
            "If these memory layers conflict, prefer the newer/higher-priority layer in this order: "
            "Recent Turn Memory, then Verbatim Source Memory, then Structured Working Memory, then Archival Memory. "
            "Do not use real-world knowledge outside the provided memory."
        )
        full_prompt = (
            f"{user_prompt}\n\n"
            f"{priority_instruction}\n\n"
            f"Recent Turn Memory:\n{recent_context}\n\n"
            f"Verbatim Source Memory:\n{verbatim_source_context}\n\n"
            f"Structured Working Memory:\n{working_unit_context}\n\n"
            f"Archival Memory:\n{raw_context}"
        )
        response = self.answer_llm.llm.get_completion(full_prompt)
        retrieval_metadata = {
            "query_terms": query_terms,
            "recent_turn_hits": [
                {
                    "turn_id": turn.turn_id,
                    "source": turn.source,
                    "timestamp": turn.timestamp,
                    "token_count": turn.token_count,
                }
                for turn in recent_turns
            ],
            "working_unit_hits": [
                {
                    "unit_id": unit.unit_id,
                    "source_turn_ids": unit.source_turn_ids,
                    "timestamp": unit.timestamp,
                    "fidelity_mode": unit.fidelity_mode,
                    "topic": unit.topic,
                    "keywords": unit.keywords,
                }
                for unit in working_units
            ],
            "verbatim_source_turn_ids": verbatim_source_turn_ids,
            "verbatim_source_available": bool(verbatim_source_turn_ids),
            "verbatim_source_context": verbatim_source_context,
            "archival_hits": archival_hits,
        }
        return response, recent_context, verbatim_source_context, working_unit_context, raw_context, query_terms, full_prompt, retrieval_metadata


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
    parser.add_argument("--memory-unit-max-output-tokens", type=int, default=12000)
    parser.add_argument("--memory-unit-repair-output-tokens", type=int, default=12000)
    parser.add_argument("--recent-k", type=int, default=5)
    parser.add_argument("--enable-topic-regrouping", action="store_true")
    parser.add_argument("--regroup-similarity-threshold", type=float, default=0.42)
    parser.add_argument("--regroup-min-cluster-size", type=int, default=2)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(args.output)
    run_config = _build_run_config(args, output_path, run_id)
    _write_run_metadata_traces(run_config)

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
        memory_unit_max_output_tokens=args.memory_unit_max_output_tokens,
        memory_unit_repair_output_tokens=args.memory_unit_repair_output_tokens,
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
        prediction, recent_context, verbatim_source_context, working_unit_context, raw_context, query_terms, full_prompt, retrieval_metadata = agent.answer(question)
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
                "retrieval_metadata": retrieval_metadata,
                "recent_context": recent_context,
                "verbatim_source_context": verbatim_source_context,
                "working_unit_context": working_unit_context,
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
        "run_id": run_id,
        "run_config": run_config,
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
        "memory_unit_max_output_tokens": args.memory_unit_max_output_tokens,
        "memory_unit_repair_output_tokens": args.memory_unit_repair_output_tokens,
        "topic_regrouping_enabled": args.enable_topic_regrouping,
        "trace_path": args.trace_path,
        "recent_trace_path": args.recent_trace_path,
        "group_trace_path": args.group_trace_path,
        "unit_trace_path": args.unit_trace_path,
        "window_trace_path": args.window_trace_path,
        "trace_paths": _trace_paths_from_args(args),
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
        "storage_summary": {
            "chunks_ingested": len(chunks),
            "recent_turn_buffer_size": len(agent.recent_memory.turns),
            "recent_turn_buffer_tokens": agent.recent_memory.total_tokens,
            "raw_turn_window_buffer_size": len(agent.raw_turn_window.turns),
            "raw_turn_window_buffer_tokens": agent.raw_turn_window.token_count,
            "memory_unit_buffer_size": len(agent.memory_unit_buffer.units),
            "memory_unit_buffer_tokens": agent.memory_unit_buffer.total_tokens,
            "archival_note_count": len(agent.memory_system.memories),
            "archived_ids": agent.archived_chunk_ids,
            "flush_count": len(agent.flush_history),
            "turn_store_size": len(agent.turn_store),
            "memory_unit_store_size": len(agent.memory_unit_store),
            "archival_note_unit_map_size": len(agent.archival_note_unit_ids),
        },
        "max_questions": args.max_questions,
        "summary": summary,
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
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
