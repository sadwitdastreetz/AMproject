# AMproject

This repository is a research workspace for studying `agent memory systems`, with a current focus on:

- understanding `A-Mem`,
- reproducing benchmark behavior on [MemoryAgentBench](https://github.com/HUST-AI-HYZ/MemoryAgentBench),
- analyzing `selective forgetting / conflict resolution`,
- preparing a stronger next-step memory design grounded in experiments rather than intuition alone.

The current state of the project is research-heavy rather than implementation-heavy: we have already completed substantial benchmark exploration, logging, and failure analysis, while the long-term memory-core redesign is intentionally still open.

## Current Focus

The main question driving the latest work is:

> What does A-Mem get right about memory organization, and where does it break down on selective forgetting, especially under conflict and multi-hop conditions?

To answer that, this workspace has been used to:

- read and analyze the A-Mem paper and code,
- run A-Mem on `MemoryAgentBench/Conflict_Resolution`,
- compare `single-hop` and `multi-hop` behavior,
- switch the baseline model to `gpt-5.4-mini`,
- add structured memory-update traces,
- inspect retrieval logs and final prompts case by case,
- document the resulting findings in `docs/`.

## What We Have Established

From the experiments so far, the strongest working conclusion is:

> A-Mem is strong at `semantic organization`, but weak at `stateful conflict resolution`.

More concretely, the experiments suggest that A-Mem currently struggles because it does not explicitly maintain:

- current-vs-outdated fact state,
- conflict-aware overwrite logic,
- time-aware conflict arbitration,
- executable multi-hop state chains.

This does **not** make A-Mem unhelpful. On the contrary, it remains a strong inspiration source, especially for:

- note-centered memory representation,
- local semantic evolution,
- linked memory neighborhoods,
- agent-facing memory organization.

## Repository Status

This repository currently serves as a **research archive + experimentation workspace**.

It now contains:

- A-Mem-related experiment logs and reports in `docs/`,
- local benchmark and reference repositories for analysis,
- light project scaffolding under `src/`,
- a paused but well-documented foundation for the next design phase.

At the moment, the repository is **not yet** a finalized implementation of a new general memory system. It is the evidence base and working area that will support that implementation.

## Key Documents

If you are resuming work, start here:

- [A-Mem Session Index](/C:/Users/ddger/Documents/AMproject/docs/amem_session_index.md)
- [A-Mem Experiments Log](/C:/Users/ddger/Documents/AMproject/docs/amem_experiments_log.md)
- [A-Mem Key Decisions](/C:/Users/ddger/Documents/AMproject/docs/amem_key_decisions.md)
- [A-Mem Code Changes](/C:/Users/ddger/Documents/AMproject/docs/amem_code_changes.md)
- [A-Mem Findings And Lessons](/C:/Users/ddger/Documents/AMproject/docs/amem_findings_and_lessons.md)
- [A-Mem Risks And Next Steps](/C:/Users/ddger/Documents/AMproject/docs/amem_risks_and_next_steps.md)
- [A-Mem Selective Forgetting Experiment Report](/C:/Users/ddger/Documents/AMproject/docs/amem_selective_forgetting_experiment_report.md)

## Workspace Layout

```text
docs/
  amem_session_index.md
  amem_experiments_log.md
  amem_key_decisions.md
  amem_code_changes.md
  amem_findings_and_lessons.md
  amem_risks_and_next_steps.md
  amem_selective_forgetting_experiment_report.md

AgenticMemory/
  A-Mem benchmark-oriented research code

A-mem-sys/
  A-Mem production-style system code

MemoryAgentBench_official/
  official benchmark repository for alignment and inspection

src/
  memory_agent/
```

## Practical Notes

- The benchmark work here has used `MemoryAgentBench` as the main validation environment.
- For recent runs, the baseline LLM was switched to `gpt-5.4-mini`.
- Embedding paths were adapted to use OpenAI embeddings in the local experimentation flow.
- Structured trace logging was added around A-Mem memory updates to support failure analysis.

## Near-Term Direction

The project is currently paused at a good stopping point.

When work resumes, the most natural next steps are:

1. tighten benchmark alignment where needed,
2. formalize the A-Mem failure taxonomy,
3. design the smallest conflict-aware extension that improves selective forgetting,
4. only then begin a more committed memory-core implementation.

## Summary

This repository is no longer just an architecture sketch, and not yet a finished memory framework.

It is now the documented bridge between:

- initial architectural intuition,
- A-Mem code and paper analysis,
- selective forgetting benchmark evidence,
- and the next generation of memory-system design work.

