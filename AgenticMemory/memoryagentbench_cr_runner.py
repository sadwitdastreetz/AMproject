import argparse
import json
import os
import sys
from pathlib import Path

from datasets import load_dataset

from memory_layer import DEFAULT_EMBEDDING_MODEL
from memory_layer_robust import RobustAgenticMemorySystem, RobustLLMController
from test_advanced_robust import parse_plain_text_answer


BENCH_ROOT = Path(__file__).resolve().parent.parent / "MemoryAgentBench"
BENCH_UTILS = BENCH_ROOT / "utils"
for path in (BENCH_ROOT, BENCH_UTILS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from eval_other_utils import calculate_metrics, chunk_text_into_sentences, parse_output
from templates import get_template


class AMemConflictResolutionAgent:
    def __init__(self, model: str, backend: str, retrieve_k: int, trace_path: str | None = None):
        self.memory_system = RobustAgenticMemorySystem(
            model_name=DEFAULT_EMBEDDING_MODEL,
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
        self.memorize_template = get_template("factconsolidation_sh_6k", "memorize", "Agentic_memory")
        self.query_template = get_template("factconsolidation_sh_6k", "query", "Agentic_memory")

    def ingest_chunks(self, context: str, chunk_size: int):
        chunks = chunk_text_into_sentences(context, chunk_size=chunk_size)
        for chunk_idx, chunk in enumerate(chunks):
            # Align memory construction with the official benchmark:
            # each chunk is framed as a memorization dialogue turn before
            # being written into the agent's memory system.
            formatted_chunk = self.memorize_template.format(
                context=chunk,
                time_stamp=f"chunk_{chunk_idx:04d}",
            )
            self.memory_system.add_note(
                formatted_chunk,
                time=f"chunk_{chunk_idx:04d}",
            )
        return chunks

    def generate_query_terms(self, question: str) -> str:
        prompt = f"""Given the following question, generate several keywords separated by commas.

Question: {question}

Keywords:"""
        response = self.retriever_llm.llm.get_completion(prompt)
        return response.strip() or question

    def answer(self, question: str):
        query_terms = self.generate_query_terms(question)
        raw_context, _ = self.memory_system.find_related_memories(query_terms, k=self.retrieve_k)
        user_prompt = self.query_template.format(question=question)
        full_prompt = f"{user_prompt}\n\nRelevant Archival Memory:\n{raw_context}"
        response = self.answer_llm.llm.get_completion(full_prompt)
        return response, raw_context, query_terms, full_prompt


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
    parser.add_argument("--chunk-size", type=int, default=4096)
    parser.add_argument("--retrieve-k", type=int, default=10)
    parser.add_argument("--max-questions", type=int, default=10)
    parser.add_argument("--output", default="memoryagentbench_cr_results.json")
    parser.add_argument("--trace-path", default=None)
    args = parser.parse_args()

    row = load_conflict_resolution_row(args.source)
    agent = AMemConflictResolutionAgent(
        model=args.model,
        backend=args.backend,
        retrieve_k=args.retrieve_k,
        trace_path=args.trace_path,
    )
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
        prediction, raw_context, query_terms, full_prompt = agent.answer(question)
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
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "backend": args.backend,
        "model": args.model,
        "chunk_size": args.chunk_size,
        "retrieve_k": args.retrieve_k,
        "chunks_ingested": len(chunks),
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
    for metric_name, metric_value in summary.items():
        print(f"{metric_name}: {metric_value:.4f}")


if __name__ == "__main__":
    main()
