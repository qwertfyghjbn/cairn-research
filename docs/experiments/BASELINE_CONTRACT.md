# Cairn V0 Baseline Contract

```yaml
contract_id: cairn-v0-baseline
contract_version: 1
status: active
effective_date: 2026-09-29
reference_commit: 8e7e0ea67552383851dfcabfba0c4e9c8d007878
baseline_id: cairn-main-8e7e0ea
```

## 1. 目的与适用范围

本文定义 Cairn V0 的可复现实验基线，以及研究版本偏离该基线时必须遵守的变更协议。
它冻结的是 **V0 对照组的身份和行为**，不是永久禁止研究这些机制。

后续版本可以修改本文中的任何机制，但必须创建新的 `system_version`，声明所偏离的合同条款，
并在同一对照实验中保持其他变量一致。任何未声明的能力变化都会使对照无效。

文中的规范词含义如下：

- **必须**：不满足时，该运行不能作为符合本合同的 V0 数据。
- **不得**：出现时，系统已经成为研究变体，不能继续标记为 V0。
- **建议**：推荐做法；偏离时需要在实验记录中说明。

架构和源码入口见
[CAIRN_BASELINE_ARCHITECTURE.md](../architecture/CAIRN_BASELINE_ARCHITECTURE.md)，
上游来源、依赖与镜像 digest 见 [M0_BASELINE.md](M0_BASELINE.md)。

## 2. 三层冻结模型

| 层级 | 内容 | 是否可修改 |
| --- | --- | --- |
| V0 定义 | 上游源码、协议、调度、Prompt、任务语义和运行时行为 | V0 内不得修改；研究版本可声明偏离 |
| 对照实验条件 | 模型、任务、预算、Worker 数、工具、容器、seed、evaluator | 每个实验可以选择；同一比较组内必须一致 |
| 观测层 | manifest、事件、metrics、artifact、离线 evaluator | 可以增加，但必须满足第 12 节的语义透明要求 |

本合同暂不指定唯一的正式评测配置。模型、预算、Worker 数和任务集合将在 Experiment Harness
和具体实验说明中选择并冻结。因此，“符合 V0”表示系统行为符合本文；“可比较”还要求运行
manifest 中的实验条件相同。

## 3. 基线身份

### C-ID-01：源码与依赖

V0 的可执行参考树必须是：

- 上游仓库：`https://github.com/oritera/Cairn.git`
- 上游提交：`8e7e0ea67552383851dfcabfba0c4e9c8d007878`
- 包版本：`0.2.1`，距离 `v0.2.1` tag 14 个提交
- `cairn/uv.lock` SHA-256：
  `90c5a3cc9405e27e47bc9ae5e5681ab86c63e2a23afb7768fcf1b7aa1dc80ffb`
- `cairn/pyproject.toml` SHA-256：
  `60d62d0bb36ec3631636f0483564d765bdb1f27afd1ee80d26a70ef83d9881bb`

纯观测版本应使用类似 `cairn-v0-observed-<revision>` 的独立 `system_version`，并在 manifest
中同时记录 `baseline_id=cairn-main-8e7e0ea`。它只有通过第 12、17 节的等价性要求，才能作为
V0 的可观测实现使用。

### C-ID-02：容器与工具链

容器运行必须记录镜像 index digest 和 `linux/amd64` 平台。M0 冻结的 digest 为：

- Worker image index：
  `sha256:d90d40b7c634b8d5dc9464e04b863a185b9efe964ffd2b246f6e5cbc2a2ef053`
- Worker image linux/amd64 manifest：
  `sha256:d41bd6922951e7237f0c1c2cd4451b4bb7d38cf373e2258ae00b841a71fcdfc2`
- uv base image index：
  `sha256:c11a6b0892dcaafa4adfe89cc680117c955a8c55b107c2d432cee069b006cad8`
- uv base image linux/amd64 manifest：
  `sha256:68ab2a1582ea271691e440d537eb386cb506dd19196246a57f006223d6c62d1e`

不得只把 `latest` 或其他可变 tag 作为实验版本标识。local 模式必须记录 Python、uv、Agent
CLI 和操作系统版本。

### C-ID-03：Prompt

V0 的 `default` Prompt 内容固定如下：

| Prompt | SHA-256 |
| --- | --- |
| `bootstrap.md` | `82e9fbf22131612aa638a1d43e41b7a6ff4de5e2a80b4b74f0e55854c7cc29f7` |
| `bootstrap_conclude.md` | `4154e53a9ca30b9bae600d8d5315d6ad634eb4836d25eee25a14c2ca975782a0` |
| `reason.md` | `22bc2342ff5d29fd748553927bb46e29cb87f86034b406efb6d402592e104060` |
| `explore.md` | `7847eb249a7a6b7ddeafe37d44fc9d8443ae9f368ce2ae48a7b161e3726635d9` |
| `explore_conclude.md` | `389db6c19e92882ab8d86592185cdbc5016ea79c9c449a3d31ed5e1f3a721394` |

运行必须记录 `prompt_group` 及每个实际 Prompt 的哈希。`mock` Prompt 属于回归测试资源，
不构成真实能力评测的 Prompt。

## 4. Server 协议与状态模型

### C-SERVER-01：Project 生命周期

- Project 状态固定为 `active | stopped | completed`。
- 创建 Project 时必须生成项目内的 `origin` 和 `goal` Fact。
- `stopped` 必须清除开放 Intent 的 Worker 和项目 reason lease。
- `complete` 必须创建一条指向 `goal` 的已结论 Intent，并把 Project 置为 `completed`。
- `reopen` 必须删除唯一的完成 Intent，创建 `external_feedback` Fact/Intent，并恢复 `active`。
- 已完成 Project 不得通过普通状态更新回到 active；必须走 reopen 协议。

实现位置：[`routers/projects.py`](../../cairn/src/cairn/server/routers/projects.py)。

### C-SERVER-02：Fact、Intent 与 Hint

- Fact 保持 `{id, description}` 模型；V0 不增加会被 Worker 消费的新字段。
- Intent 保持 `from → to` 语义；`to=null` 表示开放，`to=fNNN` 表示产生 Fact，
  `to=goal` 表示完成 Project。
- Intent 的 `creator` 创建后不可变；`worker` 表示当前持有者或最终执行者。
- `from` 至少包含一个已存在 Fact，且不得包含 `goal`。
- Hint 不进入 Fact–Intent 图，并保持现有的可写状态规则。
- ID 前缀、项目作用域计数方式和来源边关系不得改变。

实现位置：[`models.py`](../../cairn/src/cairn/server/models.py)、
[`db.py`](../../cairn/src/cairn/server/db.py)和
[`routers/intents.py`](../../cairn/src/cairn/server/routers/intents.py)。

### C-SERVER-03：完成声明与 flag 验证边界

Server 的 `completed` 只表示某个 Worker 通过 Cairn 协议声明目标完成。它不表示外部 evaluator
已经接受 flag。V0 不得在 Server complete 路径中加入新的 flag verifier；正式 solved 状态由
独立 evaluator 根据第 13 节判定。

### C-SERVER-04：协议响应

关键成功和错误状态码、事务行为、字段裁剪、校验规则必须保持上游实现。观测代码不得改变
请求顺序、响应体、HTTP 状态码、事务提交范围或并发可见性。

## 5. claim、heartbeat 与 release

### C-LEASE-01：Intent lease

- `bootstrap` 和 `explore` 必须在启动 Worker 前通过 heartbeat 认领目标 Intent。
- 一个开放 Intent 同时只能由一个 Worker 持有；其他 Worker 竞争时返回冲突。
- 同一 Worker 对已持有 Intent 续约是允许的。
- 已结论 Intent 不再可认领或释放，并永久保留最终 Worker。
- release 对未持有的开放 Intent 保持幂等；其他 Worker 不得释放当前持有者的 Intent。

### C-LEASE-02：reason lease

- reason 使用项目级 lease，不生成图节点。
- 同一 Project 同时最多一个 reason Worker；同一 Worker 重复 claim 幂等。
- reason 任务结束时必须执行 best-effort release。

### C-LEASE-03：续约与过期

- [`HeartbeatLease`](../../cairn/src/cairn/dispatcher/runtime/heartbeat.py)按
  `runtime.interval` 续约。
- 403/409 必须立即判定为 lease 丢失；其他 heartbeat 故障保持现有宽限逻辑。
- 最终丢失 lease 时必须终止已附着的 Worker 进程。
- Server 保持现有懒过期行为；Intent 与 reason timeout 来自全局 Settings。
- Dispatcher 必须继续验证 Server timeout 大于其轮询/heartbeat interval。

## 6. Dispatcher 调度

### C-SCHED-01：调度循环和并发

轮询阶段顺序、运行任务回收、状态刷新、非 active 任务取消、后端清理与新任务派发顺序保持
[`scheduler/loop.py`](../../cairn/src/cairn/dispatcher/scheduler/loop.py)的实现。
以下上限均为实验配置变量，但在一个比较组内必须相同：

- `runtime.max_workers`
- `runtime.max_running_projects`
- `runtime.max_project_workers`
- `workers[].max_running`
- `runtime.interval`

### C-SCHED-02：项目内优先级

- 初始图只含 `origin`/`goal`，且满足 bootstrap 条件时，优先创建/复用保留 bootstrap Intent。
- 不满足 bootstrap 条件的初始 Project 进入 reason。
- 非初始态出现新 Fact、新 Hint，或开放 Intent 从正数降为零时，reason 优先于 explore。
- 没有 reason 触发时，explore 选择最新创建的未认领普通 Intent。
- 图和 checkpoint 没有相关变化时不重复 reason。

### C-SCHED-03：Worker 选择

Worker 必须按以下顺序处理：任务类型、`max_running`、短期不健康窗口、项目/任务/Worker 的
拒绝窗口；候选者按较小 priority、较少运行任务、随机 tie-break 排序。观测代码不得增加
随机调用或改变候选集合与排序。

### C-SCHED-04：ReasonCheckpoint

reason 成功后才更新 checkpoint；初始化已有开放 Intent 的 active Project 时使用当前计数。
Fact、Hint 和开放 Intent 变化的判断维持现有计数语义。

## 7. 三类任务合同

### C-TASK-01：bootstrap

- 输入固定为 origin、goal 和 Hint JSON。
- 主阶段合法完成必须同时返回 Fact 与 complete 描述。
- 成功写回顺序必须是 conclude 保留 bootstrap Intent，再从新 Fact complete Project。
- 超时或解析失败仅在 Driver 支持、存在 session、lease 有效且 Project 仍 active 时进入
  `bootstrap_conclude`。
- conclude 阶段只把 Fact 写入图，不直接完成 Project。
- 拒绝、命令失败、无可用 fallback 等路径保持现有 release 行为。

### C-TASK-02：reason

- 输入固定为 YAML 图快照引用、合法 Fact ID、全部开放 Intent 和 `max_intents`。
- 输出只接受 complete、新 Intent 或在仍有开放 Intent 时的 noop。
- 新 Intent 数不得超过配置的 `max_intents`。
- 没有开放 Intent 时不得 noop。
- reason 不执行 conclude fallback；超时、命令失败、解析失败不写图。
- reason 结束时停止 heartbeat 并 best-effort release 项目 lease。

### C-TASK-03：explore

- 输入固定为 YAML 图快照引用、当前 Intent ID 和描述。
- 合法成功输出必须产生一个 Fact 描述，并 conclude 当前 Intent。
- 超时或解析失败仅在 Driver 支持、存在 session、lease 有效且 Project 仍 active 时进入
  `explore_conclude`。
- fallback 必须复用原 session；拒绝、命令失败和无效结果保持现有 release 行为。

### C-TASK-04：输出契约

[`contracts.py`](../../cairn/src/cairn/dispatcher/contracts.py)中的 JSON 提取、兼容格式、字段
校验、拒绝处理和最大 Intent 截断均属于 V0 capability。修改接受范围会改变模型有效输出的
概率，因此必须作为研究偏离声明。

## 8. 模型、Worker 与 Prompt 条件

### C-MODEL-01：每组实验必须固定

以下内容不是整个项目永久统一的值，但每个 baseline/variant 比较组必须完全一致并写入 manifest：

- provider、模型 ID 和模型版本（如提供）
- temperature、reasoning effort、max output 等模型参数
- Worker 数、名称、类型、任务类型、priority 和并发上限
- Agent CLI 名称、版本、session 恢复方式
- Prompt group、Prompt 哈希和模板替换输入
- provider endpoint 类型、重试策略和代理配置的非秘密部分
- random seed；若 provider 不支持确定性 seed，必须记录这一限制并使用多次重复运行

凭据不得写入 manifest、事件或 artifact。

### C-MODEL-02：V0 Worker 边界

Worker 只接收 Dispatcher 构造的 Prompt 并返回 CLI 输出。协议写入由 Dispatcher 完成。
V0 不得让 Worker 直接调用 Cairn API，也不得增加 Worker 间直接通信。

## 9. 工具与执行环境

### C-ENV-01：每组实验必须固定

以下内容必须写入 manifest，并在比较组内一致：

- `container | local` 执行模式
- 容器 image digest、平台、network mode、capabilities
- local 模式的操作系统、Python、uv、CLI 和工作目录策略
- Worker 可用工具及权限
- challenge/容器版本和网络拓扑
- 公共环境变量名及非秘密配置
- Project 完成/停止后的容器或目录清理策略

### C-ENV-02：执行行为

容器继续使用每 Project 一个容器与 Docker exec；local 模式继续使用每 Project 独立目录和宿主
进程组。进程启动、stdout/stderr 消费、TERM/KILL、session 续接和清理语义不得在 V0 观测
改动中变化。

## 10. 预算、超时与终止

### C-BUDGET-01：每组实验必须固定

每次比较必须声明并固定：

- wall-clock budget
- LLM call budget
- token budget
- cost budget 及价格表版本
- bootstrap、reason、explore 和 conclude timeout
- provider retry policy
- accepted flag、预算耗尽、Project complete 和基础设施失败时的终止规则

当前 Cairn 只强制每阶段 timeout，没有统一的 run-level token、cost、call 或 wall-clock budget。
Experiment Harness 可以从外部增加这些限制，但不得改变内部任务语义；强制终止必须进入 trace，
并按第 13 节分类。

## 11. Evaluator 边界

### C-EVAL-01：确定性与隔离

Evaluator 必须版本化，并从 run 产物或 challenge 接口确定性判定结果。它不得在运行中向 Worker
注入提示、创建 Fact/Intent、调整调度或延长预算。baseline 和 variant 必须使用同一 evaluator
版本与 challenge 判定规则。

Partial progress 可以独立评分，但不得覆盖最终 flag 的有效性判断。

## 12. V0 允许的观测改动

### C-OBS-01：允许增加的能力

在满足 C-OBS-02 的前提下，V0 observed implementation 可以增加：

- run manifest、结构化 `events.jsonl` 和 metrics
- LLM token、cost、call 和 duration 记录
- Prompt、响应、图快照及 stdout/stderr 存档
- artifact 文件引用与复制
- 调度决策、Worker 选择、claim、heartbeat、release、取消和错误事件
- evaluator 输入输出存档
- 覆盖上述行为的回归测试

### C-OBS-02：语义透明要求

观测代码必须满足：

- 不改变返回值、异常处理、控制流、API 调用及写图顺序。
- 不改变候选集合、排序、随机数调用次数或随机源。
- 不改变 Prompt、模型上下文、session、工具权限、timeout 或 retry。
- 不把采集到的数据重新注入 Worker 或 Dispatcher 决策。
- 日志/存档失败不得改变任务结果；失败本身应有可检测记录。
- 事件写入不得持有现有业务锁或改变 SQLite 事务范围。
- 密钥、认证头和敏感环境变量必须删除或脱敏。
- 记录 instrumentation 的时间、CPU、存储和上下文开销；不得隐藏明显资源影响。

无法满足这些条件的改动应标记为 research variant，而不是 V0 observability。

## 13. 结果与运行有效性

### C-RESULT-01：顶层状态

每个 run 必须归入且只归入以下状态之一：

- `SOLVED`：运行有效，并在固定预算内由 evaluator 接受至少一个满足任务目标的 flag/结果。
- `UNSOLVED`：运行有效，在合同规定的终止条件下结束，evaluator 未接受目标结果。
- `RUNTIME_INVALID`：基础设施或评测故障使结果不能用于能力归因。

### C-RESULT-02：分类边界

`RUNTIME_INVALID` 必须细分为 `provider_failure`、`worker_crash`、`dispatcher_crash`、
`container_failure`、`protocol_failure`、`evaluator_failure` 或 `timeout_infrastructure`。

以下情况通常属于有效运行中的系统结果，应归入 `UNSOLVED` 或 `SOLVED`，而不是自动排除：

- 模型产生无效 JSON 或被输出契约拒绝
- 正常任务 timeout 或 run budget exhausted
- 错误 Fact、重复探索、premature completion 或未找到 flag
- Worker 主动拒绝任务，但 provider 和执行环境正常

provider 整体不可用、容器无法启动、Dispatcher 崩溃或 evaluator 损坏等才属于 invalid。补跑规则
必须在实验开始前声明；原 invalid run 仍需保留和报告。

## 14. V0 内禁止的 capability modification

以下改动不得继续使用 `cairn-v0` 或 `cairn-v0-observed` 标识：

- 修改 Prompt、上下文内容或输出契约
- 修改调度顺序、Worker 选择或 checkpoint 实现，或在比较组内改变并发配置
- 修改 Fact/Intent/Hint、Server API、lease 或 heartbeat 语义
- 新增 planner、verifier、角色化 Agent 或 Worker 直接通信
- 修改 termination、retry 或 fallback 逻辑，或在比较组内改变 timeout 配置
- 改变模型、Worker 数、工具权限或执行环境而未作为实验条件记录
- 增加漏洞类型规则、关键词规则或 task-specific attack recipe
- 根据在线 evaluator 结果改变搜索或自动追加预算
- 在同一实验版本中同时引入多个无法分别归因的主要机制

## 15. Research Variant 偏离协议

研究版本可以有意修改第 3–14 节的机制。每项修改必须建立独立实验说明，并至少包含：

```yaml
experiment_id: <stable-id>
baseline_version: cairn-main-8e7e0ea
modified_version: <git-commit-or-system-version>
change_type: capability | efficiency | reliability
hypothesis: <可证伪的机制假设>
target_failure_types: []
affected_contract_clauses: []
changed_components: []
frozen_components: []
diagnostic_tasks: []
budget: {}
seeds: []
primary_metrics: []
mechanism_metrics: []
acceptance_criteria: []
rollback_condition: []
```

要求：

1. 一次实验只修改一个主要机制。
2. `affected_contract_clauses` 必须引用本文 ID，例如 `C-SCHED-02`。
3. baseline 和 variant 使用同一任务、模型、预算、工具、evaluator 和运行环境。
4. 修改先运行 Diagnostic Set；通过预设门槛后才进入 Development Set、公开 benchmark 和
   sealed holdout。
5. 不得覆盖或重写 V0 历史结果；研究版本使用新的 `system_version` 和 Git commit。

## 16. Manifest 最低要求

Experiment Harness 建立后，每个 run 至少必须冻结：

```text
run_id
task_id / task_hash / challenge_version
system_version / git_commit / baseline_id / contract_version
model / provider / model_parameters
worker configuration
prompt_group / prompt_hashes
tool permissions
execution mode / OS / container digests
budget / phase timeouts / retry policy
evaluator_version
random_seed
start time / end time
```

secret 值不得进入 manifest；只记录是否配置、来源类别或脱敏标识。

字段类型、事件关联、结果分类、Artifact 索引和跨文件一致性由已经生效的
[Experiment Data Protocol v1](DATA_PROTOCOL.md)统一定义。

## 17. 验证门槛

### C-VERIFY-01：V0 pristine

上游参考必须通过：

```bash
./scripts/verify_m0_baseline.sh
```

当前冻结结果为 `98 passed`。

### C-VERIFY-02：V0 observed

每次增加 instrumentation 后必须：

1. 继续通过完整上游测试。
2. 对固定 mock 场景比较 pristine 与 observed 的最终图、任务顺序、claim/release、输出契约和
   终止状态。
3. 检查 Prompt 哈希、依赖锁和配置未发生未声明变化。
4. 模拟事件存储失败，确认业务运行结果不变。
5. 报告 instrumentation 开销。

不要求两个并发运行具有完全一致的 wall-clock 时间；要求控制流、协议状态和决策输入保持
等价。涉及随机 tie-break 的测试必须固定随机源或比较允许的决策集合。

### C-VERIFY-03：已有测试映射

| 合同范围 | 现有测试入口 |
| --- | --- |
| Server、Project、Intent 与 lease | [`test_server_api.py`](../../cairn/tests/test_server_api.py) |
| 调度、Worker 选择、checkpoint | [`test_scheduler_logic.py`](../../cairn/tests/test_scheduler_logic.py) |
| 任务输出、fallback 与写回 | [`test_worker_tasks.py`](../../cairn/tests/test_worker_tasks.py) |
| 端到端 mock 调度 | [`test_mock_end_to_end.py`](../../cairn/tests/test_mock_end_to_end.py) |
| 进程、取消与清理 | [`test_runtime_logic.py`](../../cairn/tests/test_runtime_logic.py)、[`test_local_execution.py`](../../cairn/tests/test_local_execution.py) |
| 配置、Prompt 资源与 Driver | [`test_config_and_adapters.py`](../../cairn/tests/test_config_and_adapters.py)、[`test_contracts_and_drivers.py`](../../cairn/tests/test_contracts_and_drivers.py) |

## 18. 合同变更

合同可以演进，但不得静默修改。变更必须：

1. 增加 `contract_version`；
2. 说明修改原因和受影响的历史实验；
3. 保留旧合同以解释已有结果；
4. 明确这是更正 V0 描述、扩大观测许可，还是建立新的 baseline；
5. 若改变能力语义，应创建新的 baseline，而不是重定义已经产生数据的 V0。

## 19. M2 完成标准

当以下条件满足时，M2 视为完成：

- 本合同已进入版本控制并链接到 M0 来源和 M1 架构地图；
- 合同条款能够引用当前源码和测试入口；
- V0、对照实验变量、观测层和 research variant 的边界明确；
- 上游已跟踪运行代码相对冻结提交没有变化；
- 后续 Experiment Harness 以 `contract_version: 1` 和数据协议 `schema_version: 1.0`
  写入 manifest。
