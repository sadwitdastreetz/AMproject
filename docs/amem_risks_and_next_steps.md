# A-Mem Risks And Next Steps

## 1. 当前风险与已知偏差

### 1.1 benchmark 对齐曾经不完全

历史上存在过的偏差：

1. memory construction 阶段一开始没有套官方 memorize template
2. 我们额外加了 query-term 生成步骤
3. 某些实验使用了 `4096`，不完全等同于 selective forgetting 主分析的 `512`

当前状态：

- memory construction prompt 已补齐对齐
- query prompt 已对齐
- 但 query-term 生成步骤仍是我们 runner 的自定义部分

### 1.2 结果不能简单视为论文主表严格复现

我们现在的实验更适合表述为：

- 基于官方 benchmark 数据与 prompt discipline 的 A-Mem 近似实现分析

而不是：

- 与论文主表完全 apples-to-apples 的严格复现

### 1.3 多个运行条件并存，后续需避免混淆

已有实验跨越了：

1. `6k / 32k / 262k`
2. `512 / 4096`
3. `gpt-4o-mini / gpt-5.4-mini`
4. `未对齐 memorize prompt / 已对齐 memorize prompt`

后续继续实验时必须明确写清楚配置，不然很容易混淆结论来源。

## 2. 已完成但后续可继续深化的事项

1. 更系统地比较：
   - 对齐前后 memory-construction prompt 的差异
2. 将 trace、retrieval context、final prompt 做统一分析表
3. 补充更多 `MH` 逐题案例

## 3. 现阶段不做的事

根据当前决策，本轮暂停时不继续做：

1. 不继续提出完整新方案
2. 不继续推荐具体新架构
3. 不继续大规模改写 A-Mem

## 4. 后续自然的下一步

当重新恢复项目时，最自然的下一步方向有三种。

### 4.1 更严格 benchmark 对齐

可以做：

1. 评估是否移除 query-term rewrite
2. 更贴近官方 execution shell 再跑一轮

### 4.2 设计最小改造版 A-Mem

目标：

- 不推翻 note-centered memory
- 只补一个最小 conflict-aware layer

### 4.3 构建 failure taxonomy

把错误系统化分成：

1. retrieval miss
2. conflict co-existence
3. old value dominance
4. broken multi-hop chain
5. answer grounding failure

## 5. 恢复工作时优先参考的文件

1. [amem_selective_forgetting_experiment_report.md](C:\Users\ddger\Documents\AMproject\docs\amem_selective_forgetting_experiment_report.md)
2. [amem_experiments_log.md](C:\Users\ddger\Documents\AMproject\docs\amem_experiments_log.md)
3. [amem_findings_and_lessons.md](C:\Users\ddger\Documents\AMproject\docs\amem_findings_and_lessons.md)

## 6. 暂停时的最终状态

当前可以明确认为：

1. 项目已经完成从“想法阶段”到“可运行、可观测、可定位问题”的跨越
2. A-Mem 在 selective forgetting 上的问题已被多次实验和案例分析支持
3. 后续继续推进时，将不再从零开始

