# A-Mem Code Changes

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

