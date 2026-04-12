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

## 11. 四层记忆方案阶段 A：API 可用性验证与 smoke test

### 11.1 OpenRouter API 可用性复核

背景：

- 在实现 `short-term buffer + dual retrieval` 后，首次 smoke 没有真正跑通
- 重新排查发现，问题不只可能来自 API key，还涉及：
  - chat model 的 region 可用性
  - embedding provider 的实际返回

本轮追加验证内容：

1. 显式设置：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL = https://openrouter.ai/api/v1`
2. 直接调用 OpenRouter HTTP 接口验证：
   - `gpt-5.4-mini` chat
   - `openai/text-embedding-3-small` embeddings

最终确认：

- `gpt-5.4-mini` chat 可用
- `openai/text-embedding-3-small` embeddings 可用

说明：

- 这一步的目的是确认当前 OpenRouter 节点与 region 条件下，后续阶段 A 实验具备可运行前提
- 这一步不构成 benchmark 结果，只是 provider 层通路验证

### 11.2 阶段 A 最小 smoke：Recent + Archival 双通道

实验条件：

- source：
  - `factconsolidation_sh_6k`
- model：
  - `gpt-5.4-mini`
- embedding：
  - `openai/text-embedding-3-small`
- provider：
  - OpenRouter
- `chunk_size = 512`
- `max_questions = 1`
- 启用：
  - `short-term buffer`
  - `Recent Memory + Archival Memory` 双通道 retrieval
- 未启用：
  - topic regrouping

结果文件：

- `AgenticMemory/smoke_stageA_recent_only.json`
- `AgenticMemory/smoke_stageA_recent_only_trace.jsonl`
- `AgenticMemory/smoke_stageA_recent_only_recenttrace.jsonl`

结果：

- `exact_match = 0.0000`
- `f1 = 0.0000`

但本次 smoke 的关键结论不是分数，而是链路验证成功：

1. `Recent Memory` 和 `Archival Memory` 都成功进入最终 prompt
2. `recent trace` 正常记录了：
   - chunk 写入
   - token 累积
   - buffer 状态
3. 当前阶段 A 的新 orchestration 已可运行：
   - `ingest -> short-term buffer -> archival retrieval + recent retrieval -> answer`

补充观察：

- 本次 smoke 结束时：
  - `chunks_ingested = 12`
  - `archived_units = 8`
  - `recent_buffer_size = 4`
- 这与 `4096 token` buffer 设定是吻合的：
  - 前 8 个 chunk 已进入 archival
  - 最近 4 个 chunk 仍停留在 short-term buffer

### 11.3 兼容性修复

在 smoke 过程中发现一个实现兼容问题：

- `openai/text-embedding-3-small` 这种带 provider 前缀的模型名
- 会被旧的 `build_embedding_model()` 误判成 `SentenceTransformer` 名称

修复后：

- `text-embedding-*`
- 以及 `openai/text-embedding-*`

都会正确走 OpenAI/OpenRouter embedding API 路径，而不是误走本地 sentence-transformers fallback。

### 11.4 阶段 A 小基准：`factconsolidation_sh_32k` 前 50 问

实验条件：

- source：
  - `factconsolidation_sh_32k`
- model：
  - `gpt-5.4-mini`
- embedding：
  - `openai/text-embedding-3-small`
- provider：
  - OpenRouter
- `chunk_size = 512`
- `memory construction`：
  - 继续保持 benchmark 官方 memorize prompt 对齐
- 启用：
  - `short-term buffer`
  - `Recent Memory + Archival Memory` 双通道 retrieval
  - `Recent Memory` 冲突优先
- 未启用：
  - topic regrouping

结果文件：

- `AgenticMemory/cr_sh_32k_50q_stageA_recent_archival_openrouter_results.json`
- `AgenticMemory/cr_sh_32k_50q_stageA_recent_archival_openrouter_trace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageA_recent_archival_openrouter_recenttrace.jsonl`

结果：

- `exact_match = 0.4400`
- `f1 = 0.4793`
- `substring_exact_match = 0.4600`

与当前基线对比：

基线：

- `factconsolidation_sh_32k + chunk_size=512 + gpt-5.4-mini + memprompt aligned`
- `exact_match = 0.4000`
- `f1 = 0.4327`
- `substring_exact_match = 0.4000`

阶段 A 提升：

- `exact_match: +0.0400`
- `f1: +0.0467`
- `substring_exact_match: +0.0600`

结构性观察：

1. `chunks_ingested = 65`
2. `archived_units = 64`
3. `recent_buffer_size = 1`
4. `recent_buffer_tokens = 388`
5. `flush_windows = 8`

解释：

- 这说明阶段 A 方案在 `50` 问实验结束时：
  - 大部分 chunk 已经通过 flush 进入 archival A-Mem
  - 最后的 1 个 chunk 仍停留在 short-term buffer
- 也就是说，阶段 A 不会改变 benchmark 原始 chunk 数，但会改变：
  - 哪些内容停留在 recent memory
  - 哪些内容沉到 archival memory

当前结论：

- 只引入 `short-term recent-first retrieval`
- 还未启用 topic regrouping

就已经在 `SH 32k` 小基准上带来了可见提升。

## 12. 阶段 B：Topic Regrouping 实现与测试

### 12.1 阶段 B 初始 smoke 与 regrouping 问题暴露

初始目标：

- 在阶段 A 基础上启用：
  - `topic regrouping`
- 验证链路：
  - `short-term buffer -> flush window -> topic regrouping -> grouped sub-chunks -> A-Mem`

初始 smoke：

- `factconsolidation_sh_6k`
- `chunk_size = 512`
- `max_questions = 3`
- 启用：
  - topic regrouping

初始结果文件：

- `AgenticMemory/smoke_stageB_topic_regrouping_sh6k_3q.json`
- `AgenticMemory/smoke_stageB_topic_regrouping_sh6k_3q_grouptrace.jsonl`

初始结构观察：

- 主链路可运行
- 但第一版 regrouping 使用：
  - 相似度阈值
  - 连通分量

导致严重的 giant-cluster 问题：

- 一个 flush window 中：
  - `582` 个句子
  - 其中 `533` 个句子落入同一个 topic group

解释：

- `FactConsolidation` 里的事实句模板高度相似
- 简单的 embedding threshold + transitive connectivity 很容易形成一整个巨型簇

结论：

- 方向未失效
- 但第一版 clustering 机制不够稳，需要继续收敛

### 12.2 阶段 B regrouping 机制修正

为了解决 giant-cluster 问题，本轮对 `topic_regrouper.py` 做了三类修正：

1. 句子清理
   - 合并纯编号/极短碎片句，减少 `sent_tokenize` 在事实编号文本上的碎裂
2. 图构造收紧
   - 从“阈值即连边”改为：
     - `similarity threshold`
     - `reciprocal top-k neighbors`
   - 减少由模板相似造成的链式连通
3. 超大簇二次拆分
   - 对超大 cluster 做二次切分
   - 使用轻量 `KMeans` 控制单 topic 的最大句子规模

这一步的目标不是追求最终最优分数，而是让 regrouping 至少形成可读、可分析、非塌缩的 topic buckets。

### 12.3 阶段 B 修正后 smoke

重新跑：

- `factconsolidation_sh_6k`
- `chunk_size = 512`
- `max_questions = 3`
- 启用：
  - topic regrouping

修正后观察：

- `sentence_count = 306`
- `cluster_count = 24`
- 最大簇从“几乎覆盖整个窗口”下降到：
  - `max_cluster = 52`

这说明：

- regrouping 仍不完美
- 但已经从“完全塌缩”变为“可工作的多 topic 分组”
- 一些 topic preview 已经能看出较明显的语义中心，例如：
  - `position / sport`
  - `founded by`
  - `continent`
  - `headquarters in city`

### 12.4 阶段 B 中等规模测试：`factconsolidation_sh_32k` 前 20 问

实验条件：

- source：
  - `factconsolidation_sh_32k`
- model：
  - `gpt-5.4-mini`
- embedding：
  - `openai/text-embedding-3-small`
- provider：
  - OpenRouter
- `chunk_size = 512`
- 启用：
  - `short-term buffer`
  - `Recent + Archival` 双通道 retrieval
  - `Recent Memory` 冲突优先
  - topic regrouping

结果文件：

- `AgenticMemory/cr_sh_32k_20q_stageB_topic_regrouping_openrouter_results.json`
- `AgenticMemory/cr_sh_32k_20q_stageB_topic_regrouping_openrouter_trace.jsonl`
- `AgenticMemory/cr_sh_32k_20q_stageB_topic_regrouping_openrouter_recenttrace.jsonl`
- `AgenticMemory/cr_sh_32k_20q_stageB_topic_regrouping_openrouter_grouptrace.jsonl`

结果：

- `exact_match = 0.6500`
- `f1 = 0.6950`
- `substring_exact_match = 0.6500`

与旧的 `20` 问结果相比，表现已经明显更强。

### 12.5 阶段 B 正式小基准：`factconsolidation_sh_32k` 前 50 问

实验条件：

- source：
  - `factconsolidation_sh_32k`
- model：
  - `gpt-5.4-mini`
- embedding：
  - `openai/text-embedding-3-small`
- provider：
  - OpenRouter
- `chunk_size = 512`
- 前 `50` 问
- 启用：
  - short-term buffer
  - recent-first dual retrieval
  - topic regrouping

结果文件：

- `AgenticMemory/cr_sh_32k_50q_stageB_topic_regrouping_openrouter_results.json`
- `AgenticMemory/cr_sh_32k_50q_stageB_topic_regrouping_openrouter_trace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageB_topic_regrouping_openrouter_recenttrace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageB_topic_regrouping_openrouter_grouptrace.jsonl`

结果：

- `exact_match = 0.5600`
- `f1 = 0.6013`
- `substring_exact_match = 0.5800`

与已有对照相比：

原始基线：

- `exact_match = 0.4000`
- `f1 = 0.4327`
- `substring_exact_match = 0.4000`

阶段 A：

- `exact_match = 0.4400`
- `f1 = 0.4793`
- `substring_exact_match = 0.4600`

阶段 B：

- `exact_match = 0.5600`
- `f1 = 0.6013`
- `substring_exact_match = 0.5800`

阶段 B 相对提升：

- 相对原始基线：
  - `exact_match: +0.1600`
  - `f1: +0.1687`
  - `substring_exact_match: +0.1800`
- 相对阶段 A：
  - `exact_match: +0.1200`
  - `f1: +0.1220`
  - `substring_exact_match: +0.1200`

结构性观察：

- `chunks_ingested = 65`
- `archived_units = 205`
- `recent_buffer_size = 1`
- `flush_windows = 8`

解释：

- 阶段 B 不再把每个 flush window 原样写入 archival
- 而是把每个 window 重新 regroup 成多个 topic sub-chunks
- 因此 archival units 数量明显增加

当前结论：

- 在当前实现下，阶段 B 的 topic regrouping 不是“轻微改善”
- 而是在 `SH 32k` 小基准上带来了非常明显的增益
- 说明“recent-first + write-unit reorganization” 这个方向值得继续深挖

## 2026-04-11 - Stage B topic regrouping 单-window 耗时 profiling

目的：

- 只测试一个 short-term flush window 的 topic regrouping 耗时
- 与完整 benchmark runner 隔离
- 不调用 A-Mem `add_note`
- 不执行 QA
- 不把 dataset 加载、runner 启动、recent retrieval 等额外开销混入 regrouping 内部计时

测试条件：

- worktree：`AMproject-stageB`
- source：`factconsolidation_sh_32k`
- `chunk_size = 512`
- `recent_token_budget = 4096`
- embedding：`openai/text-embedding-3-small`
- provider：OpenRouter
- window：`window_0000`
- 输入 chunk：`chunk_0000` 到 `chunk_0007`
- window token 数：`4348`
- 输入句子数：`306`
- 输出 topic groups：`28`

产物：

- `AgenticMemory/profile_topic_regrouping.py`
- `AgenticMemory/profile_topic_regrouping_sh32k_window0_result.json`
- `AgenticMemory/profile_topic_regrouping_sh32k_window0_trace.jsonl`

内部耗时：

- `sentence_split_seconds = 0.0211`
- `embedding_seconds = 6.4161`
- `similarity_seconds = 0.0097`
- `graph_build_seconds = 0.0509`
- `connected_components_seconds = 0.0006`
- `kmeans_split_seconds = 7.6426`
- `total_seconds = 14.1450`

观察：

- 这次命令 wall time 约 `53.8s`，但这包含 Python 启动、dataset 加载等外部成本
- regrouping 内部计时应以 trace/result 中的 `timing_seconds.total_seconds = 14.1450` 为准
- 当前主要耗时来自 embedding 调用和 oversized cluster 的 KMeans 拆分
- 句子两两 cosine similarity 和 graph build 在本 window 上不是主要耗时
- 这说明当前效率瓶颈不只在 O(n^2) similarity，也包括 embedding API latency 与 KMeans 工程补丁

当前结论：

- Stage B topic regrouping 仍不能收口为最终方法
- 后续必须继续做效率与质量验证
- `similarity_threshold`、`reciprocal_top_k`、`max_cluster_sentences`、KMeans 拆分策略都需要 ablation
- 如果目标是即时 memory evolution，当前整窗 flush + API embedding + KMeans 拆分的成本需要继续优化

## 2026-04-11 - Stage B sliding window flush 机制改造

目的：

- 将 short-term buffer 从“满窗 flush 后清空”改为“FIFO 滑动 buffer”
- 为后续即时 memory evolution 和更连续的 topic regrouping 做准备

代码变更：

- `AgenticMemory/short_term_memory.py`
  - 新增 `overlap_tokens`
  - `flush_window()` 改为只弹出最早的 stride window
  - 剩余 buffer 内容保留，但不参与本次 archival write
  - trace event 从 `recent_flush_cleared` 改为 `recent_flush_slid`
- `AgenticMemory/memoryagentbench_cr_runner.py`
  - 新增 CLI 参数 `--recent-window-overlap-tokens`
  - 结果 JSON 记录 `recent_window_overlap_tokens`

默认设置：

- `recent_token_budget = 4096`
- `recent_window_stride_tokens = 512`
- `recent_window_overlap_tokens = 3584`
- overlap 会被 clamp 到 `< token_budget`

验证：

- `py_compile` 通过：
  - `short_term_memory.py`
  - `memoryagentbench_cr_runner.py`
  - `profile_topic_regrouping.py`
- 隔离逻辑测试确认：
  - flush 后 buffer 不再清空
  - 本次只写入最早的 stride window
  - 其余 item 保留在 short-term buffer
- 语义修正：
  - 4096-token buffer 在当前 `chunk_size=512` 设置下应表示最近约 8 个 chunk
  - 默认滑动步长应接近 1 个 benchmark chunk，而不是半窗

注意：

- 当前版本不把保留的约 `3584` tokens 重复写入 archival
- 这降低了 note duplication 风险
- 但也意味着 topic regrouping 当前只作用于弹出的约 `512` token 小 window，可能削弱跨 buffer 的离散主题聚合能力
- 后续实验需要单独观察该副作用

## 2026-04-11 - Stage B sliding buffer 默认参数 50 问小基准

目的：

- 对比 Stage B 原整窗 flush 版本与 FIFO sliding buffer 版本
- 检查“只把最早约 512-token 小 window 写入 archival，剩余 buffer 保留”的效果

实验条件：

- source：`factconsolidation_sh_32k`
- model：`gpt-5.4-mini`
- embedding：`openai/text-embedding-3-small`
- provider：OpenRouter
- `chunk_size = 512`
- 前 `50` 问
- 启用：
  - short-term buffer
  - recent-first dual retrieval
  - topic regrouping
  - FIFO sliding buffer
- `recent_token_budget = 4096`
- `recent_window_stride_tokens = 512`
- `recent_window_overlap_tokens = 3584`

结果文件：

- `AgenticMemory/cr_sh_32k_50q_stageB_sliding_default_results.json`
- `AgenticMemory/cr_sh_32k_50q_stageB_sliding_default_trace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageB_sliding_default_recenttrace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageB_sliding_default_grouptrace.jsonl`

结果：

- `exact_match = 0.4800`
- `f1 = 0.5247`
- `substring_exact_match = 0.5000`

结构指标：

- `chunks_ingested = 65`
- `archived_units = 278`
- `flush_windows = 58`
- `recent_buffer_size = 7`
- `recent_buffer_tokens = 3637`

与对照相比：

原始基线：

- `exact_match = 0.4000`
- `f1 = 0.4327`
- `substring_exact_match = 0.4000`

阶段 A：

- `exact_match = 0.4400`
- `f1 = 0.4793`
- `substring_exact_match = 0.4600`

Stage B 整窗 flush：

- `exact_match = 0.5600`
- `f1 = 0.6013`
- `substring_exact_match = 0.5800`
- `archived_units = 205`
- `flush_windows = 8`

Stage B FIFO sliding buffer：

- `exact_match = 0.4800`
- `f1 = 0.5247`
- `substring_exact_match = 0.5000`
- `archived_units = 278`
- `flush_windows = 58`

当前观察：

- FIFO sliding buffer 仍优于原始基线和阶段 A
- 但显著低于 Stage B 整窗 flush
- 这说明只把最早约 512-token 小 window 送入 topic regrouping，可能削弱了 topic regrouping 的跨 chunk 离散主题聚合能力
- 同时 archival units 增加到 `278`，说明小窗写入更碎，可能提高检索噪声或 note construction 成本
- 当前结果不支持直接用 FIFO 512-token 小窗替代整窗 regrouping 作为默认 Stage B 方案

## 2026-04-11 - Stage B ping-pong two-region buffer 实现

目的：

- 替换 FIFO 512-token sliding write
- 使用类似复制式 GC 的 two-region ping-pong buffer
- 只暴露总 buffer size，region size 固定为总 buffer 的一半

机制：

- `recent_token_budget = buffer_size`
- `recent_region_size = buffer_size / 2`
- 先写 region A
- region A 满后写 region B
- region B 满后 flush region A 到 topic regrouping / archival，并清空 region A
- 接着写 region A
- region A 满后 flush region B
- 以此交替

代码变更：

- `AgenticMemory/short_term_memory.py`
  - 新增 `regions`
  - 新增 `region_tokens`
  - 新增 `region_full`
  - 新增 `active_region`
  - 新增 `pending_flush_region`
  - `flush_window()` 改为只 flush 待清空 region
- `AgenticMemory/memoryagentbench_cr_runner.py`
  - 移除主实验参数中的 sliding stride / overlap 语义
  - 结果 JSON 记录 `recent_region_size`
  - `flush_history` 记录 region flush 后的 buffer 状态

验证：

- `py_compile` 通过
- 隔离逻辑测试通过：
  - `4096` buffer 下 region size 为 `2048`
  - 第一次 flush 写入 `chunk_0000` 到 `chunk_0003`
  - 保留 `chunk_0004` 到 `chunk_0007`
  - 下一轮 flush 写入 `chunk_0004` 到 `chunk_0007`

下一步实验：

- 跑三组 `factconsolidation_sh_32k + chunk_size=512 + 前50问`：
  - buffer `4096` / region `2048`
  - buffer `8192` / region `4096`
  - buffer `2048` / region `1024`

## 2026-04-12 - Stage B ping-pong buffer 小基准

目的：

- 对比 ping-pong two-region buffer 与既有 Stage B 整窗 flush / FIFO sliding buffer
- 检查 region size 对 topic regrouping 写入视野的影响

共同实验条件：

- source：`factconsolidation_sh_32k`
- model：`gpt-5.4-mini`
- embedding：`openai/text-embedding-3-small`
- provider：OpenRouter
- `chunk_size = 512`
- 前 `50` 问
- 启用：
  - short-term buffer
  - recent-first dual retrieval
  - topic regrouping
  - ping-pong two-region buffer

### buffer 4096 / region 2048

结果文件：

- `AgenticMemory/cr_sh_32k_50q_stageB_pingpong_b4096_results.json`
- `AgenticMemory/cr_sh_32k_50q_stageB_pingpong_b4096_trace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageB_pingpong_b4096_recenttrace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageB_pingpong_b4096_grouptrace.jsonl`

结果：

- `exact_match = 0.4800`
- `f1 = 0.5270`
- `substring_exact_match = 0.5000`

结构指标：

- `chunks_ingested = 65`
- `recent_token_budget = 4096`
- `recent_region_size = 2048`
- `flush_windows = 15`
- `archived_units = 268`
- `recent_buffer_size = 5`
- `recent_buffer_tokens = 2569`

观察：

- 相比 FIFO 512-token sliding buffer，指标基本接近
- 虽然写入 horizon 从 512 提升到 2048，但仍未恢复整窗 4096 regrouping 的效果
- archived units 仍偏多，说明 2048 region 对当前 FactConsolidation 可能仍然偏碎

### buffer 8192 / region 4096

结果文件：

- `AgenticMemory/cr_sh_32k_50q_stageB_pingpong_b8192_results.json`
- `AgenticMemory/cr_sh_32k_50q_stageB_pingpong_b8192_trace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageB_pingpong_b8192_recenttrace.jsonl`
- `AgenticMemory/cr_sh_32k_50q_stageB_pingpong_b8192_grouptrace.jsonl`

结果：

- `exact_match = 0.5800`
- `f1 = 0.6133`
- `substring_exact_match = 0.6000`

结构指标：

- `chunks_ingested = 65`
- `recent_token_budget = 8192`
- `recent_region_size = 4096`
- `flush_windows = 7`
- `archived_units = 180`
- `recent_buffer_size = 9`
- `recent_buffer_tokens = 4730`

观察：

- 当前结果优于 Stage B 整窗 flush：
  - 整窗 flush：`exact_match = 0.5600`, `f1 = 0.6013`, `substring_exact_match = 0.5800`
  - ping-pong 8192/4096：`exact_match = 0.5800`, `f1 = 0.6133`, `substring_exact_match = 0.6000`
- 它也明显优于 ping-pong 4096/2048
- 这支持一个更具体的判断：
  - 当前 topic regrouping 的有效写入视野大约需要接近 `4096` tokens
  - recent buffer 可以更大，用于保留短期裁决上下文

### 取消 buffer 2048 / region 1024

- 原计划第三组为 buffer `2048` / region `1024`
- 由于用户中途调整实验范围，本轮不再运行该组
- 从已有结果看，region 从 `2048` 增至 `4096` 后效果显著变好，因此 `1024` region 优先级暂时降低

当前结论：

- ping-pong 思路本身可行
- 但关键不是“是否 ping-pong”，而是 archival write horizon 是否足够大
- `4096/2048` 不足以超过整窗 flush
- `8192/4096` 当前是 Stage B 系列里最好的小基准结果

## 2026-04-12 - Edge pruning + connected components 替代 KMeans baseline

目的：

- 移除 topic regrouping 中的 KMeans oversized-cluster split
- 将其替换为更轻量、可解释的 graph baseline：
  - reciprocal top-k edge pruning
  - similarity threshold
  - connected components

代码变更：

- `AgenticMemory/topic_regrouper.py`
  - 删除 `sklearn.cluster.KMeans` 依赖
  - 删除 `_split_oversized_cluster()`
  - 删除 `kmeans_split_seconds`
  - trace 中新增：
    - `clustering_strategy = edge_pruning_connected_components`

隔离 profiling 条件：

- source：`factconsolidation_sh_32k`
- `chunk_size = 512`
- profiling window：`window_0000`
- 输入 chunk：`chunk_0000` 到 `chunk_0007`
- 输入句子数：`306`
- embedding：`openai/text-embedding-3-small`

产物：

- `AgenticMemory/profile_topic_regrouping_edge_pruning_sh32k_window0_result.json`
- `AgenticMemory/profile_topic_regrouping_edge_pruning_sh32k_window0_trace.jsonl`

结果：

- `groups_count = 25`
- 最大 group 句子数：`121`
- `total_seconds = 5.6586`
- `embedding_seconds = 5.5965`
- `similarity_seconds = 0.0063`
- `graph_build_seconds = 0.0403`
- `connected_components_seconds = 0.0004`

与旧 KMeans profiling 对比：

- 旧 KMeans 版本：
  - `groups_count = 28`
  - 最大 group 句子数约 `66`
  - `total_seconds = 14.1450`
  - `kmeans_split_seconds = 7.6426`
- edge pruning baseline：
  - `groups_count = 25`
  - 最大 group 句子数 `121`
  - `total_seconds = 5.6586`

当前观察：

- 新 baseline 明显更快
- 但默认 `similarity_threshold=0.42` 与 `reciprocal_top_k=5` 仍会产生 giant cluster
- 因此它目前只能视为轻量 baseline，不能直接视为优于 KMeans 的最终替代
- 下一步如果跑完整 benchmark，应同时考虑提高阈值或降低 top-k 做 ablation

## 2026-04-12 - Adaptive partition selection for topic regrouping

目的：

- 在不恢复 KMeans 的前提下，解决 edge pruning baseline 的 giant cluster 问题
- 不全局固定 `alpha/top_m`
- 对每个 flush window 自适应选择结构评分最好的 graph partition

实现：

- `AgenticMemory/topic_regrouper.py`
  - 对同一个 window 生成多个 candidate partitions
  - 每个 candidate 仍然使用：
    - global similarity threshold
    - reciprocal top-k
    - local edge pruning
    - connected components
  - 候选集：
    - base reciprocal top-k
    - `alpha=0.0, top_m=5`
    - `alpha=0.0, top_m=3`
    - `alpha=0.5, top_m=3`
    - `alpha=1.0, top_m=3`
    - `alpha=0.5, top_m=2`
    - `alpha=1.0, top_m=2`
  - 对 tiny components 做 nearest non-tiny centroid attachment，防止 singleton 直接成为 archival notes
  - 用结构评分选择最终 partition

评分：

- `semantics_score`
- `balance_score`
- `avg_size_score`
- `fragmentation_penalty`
- `giant_penalty`

当前 score：

- `score = semantics_score + 0.25 * balance_score + 0.75 * avg_size_score - 1.5 * fragmentation_penalty - 0.7 * giant_penalty`

隔离 profiling 条件：

- source：`factconsolidation_sh_32k`
- `chunk_size = 512`
- profiling window：`window_0000`
- 输入 chunk：`chunk_0000` 到 `chunk_0007`
- 输入句子数：`306`
- embedding：`openai/text-embedding-3-small`

产物：

- `AgenticMemory/profile_topic_regrouping_adaptive_partition_v3_sh32k_window0_result.json`
- `AgenticMemory/profile_topic_regrouping_adaptive_partition_v3_sh32k_window0_trace.jsonl`

结果：

- selected candidate：
  - `alpha = 1.0`
  - `top_m = 3`
- `groups_count = 65`
- 最大 group 句子数：`16`
- singleton ratio：`0.0`
- tiny cluster ratio：`0.0`
- `total_seconds = 6.5471`
- `embedding_seconds = 6.1823`
- `partition_selection_seconds = 0.3340`

与前序版本对比：

- KMeans 版本：
  - `groups_count = 28`
  - 最大 group 约 `66`
  - `total_seconds = 14.1450`
- edge pruning baseline：
  - `groups_count = 25`
  - 最大 group `121`
  - `total_seconds = 5.6586`
- adaptive partition selection：
  - `groups_count = 65`
  - 最大 group `16`
  - `total_seconds = 6.5471`

当前观察：

- adaptive partition selection 明显压制了 giant cluster
- 相比 KMeans 仍显著更快
- 相比 naive edge pruning，partition selection 多花约 `0.33s`，主要成本仍是 embedding
- 当前风险是 groups 数量偏多，可能带来 archival note 碎片化
- 下一步需要跑 `8192/4096` 小基准确认 QA 指标，不应只看结构指标

## 2026-04-12 - Method update: format-aware unitization

类型：

- 方法论与代码接口更新
- 未新增 benchmark 结果

背景：

- MemoryAgentBench 将输入统一包装成 multi-turn memorization protocol
- 但不同 split 的 `{context}` 内部形态并不统一：
  - CR / FactConsolidation 是编号 facts chunk
  - ReDial / LongMemEval 更接近 dialogue turns
  - EventQA / InfBench / DetectiveQA 更接近 book / narrative / document
  - ICL 更接近 example list

代码更新：

- `AgenticMemory/topic_regrouper.py`
  - 将内部局部单位从 `SentenceUnit` 调整为更中性的 `RegroupUnit`
  - 新增 `unitization_mode`
  - 当前支持：`fact_sentence`, `sentence`, `paragraph`, `chunk`
  - trace 中新增 `unitization_mode`, `unit_count`, `unit_indices`
  - 为兼容旧 trace 分析，暂时保留 `sentence_count` / `sentence_indices` 字段
- `AgenticMemory/memoryagentbench_cr_runner.py`
  - 新增 CLI 参数 `--regroup-unitization-mode`
  - 默认值为 `fact_sentence`
  - result JSON 中记录 `regroup_unitization_mode`
- `AgenticMemory/profile_topic_regrouping.py`
  - 新增同名 profiling 参数
  - 输出 `group_unit_counts`

当前决策：

- CR 上可以继续使用 `fact_sentence`，但这只是数据形态参数
- 后续非 CR runner 不应默认复用 CR 的 sentence-level unitization
- 后续方法表述应改成 format-aware unitization + buffer-level regrouping / segmentation

验证：

- 已运行 `python -m py_compile AgenticMemory\topic_regrouper.py AgenticMemory\memoryagentbench_cr_runner.py AgenticMemory\profile_topic_regrouping.py`
- 已在 `amem310` 环境运行隔离 smoke test：
  - `fact_sentence`：`groups = 2`, `units = 5`
  - `paragraph`：`groups = 2`, `units = 4`
  - `chunk`：`groups = 1`, `units = 2`
  - 三种模式均能写出 `unitization_mode`, `unit_count`, `unit_indices` trace 字段
- 已检查 runner/profiling CLI help，确认 `--regroup-unitization-mode {fact_sentence,sentence,paragraph,chunk}` 参数可见
