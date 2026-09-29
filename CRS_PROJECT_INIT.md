# CRS 项目初始化说明

> 目标：基于 Cairn 的公开设计与实现，快速建立一个可运行、可评测、可追踪、可持续迭代的 CTF-oriented CRS（Cyber Reasoning System）研究工程。
>
> 当前阶段重点不是“重新实现一个 Cairn”，也不是立即大规模修改架构，而是先建立可靠 baseline、trace、evaluator 与 failure-driven development 流程，再根据真实困难任务暴露出的瓶颈进行机制修改。

---

## 1. 项目背景

此前项目主要围绕 S / M / P / T / B 等多 Agent 协调机制进行代码审计实验。该路线暂时搁置，主要原因包括：

1. 当前代码审计 benchmark 中高难度、能够充分区分不同协调机制的任务不足；
2. 多次实验表明，简单任务容易被强模型直接解决，导致架构差异难以显现；
3. 实验过程中相当多精力消耗在 completion semantics、lease、finalization、result sync、task closure 等 runtime / harness 问题，而不是实际安全能力；
4. 目前更希望构建一个能够真正参与 CTF / 漏洞研究类任务的 CRS，并通过真实困难任务反向推动架构设计。

因此，新的开发路线改为：

**真实困难任务 → 失败分析 → 提出架构假设 → 修改 Cairn → 小规模验证 → 大 benchmark 泛化验证。**

---

## 2. 当前总体策略

### 2.1 为什么选择 Cairn 作为起点

Cairn 目前是一个适合参考和修改的基础系统，原因包括：

- 采用 Blackboard / Fact–Intent Graph 思路；
- worker 之间通过共享状态实现间接协作；
- 已处理 worker 生命周期、任务分配、claim / heartbeat / release 等 runtime 问题；
- 已存在 Dispatcher / Worker / Server 等相对清晰的边界；
- 适合 CTF 这类“从已知状态出发，在未知搜索空间中寻找 goal”的任务；
- 可以避免项目初期重新实现大量低研究价值的基础设施。

当前策略不是长期维护一个无限魔改的 Cairn fork，而是分阶段推进：

### V0：Cairn Baseline
尽量保持原架构，先建立完整实验基础设施并测出 baseline。

### V1：Research Fork
根据困难任务中的共性失败模式，一次只修改一个主要机制。

### V2：独立 CRS Kernel
当核心数据模型、协调逻辑、worker 生命周期等已经明显偏离 Cairn 时，再重建自己的 CRS 核心。

---

## 3. 当前研究问题

项目现阶段不预先假设“某种架构一定更好”。

核心问题是：

> 在相同模型、相同工具、相同预算和相同任务条件下，哪些协调、状态管理、上下文管理、调度、验证和终止机制能够让 CRS 更高概率、更低成本、更稳定地获得有效 flag？

优先关注的潜在瓶颈包括：

- 重复探索；
- Blackboard 中已有有效 Fact，但其他 worker 不采用；
- Fact → Intent 转换效率低；
- 错误 Fact 被过早当成事实传播；
- Intent 数量膨胀；
- 后期 Blackboard 过大导致 context tax；
- worker 长时间停留在低价值方向；
- 缺乏验证与 evidence tracking；
- premature termination；
- tool / model failure 后恢复能力不足；
- worker 间探索缺乏多样性；
- 已产生的 artifact 没有被其他 worker有效复用。

这些仅作为候选问题，不应在看到真实失败 trace 之前预设结论。

---

## 4. Failure-Driven Development

本项目采用 **failure-driven development**。

开发循环固定为：

```text
1. 在困难诊断题上运行 Cairn baseline
            ↓
2. 保存完整 trace
            ↓
3. 分析失败原因
            ↓
4. 对多个任务进行 failure classification
            ↓
5. 寻找跨任务重复出现的机制瓶颈
            ↓
6. 提出 architecture hypothesis
            ↓
7. 一次只修改一个主要机制
            ↓
8. 重跑 Diagnostic Set
            ↓
9. 若改善，则运行 Development Set
            ↓
10. 若仍改善，则运行完整公开 benchmark
            ↓
11. 版本冻结后，再运行 sealed holdout
```

### 重要原则

困难任务可以告诉我们：

> “系统在哪里失败。”

但不能直接告诉我们：

> “应该为这道题增加什么特定规则。”

例如：

不应因为某题漏掉 JWT cracking，就加入 `if JWT: crack`。

如果多个任务都出现：

- 关键 Fact 已经产生；
- 后续 worker 没有检查；
- 没有产生验证 Intent；
- 最终超时；

则可以形成一个架构级假设：

> 当前系统存在 foreign Fact adoption / follow-up scheduling 问题。

这种修改才属于目标范围。

---

## 5. 评测集设计

不要使用单一 benchmark 同时承担开发、调参和最终评测。

建议至少划分四层。

### 5.1 Diagnostic Set

目的：**暴露系统机制瓶颈。**

建议规模：

- 约 5–10 个任务；
- 高难度；
- 允许频繁运行；
- 必须保留完整 trace；
- 最好不是所有 agent 都完全无法推进的任务。

优先选择：

- Cairn baseline 成功率约 20%–80% 的任务；
- 或最终未 solve，但能稳定推进较长路径的任务；
- 强单 Agent 偶尔可解，但 Cairn 仍存在不稳定性的任务。

不优先选择：

- 所有当前模型几乎 0% 成功；
- 失败主要来自环境损坏；
- 依赖非常特定冷知识、无法体现架构差异的任务。

---

### 5.2 Development Set

目的：判断某个修改是否只解决了少数诊断题。

建议：

- 10–20 个任务；
- 类型尽量多样；
- 与 Diagnostic Set 不完全重合；
- 修改在 Diagnostic Set 上明显有效后再运行。

---

### 5.3 Broad Public Benchmark

目的：验证总体能力、效率和泛化变化。

> 2026-09 已裁决(V1):主 benchmark 为 **NYU CTF Bench**(官方 test split,200 题,tag v20250206);
> Cybench 降级为 Diagnostic/Development 素材(前沿已饱和、仅 40 题、pwn 只有 2 题);
> CyberGym 不采用(非 flag 型、Level-1 近饱和、基础设施过重)。
> 详见 `docs/benchmarks/BENCHMARK_SELECTION_V1.md` 与配套 task registry。

公开 benchmark 不应在每个微小修改后全部重跑。

---

### 5.4 Sealed Holdout

目的：最终检查是否产生 benchmark overfitting。

要求：

- 开发阶段不根据这些任务修改系统；
- 尽量使用近期、未被频繁公开讨论、或自行重新封装的 CTF challenge；
- 只在形成候选稳定版本后运行。

---

## 6. 核心评测原则

比较任何两个版本时，必须尽量固定：

- 模型；
- 模型参数；
- worker 数量；
- 工具权限；
- 容器环境；
- wall-clock budget；
- LLM call budget；
- token / cost budget；
- prompt 基础模板；
- evaluator；
- challenge 版本。

不得用：

```text
v0：30 分钟 / 低预算
v1：90 分钟 / 高预算
```

然后直接宣称 v1 架构更强。

---

## 7. Primary Metrics

### 7.1 Fixed-Budget Solve Rate

最重要指标：

```text
SR@B = 固定预算 B 内成功获得有效 flag 的任务比例
```

至少记录：

- task-level solved / unsolved；
- seed / repetition；
- solve probability；
- valid run / invalid run。

---

### 7.2 Solve-vs-Budget Curve

不要只看单个预算点。

建议记录：

- success vs time；
- success vs tokens；
- success vs cost；
- success vs LLM calls。

例如：

```text
5 min
10 min
20 min
30 min
```

或：

```text
$0.5
$1
$2
$4
```

后续可计算 AUC，用于判断系统是否“更快达到相同能力”。

---

### 7.3 Subtask / Partial Progress

对没有拿到 flag 的任务，也要尽可能记录推进程度。

如果 benchmark 自带 subtask，应保存：

- 完成了哪些 subtask；
- 到达哪一关键攻击阶段；
- 是否获得关键中间 artifact；
- 是否定位到真实漏洞点；
- 是否生成可验证 exploit。

避免出现：

```text
v0 = unsolved
v1 = unsolved
```

就认为两者完全相同。

---

## 8. Efficiency Metrics

至少记录：

- `tokens_total`
- `tokens_to_flag`
- `cost_total`
- `cost_to_flag`
- `llm_calls`
- `tool_calls`
- `wall_time`
- `time_to_flag`
- `worker_active_time`
- `worker_idle_time`

可派生：

```text
cost_per_solved
tokens_per_solved
calls_per_solved
```

但效率指标不能单独覆盖 capability。

优先级始终是：

**能力 → 效率 → 协作解释 → 稳定性。**

---

## 9. Coordination Metrics

这些指标用于解释“为什么变好或变差”。

### 9.1 Duplicate Work Rate

衡量不同 worker 是否重复探索相同方向。

候选观测对象：

- 相同 endpoint；
- 相同 file / function；
- 相同 exploit hypothesis；
- 相同 tool action；
- 相同 Intent；
- 高度相似的 reasoning / artifact。

第一版不必追求完美自动分类，可以先通过 trace + 简单规则统计。

---

### 9.2 Foreign Fact Reuse

需要区分：

```text
visibility
    ↓
inspection
    ↓
relevance recognition
    ↓
follow-up
    ↓
adoption
```

建议记录：

- Fact 创建者；
- 哪些 foreign worker 看到了该 Fact；
- 哪些 worker 实际引用；
- 是否产生后续 Intent；
- 是否读取关联 artifact；
- 是否用于 exploit / verification；
- 是否进入最终成功路径。

候选指标：

```text
foreign_fact_seen_rate
foreign_fact_inspection_rate
foreign_fact_reuse_rate
foreign_fact_success_path_rate
```

---

### 9.3 Productive Intent Rate

对完成的 Intent 分类：

```text
productive_positive
productive_negative
duplicate
invalid
abandoned
timeout
```

其中 productive_negative 表示排除了一个真实候选路径，也属于有效贡献。

---

### 9.4 Intent Latency

记录：

```text
created → claimed
claimed → completed
completed → reused
```

用于观察 Blackboard 是否只是日志系统，还是能够快速改变后续搜索行为。

---

### 9.5 Exploration Diversity

第一版可记录：

- unique files touched；
- unique functions inspected；
- unique endpoints tested；
- unique attack hypotheses；
- worker 间路径重叠率。

后续再考虑 embedding / taxonomy 等更复杂方法。

---

### 9.6 Blackboard Context Tax

至少保存：

- Fact 数量；
- Intent 数量；
- edge 数量；
- graph 序列化长度；
- 注入模型的实际 token；
- 被引用 / 被使用的有效 Fact 数量。

目标是能够回答：

> Blackboard 越来越大后，共享状态的收益是否开始低于上下文成本？

---

## 10. Reliability Metrics

必须严格区分：

```text
SOLVED
UNSOLVED
RUNTIME_INVALID
```

RUNTIME_INVALID 建议继续细分：

```text
provider_failure
worker_crash
dispatcher_crash
container_failure
protocol_failure
evaluator_failure
timeout_infrastructure
```

另外记录：

- stuck Intent；
- unreleased Intent；
- worker starvation；
- infinite loop；
- invalid flag submission；
- protocol violation；
- duplicate completion；
- deadlock；
- retry count。

架构失败不能和 provider / infrastructure failure 混为一类。

---

## 11. Failure Taxonomy

项目应维护一个独立、持续扩展的 failure taxonomy。

第一版可以从以下类别开始：

```text
F01 duplicated_exploration
F02 foreign_fact_not_adopted
F03 wrong_fact_propagation
F04 intent_explosion
F05 context_overload
F06 premature_termination
F07 insufficient_verification
F08 worker_starvation
F09 local_optimum
F10 tool_failure_recovery
F11 artifact_not_reused
F12 search_diversity_collapse
F13 invalid_or_weak_evidence
F14 budget_misallocation
```

注意：

- taxonomy 是分析工具，不是强制分类框架；
- 新 trace 出现无法解释的失败时，应允许增加类别；
- 同一任务可以属于多个 failure type；
- 尽量保存具体证据，而不是只打标签。

---

## 12. Trace 设计要求

第一阶段最重要的工程资产不是某个新架构，而是 **完整、可离线分析的事件流**。

建议每个 run 至少保存：

```text
runs/
  <run_id>/
    manifest.json
    result.json
    metrics.json
    events.jsonl
    graph_snapshot.json
    agents/
      worker_001/
      worker_002/
      ...
    artifacts/
    evaluator/
```

### manifest.json

至少冻结：

```text
task_id
task_hash / version
system_version
git_commit
model
model_parameters
worker_count
budget
timeout
tool_permissions
container_image
prompt_hash
evaluator_version
random_seed
```

### events.jsonl

建议所有核心行为统一进入 event log：

```text
run_started
worker_started
worker_stopped
llm_call_started
llm_call_completed
tool_call_started
tool_call_completed
fact_created
fact_read
fact_referenced
intent_created
intent_claimed
intent_completed
intent_abandoned
artifact_created
artifact_read
flag_candidate
flag_submitted
flag_accepted
runtime_error
budget_exhausted
run_finished
```

事件应包含：

```text
timestamp
worker_id
event_id
parent_event_id
task_id
related_fact_ids
related_intent_ids
related_artifact_ids
token_usage
cost
duration
```

只要原始 trace 完整，很多未来指标都可以离线重算。

---

## 13. Artifact Store

CTF 任务中不应把大段原始输出全部塞进 Fact。

建议尽早把 Fact 和 Artifact 区分：

```text
Fact
├── concise summary
├── producer
├── evidence_refs[]
├── related_intents[]
└── timestamps

Artifact
├── command output
├── exploit script
├── binary
├── pcap
├── source snippet
├── scan result
├── screenshot
└── generated payload
```

第一阶段可以先实现简单文件引用，不需要立即设计复杂 artifact graph。

---

## 14. 什么时候继续基于 Cairn，什么时候脱离

如果修改主要属于：

- prompt；
- evaluator；
- trace；
- artifact storage；
- worker adapter；
- context retrieval；
- scheduler 小改；
- verifier 小改；

优先继续在 Cairn research fork 上实验。

当开始同时出现以下情况时，再考虑独立 CRS kernel：

- Fact / Intent 数据模型根本变化；
- Dispatcher 不再是主要协调中心；
- worker 生命周期发生本质变化；
- 引入 planner / verifier / exploiter 等不同 agent 类型；
- Blackboard 被拆成多层 memory；
- P2P communication 成为核心机制；
- 任务执行不再符合原 Cairn 的 bootstrap / reason / explore 模型；
- 继续兼容 Cairn 已经产生大量特殊分支。

脱离 Cairn 的判断标准不是代码改了多少行，而是：

> 是否已经破坏 Cairn 的核心 invariants。

---

## 15. Agent 初始化阶段任务

### Phase 0：熟悉 Cairn

Agent 首先应完成代码阅读，不要立即修改核心逻辑。

需要输出：

1. 当前仓库目录结构；
2. Server / Dispatcher / Worker 的实现位置；
3. Fact / Intent 数据结构；
4. worker 生命周期；
5. task claim / heartbeat / release 语义；
6. LLM adapter；
7. tool execution；
8. container / local execution；
9. termination / timeout；
10. 现有日志与测试；
11. 哪些模块适合插入 instrumentation；
12. 哪些行为属于必须冻结的 baseline semantics。

产物建议：

```text
docs/architecture/CAIRN_BASELINE_ARCHITECTURE.md
```

---

### Phase 1：冻结 Baseline Contract

建立 baseline contract，明确：

```text
哪些东西当前绝对不能改
哪些东西允许增加 instrumentation
哪些东西允许增加 evaluator
哪些东西允许增加 artifact logging
```

应生成：

```text
docs/experiments/BASELINE_CONTRACT.md
```

Baseline 阶段原则：

**只允许 observability modification，不允许 capability modification。**

例如：

允许：

- event logging；
- token logging；
- cost logging；
- run manifest；
- graph snapshot；
- artifact capture；
- deterministic evaluator；
- regression tests。

禁止：

- 修改 worker prompt；
- 修改 scheduling；
- 修改 Fact / Intent semantics；
- 新增 verifier；
- 修改 termination；
- 修改 worker 数；
- 增加 task-specific heuristic。

---

### Phase 2：实现 Experiment Harness

目标：

一条命令能够运行：

```text
system version
+
task
+
model
+
budget
+
seed
```

并产生完整 run directory。

建议接口类似：

```bash
python -m experiments.run \
  --system cairn-baseline \
  --task <task_id> \
  --model <model_id> \
  --workers 4 \
  --budget <...> \
  --seed <...>
```

实际命令形式可以根据 Cairn 工程结构调整，不必强制使用该示例。

---

### Phase 3：实现 Evaluator

第一版 evaluator 至少输出：

```text
validity
solved
time_to_flag
tokens_total
tokens_to_flag
llm_calls
tool_calls
cost_total
runtime_failures
facts_created
intents_created
intents_completed
intents_abandoned
artifacts_created
```

并为后续 coordination metric 留出原始数据。

---

### Phase 4：选择 Diagnostic Set

不要立即修改架构。

先选 5–10 个高难度、具有诊断价值的 CTF task。

每题至少运行多次。

目标不是立即追求高 solve rate，而是生成能够分析的失败 trace。

输出：

```text
docs/experiments/DIAGNOSTIC_SET_V1.md
```

需要记录：

- 选题来源；
- 类型；
- 估计难度；
- baseline 表现；
- 是否存在 subtask；
- 是否适合自动 evaluator；
- 为什么具有诊断价值。

---

### Phase 5：运行 Baseline

完成：

```text
Diagnostic Set × multiple seeds
```

然后产生：

```text
docs/experiments/CAIRN_BASELINE_REPORT_V1.md
```

报告中必须区分：

```text
task failure
model failure
runtime failure
provider failure
evaluation failure
```

并总结：

- recurring failure patterns；
- coordination bottlenecks；
- context / budget bottlenecks；
- artifact reuse；
- duplicate exploration；
- promising architecture hypotheses。

---

## 16. 第一轮修改的准入条件

在 baseline trace 不充分之前，不允许进入 capability modification。

一个修改进入实验，至少满足：

### 条件 A
在多个 run 中重复出现同一失败模式。

### 条件 B
失败模式至少影响两个不同 task，或有充分理由认为它属于系统级机制。

### 条件 C
修改能够写成明确假设，例如：

> 如果增加 foreign Fact prioritization，则关键 Fact 被其他 worker 后续使用的比例应提高，并减少重复搜索。

### 条件 D
存在至少一个直接中间指标用于验证机制是否真的发生改变。

### 条件 E
修改不引入 task-specific attack recipe。

---

## 17. 修改实验模板

每个 architecture modification 应建立独立实验说明：

```text
experiment_id
baseline_version
modified_version
hypothesis
target_failure_types
changed_components
frozen_components
diagnostic_tasks
budget
seeds
primary_metrics
mechanism_metrics
acceptance_criteria
rollback_condition
```

示例：

```text
Hypothesis:
Foreign Fact adoption is too low.

Modification:
Add relevance-aware Fact prioritization.

Expected mechanism change:
foreign_fact_reuse_rate ↑
duplicate_work_rate ↓

Expected outcome:
SR@B ↑ or solve-vs-budget AUC ↑

Frozen:
model
workers
budget
tools
evaluator
task set
```

---

## 18. 不使用单一综合总分

当前不设计类似：

```text
score =
0.5 * solve_rate
+ 0.2 * cost
+ 0.1 * reuse
+ ...
```

这种分数中的权重过于主观。

采用分层判断：

```text
Capability Gate
    ↓
Efficiency Gate
    ↓
Coordination Diagnosis
    ↓
Reliability Gate
```

一个修改可以被描述为：

- capability improvement；
- efficiency improvement；
- coordination improvement；
- reliability improvement；

不要求所有维度同时上升。

---

## 19. 防止 Benchmark Overfitting

必须遵守：

1. 不针对单题加入 exploit recipe；
2. 不因为某题漏掉某具体攻击技术就增加关键词规则；
3. 只对跨任务重复出现的系统性失败做架构修改；
4. Diagnostic Set 可以高频运行；
5. Development Set 低频运行；
6. Broad Benchmark 仅在候选修改通过前两层后运行；
7. Sealed Holdout 在稳定版本冻结后运行；
8. 公开 benchmark 的结果不能成为唯一泛化依据；
9. prompt 中避免包含 benchmark task identity、答案模式或题目特定提示。

---

## 20. 当前阶段禁止事项

初始化阶段不要：

- 从头重写 Cairn；
- 大规模重构核心模块；
- 直接增加复杂 planner；
- 直接加入角色化多 Agent；
- 直接设计复杂 memory hierarchy；
- 直接实现大量安全工具；
- 给某类漏洞写 attack recipe；
- 用单次 run 判断架构优劣；
- 在 trace 不完整时优化系统；
- 同时修改多个关键机制；
- 根据完整 benchmark 反复调 prompt。

---

## 21. 当前阶段优先级

当前优先级按顺序是：

```text
P0  可复现运行
P1  完整 trace
P2  可靠 evaluator
P3  Baseline contract
P4  Diagnostic Set
P5  Baseline failure analysis
P6  第一项 architecture hypothesis
P7  最小机制修改
P8  泛化验证
```

不是：

```text
先让系统尽快拿更多 flag
```

---

## 22. Agent 第一轮工作要求

Agent 阅读本文后，应首先：

1. 检查当前工作区是否已经包含 Cairn 或相关 fork；
2. 阅读项目结构与关键源码；
3. 不修改核心架构；
4. 识别可插入 instrumentation 的最小位置；
5. 输出 Baseline Architecture 文档；
6. 输出 Baseline Contract 草案；
7. 规划 Experiment Harness；
8. 规划 event schema；
9. 规划 evaluator；
10. 列出需要新增的测试；
11. 标记任何可能影响 baseline semantics 的修改；
12. 在获得足够 baseline 数据前，不提出 task-specific capability patch。

初始化完成后，项目才进入正式 baseline evaluation 阶段。

---

## 23. 项目长期目标

长期目标不是证明：

> Cairn 是好还是坏。

也不是证明：

> Blackboard 一定优于其他架构。

目标是：

> 基于真实安全任务和可复现实验，逐步确定哪些机制能够提升强模型驱动 CRS 的搜索、协作、验证、资源分配和终止能力，并最终形成一个具有清晰机制归因的独立 CRS。

因此，每一项保留下来的机制都应尽可能回答：

```text
它解决了什么失败模式？
为什么有效？
在哪类任务上有效？
代价是什么？
是否能够泛化？
```

最终系统应是实验结果逐步筛选出来的，而不是预先一次性设计出来的。
