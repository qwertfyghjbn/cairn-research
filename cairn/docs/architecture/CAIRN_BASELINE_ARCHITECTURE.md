# Cairn V0 基线架构地图

> 供后续 coding agent 阅读。本文描述冻结的上游提交
> `8e7e0ea67552383851dfcabfba0c4e9c8d007878` 的实际实现；研究分支上的
> M0 来源、依赖和验证方式见 [M0_BASELINE.md](../experiments/M0_BASELINE.md)。
> 本文是 Phase 0 的代码地图；规范性边界由已经生效的
> [Baseline Contract](../experiments/BASELINE_CONTRACT.md)定义。

## 阅读入口与边界

第一次接触此仓库，建议按以下顺序阅读：

1. 本文了解组件、状态和运行链路。
2. [Server 协议规格](../specs/server-protocol.md)和
   [Dispatcher 设计规格](../specs/dispatcher-design.md)了解原设计；遇到不一致时以本提交的源码为准。
3. 从 [`cli.py`](../../cairn/src/cairn/cli.py)进入，再沿下表定位具体模块。
4. 修改代码前先读相关测试和已经建立的
   [Baseline Contract](../experiments/BASELINE_CONTRACT.md)。

本文使用的词汇：**Project** 是一个 origin 到 goal 的搜索实例；**Fact** 是图上的描述节点；
**Intent** 是从一个或多个 Fact 出发、待探索的方向；**Hint** 是外部注入的信息；
**reason lease** 是单项目的推理占用记录。这里的「Worker」是受 Dispatcher 管理的 CLI
执行单元，不是独立的 Server 协议客户端。

## 1. 仓库与组件

```text
Cairn 组件根目录（工作区的 `cairn/`）/
├── cairn/pyproject.toml, cairn/uv.lock  Python 包与依赖锁
├── cairn/src/cairn/cli.py                serve / dispatch 命令
├── cairn/src/cairn/server/               FastAPI、SQLite、协议路由、导出
├── cairn/src/cairn/dispatcher/
│   ├── config.py                         运行配置与校验
│   ├── protocol/client.py                Server HTTP 客户端
│   ├── scheduler/loop.py                 项目轮询、选择、派发、清理
│   ├── tasks/{bootstrap,reason,explore}.py 三类任务执行与写回
│   ├── contracts.py, prompting.py        输出契约、Prompt 渲染
│   ├── workers/                           CLI Driver 和健康检查
│   ├── runtime/                           lease、进程、容器/本地后端
│   └── prompts/{default,mock}/           随包分发的 Prompt
├── cairn/tests/                           协议、调度、运行时、mock 集成测试
├── experiments/protocol/                  统一实验数据协议验证器
├── schemas/run-v1/                        M3 JSON Schema
├── examples/run-v1/                       可验证的协议示例
├── dispatch*.yaml                         Dispatcher 配置示例
├── Dockerfile, docker-compose.yaml        应用容器部署
├── container/                             Worker 镜像构建资源
├── docs/specs/                            上游协议与设计说明
└── docs/experiments/                      基线合同和实验数据协议
```

| 职责 | 代码入口 | 运行时作用 |
| --- | --- | --- |
| Server | [`server/app.py`](../../cairn/src/cairn/server/app.py)、[`routers/`](../../cairn/src/cairn/server/routers/) | 提供 HTTP API，校验并持久化图与 lease |
| 存储 | [`server/db.py`](../../cairn/src/cairn/server/db.py)、[`services.py`](../../cairn/src/cairn/server/services.py) | SQLite 事务、ID、租约过期、模型转换 |
| Dispatcher | [`scheduler/loop.py`](../../cairn/src/cairn/dispatcher/scheduler/loop.py) | 轮询项目、选 Worker、先认领再派发、取消与清理 |
| 任务执行 | [`tasks/`](../../cairn/src/cairn/dispatcher/tasks/) | 构造 Prompt、运行 Worker、校验输出、调用 Server 写回 |
| Worker Driver | [`workers/registry.py`](../../cairn/src/cairn/dispatcher/workers/registry.py)、[`workers/adapters/`](../../cairn/src/cairn/dispatcher/workers/adapters/) | 生成 CLI 命令、健康检查、提取输出和 session |
| 执行后端 | [`runtime/backend.py`](../../cairn/src/cairn/dispatcher/runtime/backend.py) | 抽象容器与本地进程的共同接口 |

数据流：

```text
CLI → Server API → SQLite Project/Fact/Intent/Hint
          ↑
          │ 仅 Dispatcher 写协议
Dispatcher → 调度与 claim → 任务执行器 → Worker Driver → CLI 进程
     ↑                                             │
     └───────────── 结构化 stdout / 状态 / session ┘
```

## 2. Server 状态模型

[`server/models.py`](../../cairn/src/cairn/server/models.py)定义 API 模型，
[`server/db.py`](../../cairn/src/cairn/server/db.py)定义 SQLite 表。

- `Project`：`active | stopped | completed`；含 `bootstrap_enabled`、创建时间和可空的
  `reason` lease。创建时自动写入 `origin` 与 `goal` 两个 Fact。
- `Fact`：目前只有项目内 ID 和 `description`。没有一等的 producer、证据引用或创建时间；
  普通 Fact 的来源需要沿结论 Intent 的 `to` 反查。
- `Intent`：`from` 是至少一个来源 Fact，`to=null` 表示仍开放；结论时 `to=fNNN`，
  完成 Project 时 `to=goal`。另有 `description`、不可变的 `creator`、当前/最终执行者
  `worker`、`last_heartbeat_at`、`created_at`、`concluded_at`。来源关系存在
  `intent_sources` 表。
- `Hint`：`content`、`creator`、`created_at`，不进入 Fact–Intent 图。
- `Settings`：Server 全局的 `intent_timeout` 与 `reason_timeout`。项目内 Fact、Intent、Hint
  使用项目作用域计数器生成 ID。

`POST /projects/{id}/complete` 会新建一条指向 `goal` 的已结论 Intent，并把 Project 置为
`completed`。这里接受的是 Worker 的完成声明，Server 并不校验 CTF flag。
`reopen` 会移除原完成 Intent，生成一条 `external_feedback` Fact/Intent 并恢复 `active`。
对应实现见 [`routers/projects.py`](../../cairn/src/cairn/server/routers/projects.py)；
常规 Intent 创建、claim、release、conclude 见
[`routers/intents.py`](../../cairn/src/cairn/server/routers/intents.py)。

Server 的 `export?format=yaml|timeline` 在
[`routers/export.py`](../../cairn/src/cairn/server/routers/export.py)。Dispatcher 使用 YAML 导出作为
`reason`/`explore` 的图快照。当前 YAML 的 Intent 条目没有 `id`，而 API ProjectDetail 有 ID；
若后续要按 Intent ID 做事件关联，应从 API/写回结果取得，不要尝试只从 YAML 恢复。

## 3. Dispatcher 调度与 Worker 生命周期

[`DispatcherLoop.run`](../../cairn/src/cairn/dispatcher/scheduler/loop.py)按
`runtime.interval` 轮询：收取已结束任务、更新项目状态、取消非 active 项目的在运行任务、
安排后端清理，再派发新任务。并发上限分别由 `max_workers`、
`max_running_projects`、`max_project_workers` 和各 Worker 的 `max_running` 控制。
Worker 先按可执行任务类型、容量、短期不健康/拒绝窗口过滤，再按较小 `priority`、
较少运行任务和随机值选取（[`worker_select.py`](../../cairn/src/cairn/dispatcher/scheduler/worker_select.py)）。

单项目的主要路径：

1. 仅有 `origin`/`goal` 且没有普通 Intent 时，若 `bootstrap_enabled` 且配置了支持
   bootstrap 的 Worker，Dispatcher 创建/复用保留 Intent，然后尝试执行 `bootstrap`；否则执行
   `reason`。
2. 非初始态，若出现比本地 `ReasonCheckpoint` 更新的 Fact/Hint，或开放 Intent 数从正数降为零，
   且当前没有 reason lease，则优先执行 `reason`。
3. 否则取最新创建的未认领普通 Intent 执行 `explore`；没有变化时等待下一轮。

| 任务 | 输入 | 有效输出及写回 | 失败/收尾 |
| --- | --- | --- | --- |
| `bootstrap` | origin、goal、Hint | 主阶段必须是 `fact + complete`；先 conclude 保留 Intent，再以新 Fact complete Project | 超时或解析失败可用同一 session 执行 `bootstrap_conclude`，只写 Fact；拒绝、命令失败等释放 Intent |
| `reason` | YAML 图引用、合法 Fact ID、开放 Intent、`max_intents` | `complete`、最多 `max_intents` 条新 Intent，或有开放 Intent 时 `noop` | 超时、解析失败、无效输出不写图；结束时释放 reason lease |
| `explore` | YAML 图引用、当前 Intent ID/描述 | 必须返回 Fact 描述，Dispatcher conclude 当前 Intent | 超时或解析失败可进入同一 session 的 `explore_conclude`；拒绝或命令失败则释放 Intent |

任务逻辑分别位于 [`tasks/bootstrap.py`](../../cairn/src/cairn/dispatcher/tasks/bootstrap.py)、
[`tasks/reason.py`](../../cairn/src/cairn/dispatcher/tasks/reason.py)、
[`tasks/explore.py`](../../cairn/src/cairn/dispatcher/tasks/explore.py)。输出解析和接受范围在
[`contracts.py`](../../cairn/src/cairn/dispatcher/contracts.py)，不是 Worker CLI 自行决定写图。
Prompt 从包内 `prompts/<group>/` 读取并由
[`prompting.py`](../../cairn/src/cairn/dispatcher/prompting.py)替换占位符。

## 4. claim、heartbeat、release 的精确语义

- `reason` 在项目上 claim 独立 lease；同项目只能有一个活跃 reason Worker。同一 Worker 重复
  claim 是幂等的，其他 Worker 会收到 409。`reason` 不创建 Fact/Intent 作为 lease 本身。
- `bootstrap` 和 `explore` 先对目标 Intent 调用 heartbeat 以完成 claim；已被其他 Worker
  持有或已结论会返回 409。Intent 创建时也可由创建者直接认领，但 Dispatcher 常规创建
  Intent 时传 `worker=null`。
- [`HeartbeatLease`](../../cairn/src/cairn/dispatcher/runtime/heartbeat.py)在任务运行期间按
  `runtime.interval` 续约。403/409 立即视为失去 lease；其他失败先有短暂宽限，最终失败会
  kill 已附着进程。
- Server 在读取或相关写入时按 `Settings` 懒过期 lease：开放 Intent 清空 `worker`，
  项目级 reason 清空占用信息。已结论 Intent 保留最终 Worker。
- 正常任务结束或失败路径会按任务类型释放 lease；release 对未持有的开放 Intent/空 reason
  lease 是幂等的。Project 停止时 Server 清除开放 Intent 的持有者与 reason lease，
  Dispatcher 下一轮取消本地任务。

这些语义分布在 [`server/services.py`](../../cairn/src/cairn/server/services.py)、
[`routers/intents.py`](../../cairn/src/cairn/server/routers/intents.py)、
[`routers/projects.py`](../../cairn/src/cairn/server/routers/projects.py)与任务执行器中。

## 5. 模型适配、工具和执行环境

[`workers/base.py`](../../cairn/src/cairn/dispatcher/workers/base.py)的 Driver 接口负责
`check_health`、`build_execute`、`build_conclude`、session 与响应提取；
[`registry.py`](../../cairn/src/cairn/dispatcher/workers/registry.py)按运行模式选择
`claudecode`、`codex`、`pi`、`mock` 实现。`mock` 生成结构化结果，供测试和调度观察。
真实模型、工具调用和工具输出由这些外部 Agent CLI 在执行环境内管理。Cairn 本身不提供
统一的逐次 tool call 抽象，也没有可直接用于研究指标的 token/cost 事件流。

后端由 `runtime.execution` 选择：

- `container`：[`ContainerManager`](../../cairn/src/cairn/dispatcher/runtime/containers.py)
  为每个 Project 创建/复用一个 Docker 容器，Worker 命令通过 Docker exec 运行；
  [`ManagedProcess`](../../cairn/src/cairn/dispatcher/runtime/process.py)收集 stdout/stderr 和退出码。
  `completed_action=stop|remove` 控制完成后的清理。
- `local`：[`LocalBackend`](../../cairn/src/cairn/dispatcher/runtime/local_backend.py)
  为每个 Project 创建独立工作目录，以宿主用户权限启动 CLI；
  [`LocalProcess`](../../cairn/src/cairn/dispatcher/runtime/local_process.py)使用独立进程组、
  超时后 TERM/KILL。CLI 使用宿主机既有配置与凭据。停止项目不删除目录；完成时可选
  `keep|remove`。

通用启动、进程附着、退出收集在
[`tasks/common.py`](../../cairn/src/cairn/dispatcher/tasks/common.py)。`reason`/`explore` 的
YAML 图被写入执行环境中的 `/tmp/cairn-prompts/.../graph.yaml`，Prompt 放的是读取该文件的
指令；因此当前快照是临时执行输入，不是持久的实验 trace。

## 6. 终止、超时与已有观测

- 任务时限由 `tasks.bootstrap/reason/explore` 及两个 conclude 时限配置；容器使用 GNU
  `timeout`，本地进程由 Python 管理。`reason` 不做 conclude fallback。
- `complete` 将 Project 置为 `completed`；`stopped`/`completed`/删除会使 Dispatcher 取消
  在运行任务并安排对应后端清理。`reopen` 可使已完成 Project 回到 active。
- Dispatcher 目前输出带时间戳的文本日志（[`logging.py`](../../cairn/src/cairn/dispatcher/logging.py)），
  涵盖派发、结果、错误和部分耗时；失败输出仅记录截断预览。Server 的可导出 YAML/时间线
  表示已提交的图状态，不含完整进程输出或全部尝试事件。
- 现有代码没有统一 `run_id`、manifest、完整 `events.jsonl`、artifact store、flag evaluator、
  token/cost 账本或固定总预算执行器。`completed` 只是协议状态，不等同于有效 flag。

## 7. 后续观测的最小候选接点

本节只定位接点；允许边界与实现要求见已经生效的
[Baseline Contract](../experiments/BASELINE_CONTRACT.md)。

| 需要的事件/数据 | 候选接点 | 避免改变的行为 |
| --- | --- | --- |
| Project/Fact/Intent/Hint 与状态变化 | Server 路由在 SQLite 提交前后；`services.py` 的 lease 过期 | 事务、HTTP 状态码、ID、过期时机 |
| 调度决策、Worker 选择、任务起止 | `DispatcherLoop._try_dispatch_project`、`_select_worker`、`_reap_futures` | 选择顺序、随机调用次数、checkpoint 更新时间 |
| claim、heartbeat、release | `CairnClient` 或 `HeartbeatLease` 边界 | API 调用顺序、续约间隔、失败宽限 |
| Prompt/图快照与模型结果 | `tasks/common.py`、三类任务执行器、Driver 输出提取 | Prompt 内容、解析/拒绝规则、fallback 条件 |
| 进程原始输出和工具痕迹 | `ProcessResult` 与容器/本地后端；CLI 可提供时另行采集 | stdout/stderr 消费方式、进程时限、工具权限 |
| 最终 flag 判断 | 独立实验 evaluator 读取 run 产物 | Server 的 `complete` 协议语义 |

特别注意：Server 的 `Fact` 当前没有 producer/时间字段；单凭最终图无法准确重建“哪个
Worker 看见了哪个 Fact”或 Fact 创建时刻。研究级指标需要在读取/写入发生时保存原始事件。

## 8. 基线语义清单与测试定位

以下候选项已由 [Baseline Contract](../experiments/BASELINE_CONTRACT.md) 写成正式 contract，
并作为后续改动的回归门槛：

- Project 初始 `origin`/`goal`、`bootstrap_enabled` 与完成/停止/重开状态转换。
- `Fact`/`Intent`/`Hint` 字段、ID、`from → to` 图写入、`goal` 不得作为来源。
- reason 项目 lease、Intent claim/heartbeat/release、懒过期和停止项目时释放。
- `bootstrap → reason → explore` 的触发优先级、最新开放 Intent 选择、checkpoint 规则。
- Worker 过滤与排序、并发上限、健康检查模式、短期不健康/拒绝窗口。
- 三类 Prompt 输入、输出契约、最大 Intent 数、超时、取消和 conclude fallback。
- container/local 后端的工作目录、session 续接、进程终止、完成后清理。

现有测试入口：

| 主题 | 主要测试 |
| --- | --- |
| Server 状态、协议和 lease | [`test_server_api.py`](../../cairn/tests/test_server_api.py)、[`test_db_migrations.py`](../../cairn/tests/test_db_migrations.py) |
| 调度与 checkpoint | [`test_scheduler_logic.py`](../../cairn/tests/test_scheduler_logic.py) |
| 三类任务与写回 | [`test_worker_tasks.py`](../../cairn/tests/test_worker_tasks.py)、[`test_mock_end_to_end.py`](../../cairn/tests/test_mock_end_to_end.py) |
| 进程、取消、后端 | [`test_runtime_logic.py`](../../cairn/tests/test_runtime_logic.py)、[`test_local_execution.py`](../../cairn/tests/test_local_execution.py)、[`test_container_archives.py`](../../cairn/tests/test_container_archives.py) |
| 配置、Driver、输出契约 | [`test_config_and_adapters.py`](../../cairn/tests/test_config_and_adapters.py)、[`test_contracts_and_drivers.py`](../../cairn/tests/test_contracts_and_drivers.py)、[`test_healthcheck.py`](../../cairn/tests/test_healthcheck.py) |

M0 的固定依赖验证命令是 `./scripts/verify_m0_baseline.sh`；已记录 `98 passed`。
M1 只增加此文档，没有修改运行路径。M2 合同进一步冻结了上述语义，并明确哪些观测
接点允许写入，以及如何避免日志失败或开销影响任务运行。M3 的
[Experiment Data Protocol](../experiments/DATA_PROTOCOL.md)统一规定观测产物的格式、关联与
验证方式，仍未接入上述运行路径。
