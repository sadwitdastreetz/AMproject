import argparse
import json
from pathlib import Path

from load_dataset import load_locomo_dataset
from memory_layer import DEFAULT_EMBEDDING_MODEL
from test_advanced_robust import RobustAdvancedMemAgent, parse_plain_text_answer


def build_agent(model: str, backend: str, retrieve_k: int, temperature_c5: float):
    return RobustAdvancedMemAgent(
        model=model,
        backend=backend,
        retrieve_k=retrieve_k,
        temperature_c5=temperature_c5,
    )


def main():
    parser = argparse.ArgumentParser(description="Run a small, reproducible A-Mem LoCoMo smoke evaluation.")
    parser.add_argument("--dataset", default="data/locomo10.json")
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--sessions", type=int, default=1)
    parser.add_argument("--turns-per-session", type=int, default=3)
    parser.add_argument("--questions", type=int, default=3)
    parser.add_argument("--backend", default="openai")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--retrieve-k", type=int, default=5)
    parser.add_argument("--temperature-c5", type=float, default=0.5)
    parser.add_argument("--output", default="smoke_repro_results.json")
    args = parser.parse_args()

    samples = load_locomo_dataset(args.dataset)
    sample = samples[args.sample_index]
    agent = build_agent(args.model, args.backend, args.retrieve_k, args.temperature_c5)

    ingested_turns = []
    session_items = list(sample.conversation.sessions.items())[: args.sessions]
    for session_id, session in session_items:
        for turn in session.turns[: args.turns_per_session]:
            content = f"Speaker {turn.speaker}says : {turn.text}"
            agent.add_memory(content, time=session.date_time)
            ingested_turns.append(
                {
                    "session_id": session_id,
                    "date_time": session.date_time,
                    "speaker": turn.speaker,
                    "text": turn.text,
                }
            )

    results = []
    for qa in sample.qa[: args.questions]:
        prediction, prompt, raw_context = agent.answer_question(
            qa.question,
            qa.category,
            qa.final_answer,
        )
        prediction = parse_plain_text_answer(prediction)
        results.append(
            {
                "question": qa.question,
                "category": qa.category,
                "reference": qa.final_answer,
                "prediction": prediction,
                "raw_context": raw_context,
                "prompt": prompt,
            }
        )

    payload = {
        "dataset": args.dataset,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "backend": args.backend,
        "model": args.model,
        "sample_index": args.sample_index,
        "sessions_used": args.sessions,
        "turns_per_session": args.turns_per_session,
        "questions_answered": len(results),
        "ingested_turns": ingested_turns,
        "results": results,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved smoke reproduction results to {output_path.resolve()}")
    print(f"Embedding model: {DEFAULT_EMBEDDING_MODEL}")
    print(f"Ingested turns: {len(ingested_turns)}")
    for idx, item in enumerate(results, start=1):
        print(f"[Q{idx}] {item['question']}")
        print(f"  Reference: {item['reference']}")
        print(f"  Prediction: {item['prediction']}")


if __name__ == "__main__":
    main()
