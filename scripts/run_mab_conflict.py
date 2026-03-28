from memory_agent.benchmarks.memory_agent_bench import load_conflict_resolution_split


def main() -> None:
    split = load_conflict_resolution_split()
    print(f"Loaded Conflict_Resolution with {len(split)} samples.")
    print("Next step: convert each sample into incremental turns and wire the memory pipeline.")


if __name__ == "__main__":
    main()
