import argparse
import json
import os
import sys
import string
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import tiktoken
from openai import APIError, BadRequestError, OpenAI, RateLimitError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from memory_agent.benchmarks.memory_agent_bench import load_conflict_resolution_episodes
from memory_agent.schemas import BenchmarkEpisode


SYSTEM_MESSAGE = "You are a helpful assistant that can read the context and memorize it for future retrieval."
MEMORIZE_TEMPLATE = (
    "Dialogue between User and Assistant {time_stamp}\n"
    "<User> The following context is the facts I have learned:\n"
    "{context}\n"
    "<Assistant> I have learned the facts and I will answer the question you ask."
)
QUERY_TEMPLATE = (
    "Pretend you are a knowledge management system. Each fact in the knowledge pool is provided "
    "with a serial number at the beginning, and the newer fact has larger serial number.\n"
    "You need to solve the conflicts of facts in the knowledge pool by finding the newest fact with "
    "larger serial number. You need to answer a question based on this rule. You should give a very "
    "concise answer without saying other words for the question only from the knowledge pool you have "
    "memorized rather than the real facts in real world.\n\n"
    "For example:\n\n"
    "[Knowledge Pool]\n\n"
    "Question: Based on the provided Knowledge Pool, what is the name of the current president of Russia?\n"
    "Answer: Donald Trump\n\n"
    "Now Answer the Question: Based on the provided Knowledge Pool, {question}\n"
    "Answer:"
)


def normalize_text(text: str) -> str:
    lowered = text.lower()
    no_punc = "".join(ch for ch in lowered if ch not in string.punctuation)
    return " ".join(no_punc.split())


def is_correct(prediction: str, gold_answers: Iterable[str]) -> bool:
    pred = normalize_text(prediction)
    return any(pred == normalize_text(gold) for gold in gold_answers)


def get_encoding(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        return tiktoken.get_encoding("o200k_base")


def token_len(text: str, encoding) -> int:
    return len(encoding.encode(text))


def truncate_to_last_tokens(text: str, limit: int, encoding) -> str:
    tokens = encoding.encode(text)
    if len(tokens) <= limit:
        return text
    return encoding.decode(tokens[-limit:])


def chunk_fact_lines(context: str, chunk_size_tokens: int, encoding) -> list[str]:
    lines = context.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for line in lines:
        add_tokens = token_len(line + "\n", encoding)
        if current and current_tokens + add_tokens > chunk_size_tokens:
            chunks.append("\n".join(current))
            current = [line]
            current_tokens = add_tokens
        else:
            current.append(line)
            current_tokens += add_tokens
    if current:
        chunks.append("\n".join(current))
    return chunks


def parse_answer(raw_output: str) -> str:
    text = raw_output.strip()
    prefix = "answer:"
    if text.lower().startswith(prefix):
        text = text[len(prefix) :].strip()
    return text.splitlines()[0].strip() if text else ""


def run_episode(
    *,
    client: OpenAI,
    model: str,
    episode: BenchmarkEpisode,
    input_length_limit: int,
    buffer_length: int,
    max_output_tokens: int,
    temperature: float,
    reasoning_effort: str | None,
    chunk_size_tokens: int,
    max_questions: int,
) -> dict:
    encoding = get_encoding(model)
    memory_limit = input_length_limit - buffer_length - max_output_tokens
    if memory_limit <= 0:
        raise ValueError("memory_limit <= 0. Increase input_length_limit or reduce buffer/max_output_tokens.")

    def call_with_retry(kwargs: dict):
        delay = 1.0
        max_attempts = 8
        for attempt in range(1, max_attempts + 1):
            try:
                return client.chat.completions.create(**kwargs)
            except RateLimitError:
                if attempt == max_attempts:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 20.0)
            except APIError:
                if attempt == max_attempts:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 20.0)

    memory_context = ""
    for chunk in chunk_fact_lines(episode.raw_context, chunk_size_tokens, encoding):
        mem_msg = MEMORIZE_TEMPLATE.format(context=chunk, time_stamp=time.strftime("%Y-%m-%d %H:%M:%S"))
        memory_context = (memory_context + "\n" + mem_msg).strip()
        memory_context = truncate_to_last_tokens(memory_context, memory_limit, encoding)

    rows = []
    exact_match_flags = []
    for idx, query in enumerate(episode.query_turns[:max_questions]):
        query_msg = QUERY_TEMPLATE.format(question=query.question)
        full_message = memory_context + "\n" + query_msg
        start = time.time()
        request_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": full_message},
            ],
            "max_completion_tokens": max_output_tokens,
        }
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        if reasoning_effort:
            request_kwargs["reasoning_effort"] = reasoning_effort

        try:
            resp = call_with_retry(request_kwargs)
        except BadRequestError as err:
            # Some newer models only accept default temperature and reject explicit values.
            if "temperature" in str(err).lower() and "default (1)" in str(err).lower():
                request_kwargs.pop("temperature", None)
                resp = call_with_retry(request_kwargs)
            elif "reasoning_effort" in str(err).lower() and "unrecognized" in str(err).lower():
                request_kwargs.pop("reasoning_effort", None)
                resp = call_with_retry(request_kwargs)
            else:
                raise
        latency = time.time() - start
        raw_out = resp.choices[0].message.content or ""
        pred = parse_answer(raw_out)
        ok = is_correct(pred, query.gold_answers)
        exact_match_flags.append(ok)
        rows.append(
            {
                "episode_id": episode.episode_id,
                "difficulty": episode.difficulty,
                "context_size": episode.context_size,
                "query_index": idx,
                "qa_pair_id": query.qa_pair_id,
                "question": query.question,
                "gold_answers": query.gold_answers,
                "prediction": pred,
                "raw_output": raw_out,
                "exact_match": ok,
                "latency_sec": latency,
            }
        )

    return {
        "episode_id": episode.episode_id,
        "difficulty": episode.difficulty,
        "context_size": episode.context_size,
        "num_questions": len(rows),
        "exact_match": (sum(exact_match_flags) / len(exact_match_flags)) if exact_match_flags else 0.0,
        "rows": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate long-context FIFO baseline on MemoryAgentBench Conflict_Resolution.")
    parser.add_argument("--model", type=str, default="gpt-5")
    parser.add_argument("--sources", type=str, default="factconsolidation_mh_6k,factconsolidation_mh_32k")
    parser.add_argument("--max-questions", type=int, default=20)
    parser.add_argument("--chunk-size-tokens", type=int, default=4096)
    parser.add_argument("--input-length-limit", type=int, default=128000)
    parser.add_argument("--buffer-length", type=int, default=4000)
    parser.add_argument("--max-output-tokens", type=int, default=10)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--reasoning-effort", type=str, default="minimal")
    parser.add_argument("--output", type=str, default="outputs/long_context_eval.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    wanted_sources = {item.strip() for item in args.sources.split(",") if item.strip()}
    episodes = [ep for ep in load_conflict_resolution_episodes() if ep.source in wanted_sources]
    if not episodes:
        raise RuntimeError(f"No episodes found for sources: {sorted(wanted_sources)}")

    client = OpenAI(api_key=api_key)
    episode_results = []
    all_rows = []
    for episode in episodes:
        result = run_episode(
            client=client,
            model=args.model,
            episode=episode,
            input_length_limit=args.input_length_limit,
            buffer_length=args.buffer_length,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
            reasoning_effort=args.reasoning_effort,
            chunk_size_tokens=args.chunk_size_tokens,
            max_questions=args.max_questions,
        )
        episode_results.append({k: v for k, v in result.items() if k != "rows"})
        all_rows.extend(result["rows"])

    grouped = defaultdict(list)
    for item in episode_results:
        key = f"{item['difficulty']}::{item['context_size']}"
        grouped[key].append(item["exact_match"])
    group_metrics = {key: sum(values) / len(values) for key, values in grouped.items()}

    payload = {
        "config": vars(args),
        "episodes": episode_results,
        "group_metrics": group_metrics,
        "rows": all_rows,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Summary ===")
    for key, score in sorted(group_metrics.items()):
        print(f"{key}: {score:.4f}")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
