# A-Mem Code Changes

## 2026-04-13 - Add MemoryUnit semantic decomposition before regrouping

更新范围：

- `AgenticMemory/memory_unit_decomposer.py`
- `AgenticMemory/topic_regrouper.py`
- `AgenticMemory/memoryagentbench_cr_runner.py`

主要变更：

- 新增 `MemoryUnit` 与 `MemoryUnitDecomposer`
- 借鉴 SimpleMem 的 semantic structured compression / MemoryEntry 思想：一个 `MemoryTurn` 可生成多个 self-contained memory units
- CR runner 的 topic regrouping flush 路径改为：
  - `List[MemoryTurn]`
  - `MemoryUnitDecomposer.decompose(turn)`
  - `List[MemoryUnit]`
  - `TopicRegrouper.regroup_units(window_id, memory_units)`
  - grouped memory units 写入 A-Mem archival notes
- 新增 `--unit-trace-path`，记录 decomposition trace
- `TopicRegrouper` 新增 `regroup_units()`，聚类输入从 sentence/fact text 升级为 `MemoryUnit.content`
- group trace 新增 `memory_unit_ids`, `topics`, `entities`, `keywords`

设计含义：

- 当前不做 sliding window
- decomposition 单位是一个完整 `MemoryTurn`
- 解析失败返回空 memory unit list，并写 trace；不 silent fallback 到 sentence split
- 旧 `regroup()` 仍保留为 legacy path，但 CR runner 主路径已接入 `regroup_units()`

验证：

- `py_compile` 通过
- 离线 mock smoke test 通过：
  - 一个 `MemoryTurn` 可生成多个 `MemoryUnit`
  - 非法 JSON 返回空列表
  - `regroup_units()` 可将 `MemoryUnit` 聚成 `TopicGroup`
- CR runner help 已确认新增 `--unit-trace-path`

## 2026-04-13 - Remove unitization router and keep MemoryTurn ping-pong buffer

更新范围：

- `AgenticMemory/short_term_memory.py`
- `AgenticMemory/memoryagentbench_cr_runner.py`
- `AgenticMemory/topic_regrouper.py`
- `AgenticMemory/profile_topic_regrouping.py`
- `AgenticMemory/unitization_router.py`

主要变更：

- 删除临时试探性的 `AgenticMemory/unitization_router.py`
- 移除 `--regroup-unitization-mode`, `--unitization-router-preview-chars`, `--allow-unitization-router-fallback`
- 移除 `MemoryTurn.unitization_decision`
- 移除 runner / group trace 中的 `unitization_decision` 和 `unitization_mode`
- 保留 `MemoryTurn` 作为 short-term ping-pong buffer 的基本对象
- 保留 ingest 时立即生成官方 `formatted_turn`
- 保留 `ShortTermMemoryBuffer.regions: List[List[MemoryTurn]]`
- `TopicRegrouper` 暂时退回为 legacy CR regrouping：输入仍是 `List[MemoryTurn]`，但内部只对 `raw_context` 做本地 factual/sentence split

设计含义：

- 当前不再把 agentic unitization router 作为已确认方向
- 后续若推进 `MemoryTurn -> sliding window over turns -> List[MemoryUnit]`，应新建更清晰的 memory-unit decomposition 模块，而不是继续扩展旧的 `unitization_mode` 分支

验证：

- `py_compile` 通过：
  - `AgenticMemory/short_term_memory.py`
  - `AgenticMemory/topic_regrouper.py`
  - `AgenticMemory/memoryagentbench_cr_runner.py`
  - `AgenticMemory/profile_topic_regrouping.py`
- CR runner help 已确认不再暴露 unitization router 相关参数
- profile script help 已确认不再暴露 `--regroup-unitization-mode`
- 隔离结构 smoke test 通过：`ShortTermMemoryBuffer` 保存 `MemoryTurn`，recent prompt 保留 official formatted turn，ping-pong flush 信号正常

## 2026-04-12 - Format-aware regrouping unitization

更新范围：

- `AgenticMemory/topic_regrouper.py`
- `AgenticMemory/memoryagentbench_cr_runner.py`
- `AgenticMemory/profile_topic_regrouping.py`

主要变更：

- 将 regrouping 内部局部单位从 `SentenceUnit` 改为更中性的 `RegroupUnit`
- 新增 `unitization_mode`
- 当前支持 `fact_sentence`, `sentence`, `paragraph`, `chunk`
- CR runner 新增 `--regroup-unitization-mode`，默认 `fact_sentence`
- profiling 脚本同步新增同名参数
- trace / result 中新增 `unitization_mode`, `unit_count`, `unit_indices`
- 为兼容已有分析脚本，暂时保留 `sentence_count` / `sentence_indices`

设计含义：

- CR / FactConsolidation 可以继续使用 `fact_sentence`
- 非 CR 数据后续应按数据形态选择 turn / paragraph / discourse block / example 等局部单位
- 方法表述从 sentence-level topic clustering 调整为 format-aware unitization + buffer-level regrouping

## 2026-04-12 - Agentic unitization router

更新范围：

- `AgenticMemory/unitization_router.py`
- `AgenticMemory/topic_regrouper.py`
- `AgenticMemory/memoryagentbench_cr_runner.py`
- `AgenticMemory/profile_topic_regrouping.py`

主要变更：

- 新增 `AgenticUnitizationRouter`
- 新增结构化 `UnitizationDecision`
- `--regroup-unitization-mode` 默认改为 `auto_agentic`
- 固定模式保留为 ablation 参数
- 新增 `dialogue_turn` 与 `example` unitization 支持
- `TopicRegrouper.regroup()` 支持 per-window unitization override
- group trace 记录 `unitization_decision`

验证：

- `py_compile` 通过
- mock LLM smoke test 通过
- OpenRouter `gpt-5.4-mini` router API smoke test 通过，CR preview 被判定为 `fact_sentence`

## 2026-04-12 - MemoryTurn short-term buffer structure

更新范围：

- `AgenticMemory/short_term_memory.py`
- `AgenticMemory/memoryagentbench_cr_runner.py`
- `AgenticMemory/unitization_router.py`
- `AgenticMemory/topic_regrouper.py`
- `AgenticMemory/profile_topic_regrouping.py`

主要变更：

- `RecentMemoryItem` 改为 `MemoryTurn`
- `ShortTermMemoryBuffer.regions` 现在保存 `List[List[MemoryTurn]]`
- `MemoryTurn` 字段固定为：
  - `turn_id`
  - `raw_context`
  - `formatted_turn`
  - `source`
  - `timestamp`
  - `token_count`
  - `ingest_index`
  - `unitization_decision`
- ingest 时立即生成官方 memorize wrapper，保存到 `formatted_turn`
- recent prompt 改为展示 `formatted_turn`
- regroup/router 输入类型改为 `MemoryTurn`
- trace 增加 turn-level 标识，保留部分 chunk 字段用于兼容旧分析

验证：

- `py_compile` 通过
- 隔离 smoke test 通过：buffer 保存 `MemoryTurn`，recent prompt 可见官方合成对话格式，group trace 可回溯 `input_turn_ids`

## 1. embedding 改造

目标：

- 让项目从依赖本地 `all-MiniLM-L6-v2` 转为可用 OpenAI API 的 embedding

处理：

- 默认 embedding 改为：
  - `text-embedding-3-small`

影响文件包括：

- `AgenticMemory/memory_layer.py`
- `AgenticMemory/memory_layer_robust.py`
- `AgenticMemory/test_advanced.py`
- `AgenticMemory/test_advanced_robust.py`
- `A-mem-sys/agentic_memory/retrievers.py`
- `A-mem-sys/agentic_memory/memory_system.py`

## 2. 添加 memory update trace

目标：

- 为 selective forgetting 分析提供结构化日志

主要改动文件：

- `AgenticMemory/memory_layer_robust.py`

新增能力：

- `MemoryUpdateTraceLogger`
- 支持 JSONL trace

主要事件：

- `note_created`
- `neighbor_retrieval`
- `no_neighbors_found`
- `evolution_decision`
- `strengthen_details`
- `neighbor_updates`
- `evolution_complete`
- `evolution_error`
- `note_stored`

## 3. benchmark runner

主要文件：

- `AgenticMemory/memoryagentbench_cr_runner.py`

增加内容：

1. 可直接加载 `MemoryAgentBench` 的 `Conflict_Resolution`
2. 支持参数：
   - `--source`
   - `--chunk-size`
   - `--max-questions`
   - `--trace-path`
3. 保存：
   - 问题
   - 答案
   - 预测
   - raw retrieval context
   - final prompt
   - metrics

## 4. GPT-5 兼容改动

主要文件：

- `AgenticMemory/memory_layer_robust.py`

改动：

- 对 GPT-5 系列使用 `max_completion_tokens`
- 对其他模型保持 `max_tokens`

原因：

- `gpt-5.4-mini` 不接受 `max_tokens`

## 5. memory construction prompt 对齐 benchmark

主要文件：

- `AgenticMemory/memoryagentbench_cr_runner.py`

改动前：

- 直接 `add_note(chunk, time=...)`

改动后：

- 先使用官方 `factconsolidation` 的 `memorize` 模板包装 chunk
- 再 `add_note(formatted_chunk, time=...)`

保留不变：

- A-Mem 的 note 分析
- A-Mem 的 evolution
- A-Mem 的检索方式

## 6. 运行辅助改动

完成内容：

1. 设置 `OPENAI_API_KEY` 环境变量
2. 为本地官方 benchmark 仓库建立目录映射
3. 使用 `amem310` 环境跑 benchmark

注意事项：

- API key 没有写入代码仓库
- 环境变量通过运行环境提供

## 7. SimpleMem-style raw turn window decomposition

主要文件：

- `AgenticMemory/memory_window_buffers.py`
- `AgenticMemory/memory_unit_decomposer.py`
- `AgenticMemory/memoryagentbench_cr_runner.py`

本次修正：

1. 新增 `RawMemoryTurnWindowBuffer`
   - 保存 `List[MemoryTurn]`
   - 默认 `window_size=40`
   - 默认 `token_budget=4096`
   - 默认 `overlap_size=2`
   - 触发条件为 turn 数达到窗口大小，或 token 数达到预算
   - 处理窗口后按 SimpleMem 风格保留 overlap turns
2. 修改 `MemoryUnitDecomposer`
   - 新增 `decompose_window(window_id, turns)`
   - prompt 输入从单个 `MemoryTurn` 改为多个 dialogue turns
   - 输出仍为 `List[MemoryUnit]`
   - `MemoryUnit.source_turn_ids` 支持多个源 turn
   - schema 借鉴 SimpleMem `MemoryEntry` 的 `lossless_restatement`, `keywords`, `timestamp`, `location`, `persons`, `entities`, `topic`
3. 新增 `MemoryUnitPingPongBuffer`
   - 二层 ping-pong buffer 存放 `List[MemoryUnit]`
   - 默认总预算 `4096 token`
   - 默认 region size 为预算的一半
   - flush 输出较大的 `MemoryUnit` window，再进入 `TopicRegrouper.regroup_units()`
4. 更新 CR runner 主线
   - ingest 时仍先构造官方 benchmark synthetic dialogue `formatted_turn`
   - `MemoryTurn` 进入 raw turn window
   - raw window 触发后由 LLM 一次性抽取多个 `MemoryUnit`
   - `MemoryUnit` 再进入二层 ping-pong buffer
   - 二层 flush 后进行 topic regrouping 或直接 memory-unit archival
   - 继续保留 Recent + Archival dual retrieval

SimpleMem 对齐依据：

- 已核对 `C:\Users\ddger\Documents\AMproject\refs\SimpleMem\core\memory_builder.py`
- `dialogue_buffer` 使用 window 处理，而不是一次只处理一个 turn
- `window = self.dialogue_buffer[:self.window_size]`
- `self.dialogue_buffer = self.dialogue_buffer[self.step_size:]`
- `step_size = max(1, window_size - overlap_size)`
- 已核对 `config.py.example` 当前样例默认 `WINDOW_SIZE = 40`, `OVERLAP_SIZE = 2`
- 已核对 `models\memory_entry.py` 的 `MemoryEntry` 字段

本项目偏离点：

- SimpleMem 只按 turn window 触发；本项目额外加入 `token_budget=4096`，用于兼容 MemoryAgentBench CR 这类单 turn/chunk 很长的输入
- SimpleMem 写入 LanceDB/BM25/hybrid retrieval；本项目不引入这些 store，仍写入 A-Mem archival notes
- 本项目额外保留 `source_turn_ids`，用于 trace 和后续错误分析
- 本项目不 fallback 到 sentence split，避免把旧 CR 特化变量混入新结构

## 8. Three-layer retrieval adaptation

主要文件：

- `AgenticMemory/memory_window_buffers.py`
- `AgenticMemory/memoryagentbench_cr_runner.py`

背景：

- 写入侧已经变成 `MemoryTurn -> MemoryUnit -> A-Mem archival`
- 读取侧此前仍只读取 `Recent MemoryTurn` 和 `Archival A-Mem`
- 中间的 `MemoryUnit` buffer 没有作为可检索存储介质进入 QA prompt

改动：

1. `MemoryUnitPingPongBuffer` 增加独立 embedding retriever
   - `retrieve(query, k)`
   - `format_for_prompt(units)`
2. `answer()` 改成三段式检索：
   - `Recent Turn Memory`
   - `Structured Working Memory`
   - `Archival Memory`
3. prompt 优先级更新为：
   - 优先使用 `Recent Turn Memory`
   - 不足时使用 `Structured Working Memory`
   - 再不足时使用 `Archival Memory`
   - 冲突时按上述层级裁决
4. `ingest_chunks()` 结束时不再强制 `flush_remaining()` 清空 `MemoryUnitPingPongBuffer`
   - 剩余 raw turn window 仍会 decomposed 成 `MemoryUnit`
   - 未达到二层 flush 条件的 `MemoryUnit` 保留为 structured working memory
5. 结果 JSON 增加 `working_unit_context`

当前语义：

- `MemoryTurn` 是高保真最近原文层
- `MemoryUnit` 是结构化工作记忆层
- `A-Mem archival note` 是长期归档层

