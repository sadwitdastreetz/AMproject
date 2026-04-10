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
