# Selective Forgetting for Memory Agents

This repository is a research starter kit for improving selective forgetting in memory agents, with a primary focus on the `Conflict_Resolution` split of [MemoryAgentBench](https://huggingface.co/datasets/ai-hyz/MemoryAgentBench).

The core hypothesis is that current memory agents fail not only because they retrieve the wrong evidence, but because they do not maintain an explicit, queryable model of:

- fact versions,
- contradiction links,
- update provenance,
- dependency chains needed for multi-hop conflict resolution.

We therefore propose a modular memory architecture centered on `versioned memory`, `targeted forgetting`, and `conflict-aware reasoning`.

## Research Goal

Build and evaluate a memory mechanism that improves:

- selective forgetting of outdated facts,
- consistency after updates,
- multi-hop conflict resolution accuracy,
- interpretability through explicit memory state transitions.

## Benchmark Focus

- Dataset: `ai-hyz/MemoryAgentBench`
- Main split: `Conflict_Resolution`
- Initial target: outperform strong retrieval and memory baselines on multi-hop conflict cases while preserving single-hop performance.

## Repository Layout

```text
docs/
  research_blueprint.md
  experiment_plan.md
src/
  memory_agent/
    config.py
    schemas.py
    memory_manager.py
    reasoning.py
    pipeline.py
    forgetting/
      selective_forgetting.py
    conflict/
      resolver.py
    storage/
      memory_store.py
    benchmarks/
      memory_agent_bench.py
configs/
  base.yaml
scripts/
  run_mab_conflict.py
tests/
  test_selective_forgetting.py
```

## Quick Start

1. Create an environment and install your preferred LLM, vector DB, and experiment tooling.
2. Read [docs/research_blueprint.md](/C:/Users/ddger/Documents/AMproject/docs/research_blueprint.md).
3. Start from [scripts/run_mab_conflict.py](/C:/Users/ddger/Documents/AMproject/scripts/run_mab_conflict.py).
4. Replace placeholder heuristics with your first train-free or LLM-assisted implementation.

## MVP Roadmap

1. Load `Conflict_Resolution` samples from MemoryAgentBench.
2. Convert each incoming chunk into candidate facts and entities.
3. Detect whether a new fact supports, updates, or contradicts an existing fact.
4. Mark stale facts as superseded instead of deleting them blindly.
5. Answer queries using only active facts plus contradiction-aware reasoning traces.
6. Run ablations on forgetting policy, conflict detection, and hop-aware retrieval.

## Research Positioning

This codebase is designed to support:

- reproducible experiments,
- paper-friendly modular ablations,
- error analysis,
- future extensions to long-range memory and continual learning.
