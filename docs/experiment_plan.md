# Experiment Plan

## Objective

Validate whether conflict-aware selective forgetting improves `Conflict_Resolution` performance on MemoryAgentBench, with special attention to multi-hop cases.

## Phase 1: Benchmark Wiring

- Load `Conflict_Resolution` split.
- Normalize each sample into an incremental interaction stream.
- Save intermediate memory states per turn for debugging.

## Phase 2: Baselines

- `full_context`: answer from all history.
- `flat_memory`: extracted fact list with semantic retrieval.
- `active_memory`: same fact list but filtered by supersession status.

## Phase 3: Proposed Method

- `cavf_v1`: versioned facts + contradiction detection + soft forgetting.
- `cavf_v2`: add dependency-aware invalidation.
- `cavf_v3`: add two-stage conflict-aware reasoning.

## Metrics

- accuracy,
- multi-hop accuracy,
- stale fact retrieval rate,
- conflict detection F1,
- average retrieved evidence count,
- latency per sample.

## Logging

Log for every question:

- retrieved fact ids,
- active vs superseded counts,
- contradiction decisions,
- final reasoning path,
- gold answer,
- predicted answer.

## Early Success Criteria

- improved multi-hop CR accuracy over flat memory baseline,
- reduced stale retrieval rate,
- interpretable resolution traces.
