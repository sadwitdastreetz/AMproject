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

## 8. 关于本轮暂停点

当前决策：

- 暂停继续提出改进方案
- 先存档
- 先把已有实验与理解整理成文档基础设施

