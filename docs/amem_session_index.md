# A-Mem / MemoryAgentBench Session Index

## 状态

本轮线程已暂停归档。当前工作已经为后续继续研究 A-Mem 在 selective forgetting / conflict resolution 上的问题打下了可复用的基础。

本组文档用于保存以下内容：

1. 已完成实验与结果
2. 关键决策与实验规范
3. 代码改动与运行方式
4. 主要观察、结论与教训
5. 风险、偏差与后续待办

## 文档目录

1. [A-Mem Experiments Log](C:\Users\ddger\Documents\AMproject\docs\amem_experiments_log.md)
   - 实验尝试、运行设定、结果文件、关键指标

2. [A-Mem Key Decisions](C:\Users\ddger\Documents\AMproject\docs\amem_key_decisions.md)
   - 重要决策、实验规范、参数选择、与 benchmark 的对齐处理

3. [A-Mem Code Changes](C:\Users\ddger\Documents\AMproject\docs\amem_code_changes.md)
   - 改过哪些代码、为什么改、改动影响什么

4. [A-Mem Findings And Lessons](C:\Users\ddger\Documents\AMproject\docs\amem_findings_and_lessons.md)
   - 对 A-Mem 方法本体的理解、问题定位、案例层面观察、经验总结

5. [A-Mem Risks And Next Steps](C:\Users\ddger\Documents\AMproject\docs\amem_risks_and_next_steps.md)
   - 当前风险、已知偏差、未完成事项、下一步建议

6. [A-Mem Selective Forgetting Experiment Report](C:\Users\ddger\Documents\AMproject\docs\amem_selective_forgetting_experiment_report.md)
   - 已产出的正式报告，偏长篇总结

## 本轮线程核心结论

1. A-Mem 的 `note-centered + local evolution + semantic linking` 依然是很强的灵感来源。
2. 但在 `Selective Forgetting / Conflict Resolution` 上，A-Mem 已被我们反复验证存在明显结构性问题。
3. 问题不只是检索，而是：
   - 冲突事实缺乏显式建模
   - 没有当前值 / 失效值机制
   - 时间戳存在但没有真正参与裁决
   - multi-hop 场景缺乏可执行链路维护
4. 即使切换到 `gpt-5.4-mini`，并且进一步对齐 benchmark 的 memory construction prompt，`MH` 结果仍然接近失效，说明问题主要不在 prompt 偏差，而在 A-Mem 本体结构。

