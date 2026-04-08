# A-Mem 在 Selective Forgetting / Conflict Resolution 上的实验报告

## 1. 报告目的

本报告总结了我们围绕 A-Mem 在 `MemoryAgentBench` 的 `Conflict_Resolution` 任务上的一系列复现、跑通、日志增强与案例分析工作，目标是回答一个核心问题：

> A-Mem 是否适合作为 selective forgetting / conflict resolution 改进的基础方法？如果它当前存在问题，这些问题具体出在哪里？

结论先行：

1. A-Mem 的记忆组织方式在第一性原理上仍然很有价值，尤其是它的 `note-centered + local evolution + semantic linking` 思路。
2. 但在我们这轮实验里，A-Mem 在 `Selective Forgetting / Conflict Resolution` 上确实表现出明显缺陷。
3. 这些缺陷不是单一来源，而是由以下几个问题叠加造成：
   - 没有显式的 `same subject + same relation + conflicting object` 冲突建模
   - 没有“旧值失效 / 新值生效”的状态更新机制
   - note 虽带时间戳，但时间信息没有真正参与检索排序或冲突裁决
   - 在 multi-hop 场景中，检索和推理更容易退化为“召回一些相关碎片”，而不是形成可执行链路


## 2. 研究背景

我们之所以专门测试 A-Mem 在 selective forgetting 上的表现，是因为：

1. 你的项目当前把 A-Mem 视为重要灵感来源，尤其认可它的 memory organization 方式。
2. 但新的论文 [Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions](https://arxiv.org/html/2507.05257) 明确指出，现有 memory agents 在 `Selective Forgetting` 上存在显著困难，尤其在 multi-hop 场景下表现极差。
3. 因此，我们希望先通过复现实验和详细日志解读，确认 A-Mem 的真实问题边界，再判断后续改进方向。

在这条线程中，我们暂时不关注你自己的新方案是否最终采用 `MemoryItem / SemanticSlot / NoteRevision` 这些形式，而是先把 A-Mem 本身吃透。


## 3. 使用代码与实验对象

本轮工作涉及的仓库与代码：

1. A-Mem 论文复现实验仓库：
   - `AgenticMemory`
2. A-Mem 产品化实现仓库：
   - `A-mem-sys`
3. Selective Forgetting benchmark：
   - `MemoryAgentBench`
   - 数据集：`ai-hyz/MemoryAgentBench`

其中本报告主要基于 `AgenticMemory` 做实验，因为它更贴近论文原型流程，便于观察 A-Mem 的 memory evolution 主线。


## 4. 我们对 A-Mem 代码做过的关键改动

为了让实验真正可跑、可分析，我们做过几类必要改动。

### 4.1 embedding 从本地模型切到 OpenAI API

原论文/原代码默认依赖本地 embedding 模型，如 `all-MiniLM-L6-v2`。为保证当前环境可稳定运行，我们把 embedding 改为：

- `text-embedding-3-small`

这个改动同时应用到：

- `AgenticMemory`
- `A-mem-sys`

并保留了兼容结构。

### 4.2 baseline LLM 切换到 `gpt-5.4-mini`

在后期实验中，我们把基准问答模型与记忆更新模型统一切到：

- `gpt-5.4-mini`

切换时还修复了一个兼容问题：

- GPT-5 系列不接受 `max_tokens`
- 需要改为 `max_completion_tokens`

### 4.3 增加 memory update trace

为了真正观察 A-Mem 的 selective forgetting 缺陷，我们在 `memory_layer_robust.py` 中增加了结构化 JSONL trace 记录器，按每次 `add_note -> process_memory` 输出日志。

当前 trace 事件包括：

- `note_created`
- `neighbor_retrieval`
- `no_neighbors_found`
- `evolution_decision`
- `strengthen_details`
- `neighbor_updates`
- `evolution_complete`
- `evolution_error`
- `note_stored`

这让我们可以追踪：

1. 新 note 提取出了什么 `keywords/context/tags`
2. 检索到了哪些旧邻居
3. LLM 做了什么 evolution 决策
4. 旧 note 的 `context/tags` 是否被改写
5. 最终有哪些 note 被存入检索空间


## 5. 我们对 benchmark 设定的核对

### 5.1 `Conflict_Resolution` 是否按 chunk ingest

我们核对了 `MemoryAgentBench` 论文和代码，确认：

1. `Conflict_Resolution` 的官方设定是 `chunked input`
2. 不是把几百条 fact 逐条单独送入 memory agent
3. benchmark pipeline 会先把整段 context 切成 chunk，再逐 chunk 送入 agent

因此，我们用 A-Mem 复现时采用“逐 chunk ingest”的粒度，与 benchmark 主体设计一致。

### 5.2 `Table 3` 中 selective forgetting 的长度设定

论文 `Table 3` 对 `FactConsolidation-SH / FactConsolidation-MH` 只报了两个主结果列，没有展开所有长度。我们进一步核对了论文和本地配置，确认：

1. `Table 3` 不是各长度平均值
2. 它更接近主实验长度设定下的结果
3. benchmark 配置表明，主实验对应的是 `262k`

### 5.3 关于 chunk size

论文对 `Selective Forgetting` 默认更偏向：

- `chunk_size = 512`

但论文也对部分高成本 memory construction 方法使用更粗粒度的设置。结合你的判断，我们把 A-Mem 视作高消耗 memory construction 方法，因此实验中保留了两类设定：

1. 与 selective forgetting 主设定更贴近的：
   - `chunk_size = 512`
2. 与高成本 memory construction 设定更接近的：
   - `chunk_size = 4096`


## 6. A-Mem 在 LoCoMo / benchmark 中的主线流程理解

A-Mem 在代码里的主线可以概括为：

1. 对话或 context chunk 流式进入系统
2. 每个 chunk 被封装成一个 `MemoryNote`
3. LLM 为其生成：
   - `keywords`
   - `context`
   - `tags`
4. 系统检索已有 memory 邻居
5. LLM 对新 note 与旧 note 的局部关系做 evolution 决策
6. 执行：
   - `STRENGTHEN`
   - `UPDATE_NEIGHBOR`
   - 或 `STRENGTHEN_AND_UPDATE`
7. 将 enriched notes 存入 embedding retriever
8. 问答时先生成 query terms，再检索相关 note，把检索结果拼进 prompt 给 LLM 回答

它的强项在于：

- semantic organization
- local neighborhood evolution
- linked note memory

它的弱项则在这轮 selective forgetting 实验中暴露得很明显：

- 它更新的是 note 的语义解释层
- 而不是事实状态层


## 7. 小规模 smoke 与早期复现

在进入新模型系统实验前，我们已经完成以下工作：

1. `A-mem-sys` 单测跑通
2. `AgenticMemory` 在 LoCoMo 上完成小规模 smoke reproduction
3. `Conflict_Resolution` 在 `6k`、`262k`、不同 chunk size 下完成初步试跑

这些早期结果的总体趋势已经显示：

1. `SH` 明显好于 `MH`
2. `chunk_size=4096` 时问题混杂了粗粒度检索噪声
3. `6k + 512` 比 `262k + 4096` 更适合观察 selective forgetting 本体


## 8. 新模型切换后的正式观察对象

在切换到 `gpt-5.4-mini` 后，我们重点关注：

1. `FactConsolidation_sh_32k + chunk_size=512`
2. `FactConsolidation_mh_32k + chunk_size=512`

并且保留：

- memory update trace
- retrieval context
- final prompt

以便逐条解释错误来源。

相关结果文件：

- `SH` 结果：`AgenticMemory/cr_sh_32k_20q_gpt54mini_chunk512_trace_results.json`
- `SH` trace：`AgenticMemory/cr_sh_32k_20q_gpt54mini_chunk512_trace.jsonl`
- `MH` 结果：`AgenticMemory/cr_mh_32k_20q_gpt54mini_chunk512_trace_results.json`
- `MH` trace：`AgenticMemory/cr_mh_32k_20q_gpt54mini_chunk512_trace.jsonl`


## 9. 新模型结果概览

### 9.1 SH

`FactConsolidation_sh_32k + chunk_size=512`

- `exact_match = 0.45`
- `f1 = 0.515`
- 写入了 `65` 个 chunk note

这说明更强模型确实提升了单跳抽取能力。

### 9.2 MH

`FactConsolidation_mh_32k + chunk_size=512`

- `exact_match = 0.00`
- `f1 = 0.0167`
- 同样写入了 `65` 个 chunk note

这说明更强模型并没有解决 A-Mem 在 multi-hop selective forgetting 上的结构性问题。


## 10. 从 update trace 看 A-Mem 的核心问题

无论 `SH` 还是 `MH`，更新日志的宏观模式都非常一致：

1. 多数新 note 都会触发邻居检索
2. evolution decision 绝大多数是：
   - `STRENGTHEN`
   - `STRENGTHEN_AND_UPDATE`
3. `neighbor_updates` 主要改的是旧 note 的：
   - `context`
   - `tags`
4. 很少看到真正意义上的事实冲突裁决

这说明当前 A-Mem 的 memory evolution 更像：

- 强化语义联系
- 丰富描述
- 局部重解释历史 note

而不是：

- 识别“同一主体 + 同一关系 + 冲突 object”
- 将旧值标记为 obsolete
- 将新值提升为当前有效状态

这正是 selective forgetting 失败的结构性根源。


## 11. SH 的详细问题分析

SH 的表现比 MH 好很多，但它已经足够暴露 selective forgetting 问题。

### 11.1 三类 SH 错误

结合 retrieval context 与逐题检查，SH 错题大致分成三类：

1. 真正的 selective forgetting 失败
2. 检索把正确答案 token 带回来了，但不是通过正确事实链
3. 纯检索失败：正确更新值没有进入上下文

下面重点分析几题最重要的样本。

### 11.2 Q19：Maria Amalia 的 religion

问题：

- `Which religion is Maria Amalia of Naples and Sicily affiliated with?`

官方正确答案：

- `Church of Greece`

模型预测：

- `Catholic Church`

原始 benchmark 中这组冲突的顺序是：

- `1662. Maria Amalia of Naples and Sicily is affiliated with the religion of Catholic Church.`
- `2115. Maria Amalia of Naples and Sicily is affiliated with the religion of Church of Greece.`

所以：

- 旧值：`Catholic Church`
- 新值：`Church of Greece`

而在我们这次问答的 `raw_context` 里，两条都出现了：

- `Maria Amalia of Naples and Sicily is affiliated with the religion of Church of Greece.`
- `Maria Amalia of Naples and Sicily is affiliated with the religion of Catholic Church.`

这题是最干净的 selective forgetting 证据之一，因为：

1. 正确新值检到了
2. 错误旧值也检到了
3. subject 和 relation 完全一致
4. 模型最终仍选择旧值

这说明失败不在“没检到”，而在于：

- A-Mem 没有给出“这组冲突中谁是当前有效值”的结构性偏好
- LLM 在冲突并存的上下文里选择了更熟悉的旧值

### 11.3 Q17：Charles Darwin 的 spouse

问题：

- `Who is Charles Darwin married to?`

官方正确答案：

- `Amala Paul`

模型预测：

- `Emma Darwin`

这题一开始我们曾误以为“只检到了答案词，但没检到正确事实链”，但复查后确认：

检索上下文里实际上同时出现了：

- `Charles Darwin is married to Emma Darwin.`
- `Charles Darwin is married to Amala Paul.`
- 以及无关但干扰性较强的：
  - `Amala Paul is a citizen of Belgium.`

因此这题更准确地说也是强 selective forgetting 证据：

1. 正确 spouse 事实在上下文中
2. 错误 spouse 事实也在上下文中
3. 模型选择了更熟悉、更像常识的旧值 `Emma Darwin`

此外，这题的 query terms 还出现了明显的旧常识偏置：

- `Charles Darwin, married to, wife, Emma Wedgwood, marriage`

这意味着在问答前的 query generation 阶段，模型就已经朝旧值方向偏移。

### 11.4 Q18：David Copperfield 的 author

问题：

- `Who is the author of David Copperfield?`

官方正确答案：

- `Charles Darwin`

模型预测：

- `Charles Dickens`

原始 benchmark 中这组冲突顺序是：

- `753. The author of David Copperfield is Charles Dickens.`
- `2203. The author of David Copperfield is Charles Darwin.`

所以：

- 旧值：`Charles Dickens`
- 新值：`Charles Darwin`

这题的检索上下文中同时出现了：

- `The author of David Copperfield is Charles Dickens.`
- `The author of David Copperfield is Charles Darwin.`

除此之外，还出现了多条和 `Charles Dickens` 同 schema 的 author 句，例如：

- `The author of Bleak House is Charles Dickens.`

这就是我们所说的“被 schema 带偏”：

1. 问题 schema 是 `The author of X is Y`
2. 检索上下文里存在多个类似 author 模板
3. `Charles Dickens` 既是旧冲突值，又在其他 author 句中高频出现
4. LLM 最终被局部模式与常识锚点双重吸引，选择了 `Charles Dickens`

因此这题同样属于：

- 冲突值并存
- 新值没有被显式提升
- 旧值在回答阶段占优势

### 11.5 Q5：United Kingdom 的 capital

问题：

- `What is the capital of United Kingdom?`

官方正确答案：

- `Rupnagar`

模型预测：

- `London`

原始 benchmark 中这组冲突顺序是：

- `502. The capital of United Kingdom is London.`
- `819. The capital of United Kingdom is Rupnagar.`

所以：

- 旧值：`London`
- 新值：`Rupnagar`

但在这次问答的检索上下文里：

- `The capital of United Kingdom is London.` 出现了
- `Rupnagar` 没出现

所以这题不能算“明明检到了新值却还选旧值”。它更接近：

1. 正确新值没有进入 retrieval context
2. 错误旧值 `London` 被直接召回
3. 模型自然输出 `London`

这题说明：

- selective forgetting benchmark 的样本结构本身没问题
- 但 A-Mem 的检索阶段已经先输了一步

### 11.6 Q10：Edmund Burke 的 citizenship

问题：

- `What is the country of citizenship of Edmund Burke?`

官方正确答案：

- `Kingdom of Ireland`

模型预测：

- `United Kingdom`

这题的检索上下文里：

- `Edmund Burke` 没出现
- `Kingdom of Ireland` 没出现
- 出现的是许多无关的 `citizen of United Kingdom` 一类句子

因此这题更纯粹是：

- subject-level retrieval failure

它不能作为 selective forgetting 的直接证据，但能说明：

- 在长上下文下，即使是单跳问题，A-Mem 的 retrieval 也会发生严重泛化偏移


## 12. SH 的中间结论

`SH` 的结果说明：

1. 更强模型可以提升单跳抽取能力
2. 但在若干关键样本中，A-Mem 已经明确暴露了 selective forgetting 问题
3. 这些问题包括：
   - 新旧冲突值并存时，没有显式 winner
   - query generation 容易被旧常识带偏
   - 检索粒度和检索偏置仍会让正确更新值丢失


## 13. MH 的详细问题分析

MH 比 SH 崩得更彻底，但这不意味着它只是“更难一点”。结合日志看，MH 的失败结构更深。

### 13.1 MH 的核心问题

MH 不只是：

- 冲突值并存

它还额外要求：

- 正确找到 hop1 的实体
- 再找到 hop2 的更新值
- 必要时还要继续 hop3

在当前 A-Mem 中，这件事往往会退化成：

- 召回一堆看起来相关的 note
- 但没有显式链路结构
- 也没有对冲突状态做清晰管理

### 13.2 Q4：PLO chairperson 的 occupation

问题：

- `What is the occupation of the chairperson of the Palestine Liberation Organization?`

官方正确答案：

- `basketball player`

模型预测：

- `Mahmoud Abbas`

我们对这题的理解经历了一个修正。

一开始的粗看会觉得：

- 检到了第一跳：
  - `The chairperson of Palestine Liberation Organization is Mahmoud Abbas.`
- 没继续走第二跳

但进一步核对 `raw_context` 和 benchmark 原始数据后，真实情况更细：

检索上下文中出现了：

- `The chairperson of Palestine Liberation Organization is Mahmoud Abbas.`
- `Mahmoud Abbas works in the field of politician.`

而 benchmark 的官方正确答案是：

- `basketball player`

这说明在原始 benchmark 里，应该还存在一条后更新的冲突事实：

- `Mahmoud Abbas works in the field of basketball player.`

但它没有被这次问答的检索带回来。

因此，这题不能简单说成“没走第二跳”。更准确地说是：

1. hop1 检到了
2. hop2 也检到了，但检到的是旧/错误值：
   - `politician`
3. 正确 hop2：
   - `basketball player`
   没检到
4. 模型最终甚至没有稳定输出 `politician`
5. 而是停在中间实体 `Mahmoud Abbas`

这题体现的是三层叠加失败：

- multi-hop retrieval failure
- selective forgetting failure
- answer grounding failure

### 13.3 MH 的一般性失败模式

结合前 20 题的检查，MH 错题通常表现为：

1. 只召回第一跳，不召回后续 hop
2. 召回了后续 hop，但召回的是错误旧值
3. 召回了若干相关碎片，但没有显式链路组织
4. LLM 最终停在中间实体，或者输出某个错误 hop

所以 MH 相比 SH 并不是“同样的问题，只是更难”，而是：

- SH 暴露的是 conflict resolution 不足
- MH 暴露的是 conflict resolution 不足 + chain composition 不足


## 14. 关于 note 的 timestamp：有，但没有被真正用起来

这是我们对话中一个非常关键的洞察。

### 14.1 timestamp 是否存在

是的，A-Mem 当前实现中的 note 确实带有 `timestamp`。

在我们的 benchmark runner 中，每个 chunk ingest 时传入：

- `time=f"chunk_{chunk_idx:04d}"`

因此 note 会带类似：

- `chunk_0003`
- `chunk_0059`

这类时间戳。

### 14.2 timestamp 是否进入问答 prompt

是的，进入了。

在 `find_related_memories()` 返回的上下文里，每条 memory 都会包含：

- `talk start time:<timestamp>`

然后这个 `raw_context` 会被原样拼入最终问答 prompt。

因此在技术上说：

- timestamp 是 note 的一部分信息
- prompt 中也确实包含 timestamp

### 14.3 为什么 timestamp 没有帮助 selective forgetting

因为当前实现中：

1. timestamp 只是普通文本字段
2. 检索并不会按时间优先级排序
3. 系统也不会在同 subject-relation 冲突时做“优先 newer note”裁决
4. prompt 中也没有明确指令要求 LLM 根据 timestamp 选择最新事实

所以对于：

- `Maria Amalia ... Catholic Church`
- `Maria Amalia ... Church of Greece`

真实发生的是：

1. 两条 note 都可能被召回
2. prompt 中也都带着各自的 `talk start time`
3. 但模型并不会自动把这视为“后者覆盖前者”

一句话说：

- timestamp 在 prompt 里
- 但没有被系统性地用于 reasoning


## 15. 本轮实验对 A-Mem 的最终判断

结合前面的探索、跑通、trace、新模型切换后的逐条日志解读，以及这几轮详尽解释，我们对 A-Mem 可以给出如下判断。

### 15.1 A-Mem 的优点没有被否定

A-Mem 仍然有非常强的研究价值：

1. 它不是简单的向量记忆库
2. 它强调 note 的富语义构造
3. 它通过局部邻居和 evolution 形成动态 memory network
4. 它在记忆组织这个层面，非常符合第一性原理直觉

因此，把 A-Mem 作为改进 selective forgetting 的出发点，方向本身是合理的。

### 15.2 但它当前在 selective forgetting 上存在明确缺口

本轮实验确认的问题包括：

1. 缺乏显式冲突检测
   - 系统不会系统地识别：
     - same subject
     - same relation
     - different object

2. 缺乏当前值 / 失效值机制
   - 新值进入后，旧值通常不会被降权、失效或覆盖

3. timestamp 没有参与决策
   - 虽然记录了时间信息，但并未真正用于检索和回答裁决

4. 更新发生在解释层，而不是事实状态层
   - 当前的 `STRENGTHEN` / `UPDATE_NEIGHBOR` 更像语义 enrich
   - 不是 state overwrite

5. 在 MH 中缺乏可执行链路维护
   - 检索拿回的是相关碎片
   - 不是受约束的 hop chain

### 15.3 新模型并没有改变结构性结论

切换到 `gpt-5.4-mini` 后：

1. `SH` 有提升
2. `MH` 依旧非常差

这说明更强的推理/抽取模型可以改善部分回答质量，但没有改变底层 memory mechanism 的结构性缺陷。


## 16. 对后续改进方向的启示

本报告不直接定义你的最终方案形式，但已经足够说明后续改进至少需要考虑以下能力：

1. 冲突识别
   - 在 note 更新时显式识别冲突事实

2. 当前值管理
   - 对同一 subject-relation 维护当前有效 object

3. 过时记忆处理
   - 旧值不一定要删掉，但需要有可解释的降权或历史化表示

4. 时间真正进入裁决逻辑
   - 不能只作为展示文本存在

5. 多跳链路维护
   - 不仅要存 note，还要支持在 retrieval / answering 时形成可执行推理链


## 17. 总结

如果只用一句话概括本轮实验：

> A-Mem 很擅长把记忆组织成语义网络，但它目前不会可靠地把“新事实替代旧事实”管理成状态，因此在 selective forgetting，尤其是 multi-hop selective forgetting 上，会表现出系统性不足。

这也是为什么：

1. 它依然值得作为灵感来源
2. 但不能直接拿来当最终 memory mechanism
3. 后续必须补上“冲突解析 + 当前状态管理 + 时间参与决策 + 多跳链路维护”这几层能力

