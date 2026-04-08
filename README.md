# General Agent Memory System

This repository is a research codebase for building a `general Agent Memory System` with `selective forgetting` as a core memory evolution capability.

The project is not aimed at solving a single benchmark in isolation. Instead, it treats benchmarks such as [MemoryAgentBench](https://huggingface.co/datasets/ai-hyz/MemoryAgentBench) as validation environments for a reusable memory core that can later support broader long-horizon settings such as `LoCoMo`.

## Project Goal

Build a modular memory framework that can:

- ingest heterogeneous observations,
- parse them into reusable memory candidates,
- evolve memory state when new evidence arrives,
- selectively forget through state transition rather than deletion,
- expose both `history` and `active state` views,
- support benchmark adapters without letting benchmarks define the core abstraction.

## Current Position

The repository currently centers on:

- architecture documentation,
- research planning,
- implementation work orders for a clean rebuild.

The main implementation direction is the `general Agent Memory System` described in the architecture docs.
Legacy benchmark-oriented code has been removed from the mainline so future implementation threads start from the right abstraction.

## Key Documents

- [research_blueprint.md](/C:/Users/ddger/Documents/AMproject/docs/research_blueprint.md)
- [general_agent_memory_architecture.md](/C:/Users/ddger/Documents/AMproject/docs/general_agent_memory_architecture.md)
- [v1_subagent_work_orders.md](/C:/Users/ddger/Documents/AMproject/docs/v1_subagent_work_orders.md)
- [experiment_plan.md](/C:/Users/ddger/Documents/AMproject/docs/experiment_plan.md)

## Repository Layout

```text
docs/
  research_blueprint.md
  general_agent_memory_architecture.md
  v1_subagent_work_orders.md
  experiment_plan.md
scripts/
src/
  memory_agent/
    __init__.py
```

## Development Direction

The implementation roadmap now follows this principle:

- state changes happen primarily at ingest-time,
- context interpretation can happen at query-time,
- structural reorganization can happen in background or offline stages.

The online default is:

`Observation -> Candidate -> Related Memory -> Evolution Decision -> State Commit`

The architectural center is:

`outer generic MemoryItem + inner A-MEM-style Note`

## Research Positioning

This codebase is intended to support:

- reproducible memory-system experiments,
- architecture-first development,
- modular ablations,
- selective forgetting research,
- future migration from SDK-style research code to service-ready interfaces.
