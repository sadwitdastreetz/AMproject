# A-Mem Key Decisions

## 1. 研究主线

本轮线程的核心目标不是直接提出新方案，而是：

1. 深入理解 A-Mem 的论文与代码
2. 跑通 benchmark 与小规模复现
3. 基于实验与日志，定位 A-Mem 在 selective forgetting 上的真实问题

## 2. 暂不绑定你自己的新方案

明确决策：

- 当前阶段不围绕 `MemoryItem / SemanticSlot / NoteRevision` 展开
- 不预设这些抽象一定保留
- 先把 A-Mem 与 selective forgetting benchmark 理清

## 3. 基准 benchmark 选择

最终聚焦：

- `MemoryAgentBench`
- 任务：
  - `Conflict_Resolution`
  - 即论文中的 `Selective Forgetting`

## 4. 关于 chunk size 的决策

重要共识：

1. 论文对 `SF` 主分析常提 `chunk_size = 512`
2. 但我们也把 A-Mem 视作高消耗 memory construction 方法，因此保留过：
   - `4096`

已形成的实验规范：

- 更贴近 benchmark 主设定时：
  - `chunk_size = 512`
- 从高成本 memory construction 视角观察时：
  - `chunk_size = 4096`

## 5. 关于 benchmark 主表的理解

已确认：

1. `Table 3` 的 `FactConsolidation-SH / MH` 不是各长度平均值
2. 更接近主实验条件下的单一长度结果
3. 与代码配置共同对照后，主设定对应 `262k`

## 6. 关于基准模型

最终固定：

- `gpt-5.4-mini` 作为当前基准模型

原因：

1. 比 `gpt-4o-mini` 更适合作为新一轮对照基线
2. 有助于区分“模型太弱”与“memory mechanism 本身有问题”

## 7. 关于 benchmark 对齐策略

经过多轮讨论后形成的决策：

1. `query prompt` 必须与官方 SF 模板对齐
2. `memory construction prompt` 也应尽量对齐官方 `memorize` 模板
3. 但 A-Mem 自身不可分割的记忆更新与检索逻辑不改

这意味着：

- 吸收 benchmark 的 task discipline
- 保留 A-Mem 的方法本体

## 8. 关于 provider 与运行环境

当前新增决策：

1. 运行环境允许通过：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   进行 provider 切换
2. 当前实验已切到：
   - OpenRouter
3. 这一切换被视为底层调用路由变化，不视为 memory method 变化

## 9. 关于后续小基准

已形成新的固定参考实验之一：

- `factconsolidation_sh_32k + chunk_size=512 + gpt-5.4-mini + trace`
- `memory construction` 对齐官方 memorize prompt
- 前 `50` 问
- 通过 OpenRouter 运行

该实验结果：

- `exact_match = 0.4000`
- `f1 = 0.4327`

用途：

- 作为后续尝试改进 selective forgetting 时的小基准
- 在继续做方法改动时优先用它做快速回归对照

## 10. 关于本轮暂停点

当前决策：

- 暂停继续提出改进方案
- 先存档
- 先把已有实验与理解整理成文档基础设施

## 11. 关于四层记忆方案的阶段拆分

当前新增决策：

1. 四层记忆方案分阶段实现
2. 先做：
   - `short-term buffer`
   - `Recent + Archival` 双通道 retrieval
3. 暂不把：
   - topic regrouping
   - A-Mem evolution 本体修复
   混入第一轮验证

原因：

1. 先单独验证 recent-memory priority 是否能立刻改善 selective forgetting
2. 避免把收益来源和变量混在一起

## 12. 关于 short-term buffer 的定义

当前新增决策：

1. short-term memory 的容量按：
   - `token budget`
   定义，而不是按固定 chunk 数定义
2. 第一版 token budget 固定为：
   - `4096`
3. 在当前 `FactConsolidation + chunk_size=512` 条件下，可近似理解为最近 `8` 个 benchmark chunks

## 13. 关于 retrieval 的第一版优先级策略

当前新增决策：

1. retrieval 第一版固定分为：
   - `Recent Memory`
   - `Archival Memory`
2. prompt 中必须显式声明：
   - 若两者冲突，优先 `Recent Memory`
3. 第一版不额外增加一次独立的 conflict arbitration LLM 调用

## 14. 关于 OpenRouter 运行前置验证

当前新增决策：

1. 在使用 OpenRouter 跑实验前，需要先验证：
   - chat model 可用
   - embedding model 可用
2. 对当前环境，已确认可用组合包括：
   - `gpt-5.4-mini`
   - `openai/text-embedding-3-small`
3. provider 通路验证应视为实验前置条件，而不是实验结果本身

## 15. 关于带 provider 前缀的 embedding model 名称

当前新增决策：

1. embedding model 名称允许使用：
   - `text-embedding-3-small`
   - `openai/text-embedding-3-small`
2. 带 provider 前缀的名称必须仍然走 OpenAI/OpenRouter embedding API
3. 不能误回落到本地 `SentenceTransformer` 路径

## 16. 关于四层记忆方案阶段 A 的当前基线结论

当前新增决策：

1. 阶段 A 的第一轮正式对照先固定为：
   - `factconsolidation_sh_32k`
   - `chunk_size = 512`
   - `gpt-5.4-mini`
   - OpenRouter
   - `openai/text-embedding-3-small`
   - 前 `50` 问
2. 阶段 A 当前只启用：
   - `short-term buffer`
   - `Recent + Archival` 双通道 retrieval
   - `Recent Memory` 冲突优先
3. 阶段 A 当前不启用：
   - topic regrouping

当前结果：

- `exact_match = 0.4400`
- `f1 = 0.4793`
- `substring_exact_match = 0.4600`

相对当前基线提升：

- `exact_match: +0.0400`
- `f1: +0.0467`
- `substring_exact_match: +0.0600`

这意味着：

- 只加 recent-memory priority 就已经能带来可见收益
- 后续 topic regrouping 应视为在这个阶段 A 基础上的第二层增益验证

## 17. 关于阶段 B 的 regrouping 实现策略

当前新增决策：

1. 阶段 B 不采用：
   - LightMem 的 turn-level segmentation
2. 阶段 B 当前采用：
   - flush window 内句子级局部单位
   - embedding-based topic regrouping
   - order-preserving reconstruction
3. regrouping 当前明确不做：
   - 文本改写
   - 事实摘要
   - relation schema 抽取

## 18. 关于阶段 B regrouping 的稳定化处理

当前新增决策：

1. 仅靠 embedding 阈值 + 连通分量会产生 giant-cluster
2. 为控制 topic collapse，当前实现加入：
   - 纯编号/短碎片句合并
   - reciprocal top-k 邻接约束
   - oversized cluster 二次拆分
3. 这些处理被视为：
   - regrouping 稳定化工程
   - 不视为 memory method 本体变化

## 19. 关于阶段 B 的当前正式结果

当前新增决策：

1. 阶段 B 当前正式小基准固定为：
   - `factconsolidation_sh_32k`
   - `chunk_size = 512`
   - `gpt-5.4-mini`
   - OpenRouter
   - `openai/text-embedding-3-small`
   - 前 `50` 问
2. 阶段 B 启用：
   - short-term buffer
   - recent-first dual retrieval
   - topic regrouping

当前结果：

- `exact_match = 0.5600`
- `f1 = 0.6013`
- `substring_exact_match = 0.5800`

相对原始基线提升：

- `exact_match: +0.1600`
- `f1: +0.1687`
- `substring_exact_match: +0.1800`

相对阶段 A 提升：

- `exact_match: +0.1200`
- `f1: +0.1220`
- `substring_exact_match: +0.1200`

当前判断：

- 阶段 B 已经显示出强于阶段 A 的额外增益
- 说明 topic regrouping 不只是结构上可行，而且在当前 `SH 32k` 小基准上已有明显效果

## 20. 关于阶段 B 不能过早收口的决定

当前新增决策：

1. 阶段 B 的 topic regrouping 目前仍是 prototype，不视为已完成方法。
2. 当前实验只说明该方向在 `SH 32k` 小基准上有效，不足以证明其是稳定、可泛化、可即时部署的 memory evolution 机制。
3. 后续优先关注：
   - regrouping 运行时成本
   - `similarity_threshold` ablation
   - `reciprocal_top_k` ablation
   - `max_cluster_sentences` 与 KMeans 拆大簇策略
   - embedding 相似度受 FactConsolidation 模板句式影响的问题
4. 当前不展开 MH 问题，优先把 SH 与 regrouping 机制本身分析清楚。

## 21. 关于 topic regrouping 耗时记录的决定

当前新增决策：

1. `TopicRegrouper` 需要在 `grouptrace` 中记录内部阶段耗时。
2. 耗时字段统一写入 `timing_seconds`：
   - `sentence_split_seconds`
   - `embedding_seconds`
   - `similarity_seconds`
   - `graph_build_seconds`
   - `connected_components_seconds`
   - `kmeans_split_seconds`
   - `total_seconds`
3. 单-window profiling 必须和正式实验 runner 隔离。
4. 新增独立测试脚本：
   - `AgenticMemory/profile_topic_regrouping.py`
5. 该脚本只构造一个 short-term flush window 并调用 `TopicRegrouper.regroup()`，不执行：
   - A-Mem note construction
   - QA
   - recent retrieval
   - benchmark scoring

当前 profiling 结果：

- 测试：`factconsolidation_sh_32k + chunk_size=512 + token_budget=4096`
- window：`window_0000`
- 输入：8 个 benchmark chunks，306 个句子
- 输出：28 个 topic groups
- regrouping 内部总耗时：`14.1450s`
- 主要耗时：
  - embedding：`6.4161s`
  - KMeans 拆大簇：`7.6426s`

当前判断：

- O(n^2) cosine similarity 是理论风险，但这次单-window profiling 中不是主耗时
- 当前更直接的工程瓶颈是 API embedding latency 与 KMeans 拆大簇
- KMeans 仍应视为工程补丁，不应作为强理论贡献表述
