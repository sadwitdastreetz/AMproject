# A-Mem Findings And Lessons

## 1. 对 A-Mem 的总体判断

A-Mem 很擅长做：

1. note-centered memory organization
2. local neighborhood evolution
3. semantic linking
4. memory enrichment

但它不擅长做：

1. conflict overwrite
2. current-state maintenance
3. selective forgetting
4. multi-hop chain maintenance

一句话概括：

> A-Mem 解决了“记忆如何组织”，但没有真正解决“冲突记忆如何成为当前有效状态”。

## 2. 从日志看到的本体问题

trace 反复显示：

1. 新 note 写入时，系统会召回旧邻居
2. evolution decision 多是：
   - `STRENGTHEN`
   - `STRENGTHEN_AND_UPDATE`
3. 更新主要作用在：
   - `context`
   - `tags`
4. 很少发生：
   - 旧值失效
   - 新值显式成为当前值

因此：

- A-Mem 做的是 `semantic evolution`
- 不是 `state evolution`

## 3. selective forgetting 的典型问题

### 3.1 冲突值共存

例如：

- `Maria Amalia ... Catholic Church`
- `Maria Amalia ... Church of Greece`

两条冲突事实会共存于 memory 中。

### 3.2 新值没有显式提升

系统不会明确说：

- 这是同一 subject + same relation
- 后者覆盖前者

### 3.3 旧常识 / 旧值仍然很容易主导回答

即使 query prompt 明确要求只依据 memory、不要依据现实世界常识，模型仍会在：

- 检索偏置
- query rewrite 偏置
- 冲突并存上下文

共同作用下，偏向旧值或更熟悉的常识值。

## 4. 时间戳问题

我们确认过：

1. note 有 timestamp
2. prompt 里也会包含 timestamp
3. 但 timestamp 没真正进入：
   - retrieval 排序
   - conflict resolution
   - answering 裁决

因此当前的 timestamp 更像：

- metadata for display

而不是：

- decision signal

## 5. SH 与 MH 的差别

### SH

特点：

- 更容易看到 selective forgetting 本体
- 某些题里正确新值和错误旧值同时被检到
- 模型仍然选旧值

这类题是 selective forgetting 的直接证据。

### MH

特点：

- 问题不只是 conflict resolution
- 还叠加：
  - hop chain retrieval failure
  - wrong second-hop retrieval
  - answer grounding failure

因此 `MH` 的失败更彻底。

## 6. 从具体题目得到的关键教训

### Q19

- 同一主体、同一关系的新旧值都被检到
- 模型选了旧值
- 是最干净的 selective forgetting 案例之一

### Q17

- spouse 新旧值同时在上下文里
- 仍选旧值

### Q18

- `David Copperfield` 的 author 新旧值同时在上下文里
- 旧值 `Charles Dickens` 还受到更强 schema 模式加持

### MH Q4

- 第一跳检到
- 第二跳也检到，但检到的是旧/错误 occupation
- 正确第二跳没进上下文
- 最终模型停在中间实体

## 7. 为什么更强模型没有根本解决问题

切换到 `gpt-5.4-mini` 后：

1. `SH` 有改善
2. `MH` 基本没改善

这说明：

- 更强模型能提升抽取与局部判断
- 但不能自动补齐 memory mechanism 的结构缺口

## 8. 最重要的经验总结

后续任何改进 selective forgetting 的方案，至少要补下面这些层：

1. 冲突检测
2. 当前值维护
3. 旧值历史化或降权
4. 时间参与裁决
5. chain-aware retrieval / reasoning

