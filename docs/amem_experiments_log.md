# A-Mem Experiments Log

## 1. 仓库与环境准备

已完成：

1. clone 仓库：
   - `AgenticMemory`
   - `A-mem-sys`
2. 建立可用 Python 环境：
   - `C:\Users\ddger\miniconda3\envs\amem310`
3. 安装依赖并确认：
   - `A-mem-sys` 可正常安装与运行测试
4. 将 embedding 路径改为 OpenAI API：
   - `text-embedding-3-small`

## 2. 早期跑通

### 2.1 A-mem-sys

结果：

- `10 passed`

意义：

- 产品化仓库最小主链路可运行

### 2.2 AgenticMemory on LoCoMo

完成内容：

- 跑通小规模 smoke reproduction
- 验证了：
  - 数据读取
  - memory 写入
  - memory 检索
  - 基于 memory 回答问题

结论：

- A-Mem 主链路在 LoCoMo 小规模条件下能工作

## 3. Conflict_Resolution 初步实验

### 3.1 `factconsolidation_sh_6k + chunk_size=4096`

结果文件：

- `AgenticMemory/cr_sh_6k_5q.json`

结果：

- `exact_match = 0.4`
- `f1 = 0.4`
- `substring_exact_match = 0.4`

说明：

- 小规模 exploratory run 能跑通
- 但 chunk 粒度过粗，不能直接当 selective forgetting 结论

### 3.2 `factconsolidation_mh_6k + chunk_size=4096`

结果文件：

- `AgenticMemory/cr_mh_6k_5q.json`

结果：

- `exact_match = 0.4`
- `f1 = 0.4`

说明：

- 同样只是 exploratory run

## 4. 262k + 4096 规范实验

### 4.1 `factconsolidation_mh_262k + chunk_size=4096`, 前 20 问

结果文件：

- `AgenticMemory/cr_mh_262k_20q_chunk4096.json`

结果：

- `chunks_ingested = 67`
- `exact_match = 0.0000`
- `f1 = 0.0333`
- `substring_exact_match = 0.0000`

结论：

- multi-hop selective forgetting 几乎完全失效

### 4.2 `factconsolidation_sh_262k + chunk_size=4096`, 前 20 问

结果文件：

- `AgenticMemory/cr_sh_262k_20q_chunk4096.json`

结果：

- `exact_match = 0.1500`
- `substring_exact_match = 0.2000`
- `f1 = 0.2256`

结论：

- `SH > MH`
- 但 selective forgetting 仍明显不足

## 5. 6k + 512 更贴近 selective forgetting 本体的实验

### 5.1 `factconsolidation_sh_6k + chunk_size=512`, 前 20 问

结果文件：

- `AgenticMemory/cr_sh_6k_20q_chunk512.json`

结果：

- `exact_match = 0.4000`
- `substring_exact_match = 0.4500`
- `f1 = 0.4167`
- `chunks_ingested = 12`

结论：

- 粒度更细后，更适合观察 selective forgetting 本体
- 这组实验里已经能看到大量“正确新值已在上下文中，但模型仍选旧值”的现象

### 5.2 `factconsolidation_mh_6k + chunk_size=512`, 前 5 问 trace

结果文件：

- `AgenticMemory/cr_mh_6k_5q_chunk512_trace_results.json`
- `AgenticMemory/cr_mh_6k_5q_chunk512_trace.jsonl`

结果：

- `exact_match = 0.0`
- `5/5` 全错

结论：

- `MH` 的失败不只是 conflict resolution，还叠加了 multi-hop chain composition 问题

## 6. 增加 trace 后的 SH 分析

### 6.1 `factconsolidation_sh_6k + chunk_size=512`, 前 5 问 trace

结果文件：

- `AgenticMemory/cr_sh_6k_5q_chunk512_trace_results.json`
- `AgenticMemory/cr_sh_6k_5q_chunk512_trace.jsonl`

结果：

- `4/5` 正确
- 唯一明显错题：
  - `Nobuhiro Watsuki`

关键观察：

- 旧值：
  - `Nobuhiro Watsuki is famous for Rurouni Kenshin.`
- 新值：
  - `Nobuhiro Watsuki is famous for The Fairly OddParents.`
- trace 显示新 note 写入时能召回旧 note
- 但系统没有显式做“新值覆盖旧值”，只做了语义邻居层面的处理

这成为后续 selective forgetting 缺陷分析的重要代表案例。

## 7. 切换到 `gpt-5.4-mini`

### 7.1 smoke test

结果文件：

- `AgenticMemory/smoke_gpt54mini_sh6k_1q.json`

说明：

- 模型切换后主链路可运行
- 同时修复了 GPT-5 需要 `max_completion_tokens` 的兼容问题

### 7.2 `factconsolidation_sh_32k + chunk_size=512`, 前 20 问

结果文件：

- `AgenticMemory/cr_sh_32k_20q_gpt54mini_chunk512.json`

结果：

- `exact_match = 0.50`
- `f1 = 0.565`

### 7.3 `factconsolidation_mh_32k + chunk_size=512`, 前 20 问

结果文件：

- `AgenticMemory/cr_mh_32k_20q_gpt54mini_chunk512.json`

结果：

- `exact_match = 0.00`
- `f1 = 0.0167`

结论：

- 更强模型能提升 `SH`
- 但几乎不能修复 `MH`

## 8. 新模型 trace 实验

### 8.1 `SH 32k + 512 + trace`

结果文件：

- `AgenticMemory/cr_sh_32k_20q_gpt54mini_chunk512_trace_results.json`
- `AgenticMemory/cr_sh_32k_20q_gpt54mini_chunk512_trace.jsonl`

结果：

- `exact_match = 0.45`
- `f1 = 0.515`

### 8.2 `MH 32k + 512 + trace`

结果文件：

- `AgenticMemory/cr_mh_32k_20q_gpt54mini_chunk512_trace_results.json`
- `AgenticMemory/cr_mh_32k_20q_gpt54mini_chunk512_trace.jsonl`

结果：

- `exact_match = 0.00`
- `f1 = 0.0167`

## 9. 对齐 memory construction prompt 后的复跑

变更：

- memory construction 阶段改为使用官方 `factconsolidation` 的 `memorize` 模板
- A-Mem 自身的记忆更新与检索方式保持不变

实验：

### `factconsolidation_mh_32k + chunk_size=512 + gpt-5.4-mini + trace`

结果文件：

- `AgenticMemory/cr_mh_32k_20q_gpt54mini_chunk512_trace_memprompt_results.json`
- `AgenticMemory/cr_mh_32k_20q_gpt54mini_chunk512_trace_memprompt.jsonl`

结果：

- `exact_match = 0.0000`
- `f1 = 0.0310`
- `substring_exact_match = 0.0500`

结论：

- 与未对齐 memory-construction prompt 的版本相比，差别很小
- 这说明 A-Mem 在 `MH` 上的失败主要不是由 prompt 未对齐引起，而是由方法本体结构导致

## 10. OpenRouter 切换与后续小基准

### 10.1 运行环境切换

完成内容：

1. 将 LLM / embedding 路径改为支持：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
2. 将当前运行环境切到：
   - `OPENAI_BASE_URL = https://openrouter.ai/api/v1`
3. 使用 key：
   - `sk-or-v1-...`

说明：

- 这一改动不改变 A-Mem 方法本体
- 仅改变底层 API provider 路由

### 10.2 OpenRouter smoke test

实验：

- `factconsolidation_sh_32k`
- `chunk_size = 512`
- `gpt-5.4-mini`
- `memory construction` 已对齐官方 memorize prompt
- `前 1 问`

结果文件：

- `AgenticMemory/smoke_sh32k_1q_gpt54mini_openrouter.json`
- `AgenticMemory/smoke_sh32k_1q_gpt54mini_openrouter_trace.jsonl`

结果：

- `exact_match = 0.0000`
- `f1 = 0.0000`

说明：

- 该 smoke test 的目的不是评估性能
- 而是确认 OpenRouter 这条调用链在当前 runner 中可正常 ingest / retrieve / answer

### 10.3 `factconsolidation_sh_32k + chunk_size=512 + gpt-5.4-mini + trace`, 前 50 问

实验条件：

- provider：
  - OpenRouter
- model：
  - `gpt-5.4-mini`
- source：
  - `factconsolidation_sh_32k`
- `chunk_size = 512`
- `memory construction` 已对齐官方 memorize prompt
- 保留 trace
- 范围：
  - `前 50 问`

结果文件：

- `AgenticMemory/cr_sh_32k_50q_gpt54mini_chunk512_trace_memprompt_openrouter_results.json`
- `AgenticMemory/cr_sh_32k_50q_gpt54mini_chunk512_trace_memprompt_openrouter.jsonl`

结果：

- `exact_match = 0.4000`
- `f1 = 0.4327`
- `substring_exact_match = 0.4000`
- `chunks_ingested = 65`

意义：

- 这组结果将作为后续尝试改进 selective forgetting 时的一个小基准
- 它比此前 `20` 问结果更稳定，也更适合作为后续对照
