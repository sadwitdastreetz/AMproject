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

## 22. 关于 Stage B flush 机制改为滑动窗口的决定

当前新增决策：

1. Stage B 的 short-term buffer flush 不再采用“整窗 flush 后清空”。
2. 改为 FIFO sliding buffer：
   - buffer 容量仍约为 `4096` tokens
   - buffer 满后，只把最早进入 buffer 的约 `512` token 小 window 送入 topic regrouping / archival write
   - 剩余约 `3584` tokens 继续保留在 short-term buffer 中
   - 保留部分不参与本次 archival construction
3. 默认 overlap 策略：
   - `recent_token_budget = 4096`
   - `recent_window_stride_tokens = 512`
   - `recent_window_overlap_tokens = 3584`
   - 即默认每次弹出并写入最早的约一个 benchmark chunk 宽度
4. overlap 参数接入 runner：
   - `--recent-window-overlap-tokens`
   - `--recent-window-stride-tokens`
5. 为避免 pathological case：
   - overlap 会被 clamp 到 `< token_budget`

当前判断：

- 滑动窗口更接近即时 memory evolution 场景，不再把 flush window 视为彼此完全割裂的 batch
- 对当前 `chunk_size=512` 设置，4096-token buffer 应被理解为最近约 8 个 chunk 的短期窗口，而不是每次 flush 后丢弃半个 buffer
- 当前版本不会把整个 4096-token buffer 重复写入 archival，避免 overlap 区域在每次 flush 时被重复构造为 note
- 后续仍需观察 FIFO 小 window 写入是否削弱 topic regrouping 的跨位置聚合能力
- 这仍属于 Stage B prototype 的机制探索，不视为最终收口方案

## 23. 关于 FIFO sliding buffer 默认基准结果的决定

当前新增实验结论：

1. 在 `factconsolidation_sh_32k + chunk_size=512 + 前50问` 上，FIFO sliding buffer 默认参数结果为：
   - `exact_match = 0.4800`
   - `f1 = 0.5247`
   - `substring_exact_match = 0.5000`
2. 它相比原始基线和阶段 A 仍有提升。
3. 但它明显弱于 Stage B 整窗 flush：
   - 整窗 flush：`exact_match = 0.5600`, `f1 = 0.6013`
   - FIFO sliding：`exact_match = 0.4800`, `f1 = 0.5247`
4. 结构上：
   - 整窗 flush：`flush_windows = 8`, `archived_units = 205`
   - FIFO sliding：`flush_windows = 58`, `archived_units = 278`

当前判断：

- FIFO sliding buffer 的语义更接近即时 memory evolution，但默认 `512-token` 小窗写入会削弱 topic regrouping 的跨 chunk 聚合能力
- 小窗写入还会产生更多 archival units，可能增加 note 碎片化、检索噪声和 construction 成本
- 因此不能把 FIFO sliding buffer 直接设为 Stage B 默认最终方案
- 后续更值得测试的方向是：
  - retrieval 仍用 4096-token recent buffer
  - archival write 使用更大的 regrouping horizon
  - 或者将 write trigger 与 write horizon 分离，避免每次只对 512-token 小窗做 topic regrouping

## 24. 关于改用 ping-pong two-region buffer 的决定

当前新增决策：

1. 放弃 FIFO 512-token sliding write 作为当前 Stage B 主方案。
2. 改用类似复制式 GC 的 two-region ping-pong buffer：
   - 总 buffer 大小由 `--recent-token-budget` 控制
   - region 大小固定为 `recent_token_budget / 2`
   - 每次只写入当前 active region
   - 当两个 region 都满后，flush 更早写满的 region 到 topic regrouping / archival
   - 被 flush 的 region 清空，并成为新的 active region
3. runner 对外只保留一个关键参数：
   - `--recent-token-budget`
4. region size 不单独暴露为实验参数，避免把变量拆太碎。

当前判断：

- 相比 FIFO 512-token 小窗写入，ping-pong region 能把 archival write horizon 提升到半个 buffer
- 对默认 `4096` buffer，write horizon 变为约 `2048` tokens
- 它避免整窗 4096 flush 的一次性大写入，也避免 512 小窗导致的过度碎片化
- 关键待验证问题是：`2048` region 是否足够恢复 topic regrouping 的跨 chunk 聚合能力

## 25. 关于 ping-pong buffer region size 的初步结论

当前新增实验结论：

1. `buffer=4096 / region=2048`：
   - `exact_match = 0.4800`
   - `f1 = 0.5270`
   - `substring_exact_match = 0.5000`
   - `flush_windows = 15`
   - `archived_units = 268`
2. `buffer=8192 / region=4096`：
   - `exact_match = 0.5800`
   - `f1 = 0.6133`
   - `substring_exact_match = 0.6000`
   - `flush_windows = 7`
   - `archived_units = 180`
3. 原计划 `buffer=2048 / region=1024` 本轮取消，不再运行。

与关键对照相比：

- Stage B 整窗 flush：
  - `exact_match = 0.5600`
  - `f1 = 0.6013`
  - `substring_exact_match = 0.5800`
- Stage B FIFO sliding：
  - `exact_match = 0.4800`
  - `f1 = 0.5247`
  - `substring_exact_match = 0.5000`

当前判断：

- `2048` region 没有恢复 topic regrouping 的跨 chunk 聚合收益
- `4096` region 当前表现最好，甚至略高于之前的 Stage B 整窗 flush
- 当前更合理的默认候选是：
  - `recent_token_budget = 8192`
  - `recent_region_size = 4096`
- 这说明 write horizon 对当前方法非常关键；如果 horizon 太小，ping-pong 机制本身不能弥补 topic regrouping 视野不足

## 26. 关于 KMeans 替代 baseline 的决定

当前新增决策：

1. KMeans oversized-cluster split 不再作为默认理论机制表述。
2. 新增轻量替代 baseline：
   - edge pruning
   - reciprocal top-k
   - connected components
3. 当前代码已移除 `KMeans` 路径，并在 trace 中记录：
   - `clustering_strategy = edge_pruning_connected_components`

profiling 观察：

- edge pruning baseline 单 window 耗时：
  - `total_seconds = 5.6586`
- 旧 KMeans 版本单 window 耗时：
  - `total_seconds = 14.1450`
- 主要速度收益来自移除：
  - `kmeans_split_seconds = 7.6426`

当前风险：

- 默认 `similarity_threshold = 0.42`
- 默认 `reciprocal_top_k = 5`
- 在 `window_0000` 上仍产生 `121` 句 giant cluster

当前判断：

- edge pruning + connected components 是更轻量、更可解释的 baseline
- 但它当前不是最终方案
- 后续需要做 threshold / top-k ablation，重点观察 giant cluster 是否能自然裂解

## 27. 关于 adaptive partition selection 的决定

当前新增决策：

1. 不回退到 KMeans。
2. 在 edge pruning + connected components 基础上加入 window-adaptive partition selection。
3. 每个 flush window 内生成多个 candidate partitions，再用结构评分选择最终 topic groups。
4. 为避免 singleton 过多，加入 nearest non-tiny centroid attachment：
   - 只吸收 tiny components
   - 不做 KMeans 式全局重聚类

当前 scoring：

- `score = semantics_score + 0.25 * balance_score + 0.75 * avg_size_score - 1.5 * fragmentation_penalty - 0.7 * giant_penalty`

单 window profiling 观察：

- selected candidate：
  - `alpha = 1.0`
  - `top_m = 3`
- `groups_count = 65`
- `max_cluster_size = 16`
- `total_seconds = 6.5471`
- `partition_selection_seconds = 0.3340`

与前序版本相比：

- naive edge pruning 的 `121` 句 giant cluster 被压制
- KMeans 的主要耗时被移除
- 新风险是 groups 数量偏多，可能导致 archival note 碎片化

当前判断：

- adaptive partition selection 是比 KMeans 更有方法论解释力的方向
- 但当前只是 structural baseline，不等于 QA 性能已验证
- 下一步应该在 `ping-pong buffer 8192 / region 4096` 条件下跑前 50 问，对比 KMeans 版本的 `exact_match = 0.5800`, `f1 = 0.6133`

## 28. 关于 unitization_mode 的修正

当前新增决策：

1. 不再把 `sentence-level` 作为通用中间层假设。
2. MemoryAgentBench 的 `multi-turn` 指的是外层实验协议：
   - 每个 benchmark chunk 会被官方 memorize prompt 包装成一轮 user-assistant 交互
   - 但 `{context}` 内部的数据形态并不统一
3. 对 CR / FactConsolidation：
   - `{context}` 是编号 facts chunk
   - 当前可以继续使用 `fact_sentence` 作为局部 unitization 参数
   - 这应被视为该数据集形态下的实验参数，而不是通用 memory evolution 机制
4. 对非 CR 数据：
   - 后续不应默认使用 CR 的 sentence/fact-sentence 策略
   - 对话类数据应使用 turn/message 单位
   - 长文、小说、document haystack 应使用 paragraph / discourse block / chunk 单位
   - ICL 类数据应使用 example 单位
5. 当前代码先暴露 `--regroup-unitization-mode`，默认仍为 `fact_sentence`，用于保持已跑 CR 实验可复现。

当前判断：

- 这个修正暂时解决了“CR 上 sentence-level 可能过拟合”的方法论问题
- 论文/报告中应写成 format-aware unitization，而不是 sentence-level topic clustering
- Stage B topic regrouping 仍未收口，后续需要在非 CR 数据或更自然的 dialogue/document 形态上重新验证

## 29. 关于 agentic unitization router 的决定

当前新增决策：

1. `unitization_mode` 不再只作为人工指定参数。
2. 新增 agentic router，让记忆系统在每个 flush window 进入 regrouping 前自行判断局部离散单位。
3. 默认策略改为：
   - `--regroup-unitization-mode auto_agentic`
4. 固定模式仍保留，用于 ablation 和复现实验：
   - `fact_sentence`
   - `dialogue_turn`
   - `paragraph`
   - `example`
   - `chunk`
   - `sentence`
5. router 输出必须是结构化 decision：
   - `mode`
   - `confidence`
   - `reason`
   - `router_type`
   - `fallback_used`
6. 默认 router 失败时终止实验，避免 silent fallback 污染实验结果。
7. 如需容错，可显式传入：
   - `--allow-unitization-router-fallback`

当前判断：

- 这是更符合 agentic memory evolution 的方向
- 代价是每个 flush window 增加一次 LLM 调用
- 后续实验报告必须记录 router decision，否则不能解释 regrouping 的输入单位选择

## 30. 关于 MemoryTurn buffer 的结构修正

当前新增决策：

1. ping-pong short-term buffer 的基本对象不再是 `RecentMemoryItem`。
2. buffer 内部改为保存 `MemoryTurn`：
   - `turn_id`
   - `raw_context`
   - `formatted_turn`
   - `source`
   - `timestamp`
   - `token_count`
   - `ingest_index`
   - `unitization_decision`
3. `formatted_turn` 在 ingest 时立即生成，保持 MemoryAgentBench 的 synthetic dialogue protocol。
4. recent prompt 默认展示 `formatted_turn`，而不是裸 `raw_context`。
5. 本次只做结构重构，不继续改变 flush 后的 regrouping 策略。

当前判断：

- 这一步把“benchmark chunk”与“合成 dialogue turn”拆清楚了
- 后续如果要做 per-turn agentic unitization，应在 `MemoryTurn.unitization_decision` 上落点
- flush 阶段后续应消费 `List[MemoryTurn]`，再决定如何展开为 local units

## 31. 关于移除临时 unitization router 的决定

当前新增决策：

1. 暂停继续推进 `unitization_mode` / `AgenticUnitizationRouter` 这一临时路线。
2. 删除 `AgenticMemory/unitization_router.py`，避免把尚未定型的 agentic routing 抽象继续固化到 runner、trace 和实验参数中。
3. `MemoryTurn` 不再保存 `unitization_decision`。
4. 必须保留已经确认有价值的基础设施：
   - short-term ping-pong buffer
   - `MemoryTurn`
   - ingest 时生成并保存官方 `formatted_turn`
   - recent retrieval 使用 `formatted_turn`
   - flush 阶段消费 `List[MemoryTurn]`
5. 当前 `TopicRegrouper` 只作为 legacy CR regrouping 路径保留，不再被表述为通用 memory evolution 机制。

当前判断：

- 真正值得继续沉淀的是 `MemoryTurn -> sliding window over turns -> List[MemoryUnit]`。
- 未来如果做 agentic decomposition，应输出多个结构化 `MemoryUnit`，而不是让系统先选择一个粗粒度 `unitization_mode`。
- 这次整理的目的不是提出新方法，而是把代码从 CR 过拟合的临时抽象中退出来。

## 32. 关于 MemoryUnit semantic decomposition 的决定

当前新增决策：

1. 保留现有 `MemoryTurn + ping-pong buffer + A-Mem archival + Recent-first retrieval` 流程。
2. 替换当前最脆弱的 `MemoryTurn.raw_context -> sentence/fact split` 路径。
3. 借鉴 SimpleMem 的 semantic structured compression / MemoryEntry 思想，但不照搬其 sliding window、retrieval store 或完整 pipeline。
4. 第一版 decomposition 单位固定为单个完整 `MemoryTurn`：
   - 不做 sliding window
   - 一个 `MemoryTurn` 可以输出多个 `MemoryUnit`
   - `MemoryUnit.content` 必须 self-contained
5. 第一版保留现有 clustering：
   - cluster 输入从 sentence text 改成 `MemoryUnit.content`
   - grouped memory units 继续包装成官方 memorize prompt 后写入 A-Mem
6. 解析失败不 fallback 到 sentence split：
   - 返回空 `MemoryUnit` list
   - 写入 unit trace
   - 避免把新方法和旧 sentence split 变量混在一起

当前判断：

- 这是比 `unitization_mode` 更清晰的通用抽象。
- 该方案可以统一 CR 的 numbered facts 与 LongMemEval/LoCoMo 的自然 dialogue turn。
- 后续需要用小规模实验观察 decomposition 漏事实、幻觉和额外 token 成本。
