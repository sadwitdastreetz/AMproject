# Research Blueprint

## 1. Research Problem Definition

### Task Definition

We study `selective forgetting` for memory agents under `multi-hop conflict resolution`.

Given an incremental stream of user-provided information, the agent must:

1. store useful facts,
2. detect when new evidence updates or contradicts prior memory,
3. suppress outdated facts during downstream reasoning,
4. preserve the right dependency chain for answering multi-hop questions.

In the `Conflict_Resolution` setting, this is harder than ordinary retrieval because the correct answer often depends on:

- identifying which memory item is obsolete,
- tracing which downstream facts are affected by that change,
- recomputing the answer over the updated world state rather than the accumulated raw history.

### Problem Statement

Current memory systems mostly optimize `remembering` and `retrieving`, but selective forgetting requires `state maintenance under contradiction`.

The core research question is:

How can we build a memory agent that updates its internal world model in a structured, interpretable, and query-efficient way so that outdated facts are suppressed without destroying useful historical evidence?

### Research Hypothesis

Multi-hop conflict failures primarily arise because existing methods do not represent:

- fact versioning,
- contradiction edges,
- temporal/update priority,
- dependency-aware invalidation.

An explicit `versioned conflict graph` plus `targeted forgetting policy` should improve multi-hop conflict resolution substantially over flat memory stores and naive retrieval.

## 2. Core Challenges of Selective Forgetting

### What Makes Selective Forgetting Hard

- The agent must forget `the right memory`, not simply the oldest or least similar one.
- Contradictions are often implicit rather than lexical.
- A later update can invalidate several earlier inferences.
- Some historical facts should be inactive for answering but still preserved for provenance and audit.
- The agent must distinguish `fact replacement`, `fact refinement`, `context shift`, and `coexistence`.

### Why Multi-Hop Conflict Resolution Is Especially Difficult

- The answer often depends on chaining multiple facts, where one stale node corrupts the whole chain.
- Conflict may occur in one hop while the question targets another hop downstream.
- Standard retrievers surface both old and new evidence, forcing the language model to resolve contradictions on the fly.
- LLMs tend to average or merge conflicting evidence instead of committing to the latest valid state.
- Multi-hop questions require `memory update` and `reasoning update`; many systems only attempt one of the two.

## 3. Analysis of Existing Methods

### Memory-Based Methods

Representative style: fact extraction, summary memory, hierarchical memory, external memory stores.

Strengths:

- efficient storage,
- persistent cross-session memory,
- lower token cost than full-context prompting.

Failure modes:

- aggressive fact compression loses update context,
- stored memories are usually flat and not versioned,
- contradiction handling is weak or absent,
- retrieval frequently returns both active and obsolete memories.

Why they fail on CR:

- they optimize `salience` rather than `truth under change`,
- they treat memory records as additive,
- they rarely model supersession relations explicitly.

### RAG-Based Methods

Representative style: BM25, dense retrieval, graph retrieval, top-k evidence selection.

Strengths:

- strong precise lookup for stable facts,
- scalable and modular,
- easy to swap retrieval backends.

Failure modes:

- retrieval returns local evidence fragments rather than an updated world state,
- top-k expansion often increases contradiction exposure,
- similarity search is weak at “retrieve the latest valid fact replacing X”.

Why they fail on CR:

- retrieval alone cannot decide which evidence should be invalidated,
- multi-hop conflict resolution needs state revision, not only evidence recall.

### Long-Context Methods

Representative style: put all history into the prompt and let the model reason end to end.

Strengths:

- no lossy compression in principle,
- direct access to full conversational history.

Failure modes:

- compute cost grows with history,
- attention over long histories is noisy,
- models still struggle to consistently prioritize updated facts.

Why they fail on CR:

- the model sees both outdated and current facts simultaneously,
- longer context does not create explicit update semantics.

### Reasoning-Based Methods

Representative style: chain-of-thought, deliberate reasoning, iterative retrieval-reasoning loops.

Strengths:

- better local disambiguation,
- some improvement in multi-hop composition.

Failure modes:

- reasoning operates over whatever evidence was retrieved,
- if memory state is stale, better reasoning still starts from the wrong premises,
- repeated reasoning increases latency and cost.

Why they fail on CR:

- reasoning is asked to compensate for memory architecture deficiencies,
- it lacks a structured mechanism to deactivate stale facts before inference.

## 4. Why Existing Methods Fail

The benchmark suggests a common failure pattern across paradigms:

1. `Encoding failure`: the system stores incomplete or oversimplified facts.
2. `Update failure`: the system cannot decide whether a new fact replaces, refines, or coexists with an old one.
3. `Retrieval failure`: obsolete and current facts are retrieved together.
4. `Reasoning failure`: the model blends contradictions instead of enforcing one valid state.

This motivates a shift from `memory as searchable notes` to `memory as a maintained world model`.

## 5. Proposed Research Directions

### Direction A: Versioned Memory Graph

Store each fact as a node with:

- entity,
- relation,
- value,
- source span,
- timestamp or arrival order,
- confidence,
- status: `active`, `superseded`, `uncertain`,
- edges: `supports`, `contradicts`, `derived_from`, `supersedes`.

Expected benefit:

- explicit state tracking,
- easier pruning of stale evidence,
- interpretable error analysis.

### Direction B: Targeted Forgetting Instead of Hard Deletion

Selective forgetting should be implemented as `state transition`, not physical deletion.

Use:

- soft forgetting: suppress from normal retrieval,
- hard forgetting: remove only when storage budget requires it,
- provenance retention: keep inactive facts for audit and ablations.

Expected benefit:

- safer updates,
- easier rollback,
- better scientific interpretability.

### Direction C: Dependency-Aware Invalidation

When one fact is updated, propagate invalidation to derived facts or candidate reasoning paths.

Example:

- old employer changes,
- downstream office location or manager facts may need re-evaluation.

Expected benefit:

- better multi-hop consistency,
- fewer stale reasoning chains.

### Direction D: Conflict-Aware Retrieval

Retrieve by both semantic relevance and memory status:

- prioritize `active` facts,
- downweight `superseded` nodes,
- surface contradiction partners when confidence is low.

Expected benefit:

- cleaner evidence set,
- less burden on the generator.

### Direction E: Two-Stage Reasoning

Stage 1: resolve memory state.

Stage 2: answer the user query from the resolved state.

Expected benefit:

- separates “what is currently true” from “how to answer”.

## 6. System Architecture Design

### Memory Manager

Responsibilities:

- ingest incremental chunks,
- extract candidate facts,
- canonicalize entities and relations,
- write fact nodes to memory,
- attach provenance and timestamps.

Inputs:

- raw chunk,
- session metadata,
- existing memory state.

Outputs:

- updated memory graph,
- operation trace.

### Forgetting Module

Responsibilities:

- detect update and contradiction events,
- assign fact status,
- suppress stale memories from standard retrieval,
- propagate invalidation to dependent facts.

Policies:

- recency-aware,
- confidence-aware,
- relation-specific,
- budget-aware.

### Conflict Resolution Module

Responsibilities:

- compare new fact against stored candidates,
- classify relation as `support`, `refine`, `contradict`, `unknown`,
- create `supersedes` links when justified,
- request LLM adjudication only for ambiguous cases.

### Reasoning Module

Responsibilities:

- retrieve active evidence,
- trace multi-hop reasoning paths over the graph,
- verify that each hop uses active nodes,
- produce answer plus reasoning trace.

## 7. Technical Solution Design

### Proposed Selective Forgetting Mechanism

We propose `Conflict-Aware Versioned Forgetting (CAVF)`.

Pipeline:

1. Extract fact triples or structured claims from incoming chunk.
2. Match candidates to existing entity-relation slots.
3. Detect whether the new fact:
   - supports existing memory,
   - refines it,
   - contradicts it,
   - or introduces a parallel context.
4. If contradiction is detected, mark the previous fact `superseded`.
5. Propagate status changes to dependent derived facts.
6. Keep superseded facts in provenance memory but exclude them from active retrieval by default.

### Memory Update Policy

Per fact record:

- `activation_score`
- `supersession_score`
- `recency`
- `source_reliability`
- `dependency_count`
- `query_frequency`

Update rule:

- high-confidence contradiction from newer evidence triggers supersession,
- ambiguous contradiction triggers `uncertain` state and dual retrieval,
- high-value stable facts are never hard-deleted during MVP.

### Multi-Hop Conflict Processing Approach

For each query:

1. identify target entities and relations,
2. retrieve active subgraph,
3. if needed, include contradiction neighbors for adjudication,
4. run path search over valid graph edges,
5. reject paths containing superseded nodes,
6. generate answer from best active path.

Possible path scoring:

- relevance score,
- node status score,
- recency consistency,
- contradiction penalty,
- hop completeness.

## 8. Minimum Viable System (MVP)

### MVP Objective

Demonstrate that explicit versioning and supersession can beat naive memory retrieval on `Conflict_Resolution`, especially on multi-hop items.

### MVP Components

- chunk ingestor,
- simple fact extractor,
- memory store,
- contradiction detector,
- supersession marker,
- active-memory retriever,
- hop-aware answerer,
- experiment runner.

### Recommended MVP Strategy

Start with heuristic-plus-LLM hybrid logic:

- heuristics for entity/relation slot matching,
- LLM only for ambiguous contradiction classification,
- deterministic retrieval and path filtering.

This keeps the system paper-friendly and easier to ablate.

## 9. Project Directory Structure

```text
AMproject/
  README.md
  docs/
    research_blueprint.md
    experiment_plan.md
  configs/
    base.yaml
  scripts/
    run_mab_conflict.py
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
  tests/
    test_selective_forgetting.py
```

Design principles:

- paper-ready modularity,
- replaceable components,
- explicit traces for qualitative analysis,
- easy ablation through config switches.

## 10. First-Stage Experimental Design

### Main Benchmark Setup

Primary benchmark:

- `MemoryAgentBench`
- split: `Conflict_Resolution`

Primary metrics:

- single-hop accuracy,
- multi-hop accuracy,
- contradiction resolution precision,
- stale-memory retrieval rate,
- reasoning path validity.

### Baselines

At minimum compare against:

- no-memory or full-history prompting,
- simple vector or BM25 retrieval,
- flat fact memory without supersession,
- your proposed versioned conflict-aware memory.

### Core Ablations

1. Remove supersession edges.
2. Remove dependency invalidation.
3. Replace conflict-aware retrieval with vanilla top-k retrieval.
4. Replace two-stage reasoning with direct answer generation.
5. Hard-delete stale facts instead of soft-forgetting.

### Error Analysis Axes

- wrong contradiction detection,
- entity linking mismatch,
- stale fact leakage,
- correct update but broken multi-hop chain,
- reasoning failure despite correct memory state.

### First Publishable Claim

A realistic first paper claim is:

An explicit versioned memory representation with soft supersession improves selective forgetting and multi-hop conflict resolution over flat memory stores on MemoryAgentBench.

That claim is modest, testable, and extensible.

## 11. Paper-Framing Suggestions

Potential title direction:

`Conflict-Aware Versioned Memory for Selective Forgetting in LLM Agents`

Possible contributions:

1. formalization of selective forgetting as stateful conflict resolution,
2. a modular memory architecture with explicit supersession,
3. an evaluation protocol on MemoryAgentBench CR with ablations,
4. analysis of why retrieval-only memory fails under multi-hop contradictions.

## 12. Practical Next Steps

1. Implement the data loader and inspect all `Conflict_Resolution` examples.
2. Build a flat-memory baseline first.
3. Add versioned fact records and supersession links.
4. Add active-only retrieval.
5. Add dependency-aware invalidation.
6. Run ablations and collect failure cases for the eventual paper.
