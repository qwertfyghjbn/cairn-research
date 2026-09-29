# Cairn Experiment Data Protocol v1

```yaml
protocol_id: cairn-experiment-data
schema_version: "1.0"
status: active
effective_date: 2026-09-29
baseline_contract: cairn-v0-baseline@1
```

## 1. 目的与边界

本协议是 M3 的统一数据合同。它规定一次实验运行如何描述配置、事件、结果、指标、图快照
和 Artifact，使 Experiment Harness、instrumentation、evaluator 与离线分析读取相同格式。

本协议不改变 Cairn 的 Server、Dispatcher、Prompt、调度、Fact/Intent 语义或终止行为。
观测实现仍必须遵守 [Baseline Contract](BASELINE_CONTRACT.md) 的 `C-OBS-01`、
`C-OBS-02`、`C-RESULT-01`、`C-RESULT-02` 和第 16 节 Manifest 要求。

规范性机器接口位于 [`schemas/run-v1/`](../../schemas/run-v1/)，参考验证器位于
[`experiments/protocol/validate.py`](../../experiments/protocol/validate.py)。本文解释字段语义和
Schema 不能完整表达的跨文件约束。

## 2. Run 目录

一个 run 是不可覆盖的目录：

```text
runs/<run_id>/
├── manifest.json              必需：运行身份和冻结条件
├── events.jsonl               必需：仅追加的原始事件流
├── result.json                必需：evaluator 的最终判定
├── metrics.json               必需：可重算的派生指标
├── graph_snapshot.json        必需：最终或中断时的图状态
├── artifacts/
│   ├── index.jsonl            必需：Artifact 索引，可以为空
│   └── ...                    按索引引用的文件
├── agents/<worker_id>/...     可选：Worker 私有输出归档
└── evaluator/...              可选：evaluator 输入输出归档
```

规则：

1. `run_id` 必须在目录创建前确定，在全部顶层记录中一致。
2. 已发布的 run 目录不得就地改写；补算指标应写新 `metric_set_version` 或新分析产物。
3. `events.jsonl` 和 `artifacts/index.jsonl` 仅追加，每行一个 UTF-8 JSON 对象，不允许空行。
4. JSON 文件使用临时文件写完、`fsync` 后原子 rename。事件行必须在一次写调用中完整追加。
5. 运行中断也要保留目录，设置 `run_state=interrupted`，并用已有事件生成结果和快照。
6. Artifact 只能使用 run 目录下 `artifacts/` 开头的 POSIX 相对路径；禁止绝对路径和 `..`。

完整合法样例见 [`examples/run-v1/complete/`](../../examples/run-v1/complete/)。

## 3. 通用类型

| 类型 | 规则 |
| --- | --- |
| `schema_version` | 当前固定为字符串 `1.0` |
| ID | 1–128 字符，首字符为字母或数字，之后允许字母、数字、`.`、`_`、`:`、`-` |
| 时间 | 带时区的 RFC 3339；生产数据统一写 UTC `Z` |
| duration | 整数毫秒，取自单调时钟 |
| token | 非负整数；provider 不提供时用 `null`，不能用 `0` 代替未知 |
| cost | 非负 USD 数值；无法计算时用 `null` |
| SHA-256 | 64 位小写十六进制；容器 digest 保留 `sha256:` 前缀 |

空值语义：`0` 表示测得为零，`null` 表示未提供或不可可靠计算。必填字段即使未知也必须显式
写 `null`；不得省略来混淆协议版本。

## 4. `manifest.json`

Schema：[run-manifest.schema.json](../../schemas/run-v1/run-manifest.schema.json)。Manifest 冻结
这次运行的身份与比较条件，而不是保存运行过程。

主要字段：

| 字段 | 含义 |
| --- | --- |
| `run_id`, `experiment_id` | 稳定运行 ID 与所属实验 ID |
| `run_state` | `finished` 或 `interrupted` |
| `task` | `task_id`、内容哈希和 challenge 版本 |
| `system` | system version、完整 Git commit、baseline ID、合同版本 |
| `model` | provider、模型版本、参数、endpoint 类型及 seed 支持情况 |
| `workers` | Worker 数与每类 Worker 的任务、优先级、并发、CLI/session 配置 |
| `prompts` | prompt group 及实际使用的每个 Prompt 哈希 |
| `environment` | 执行模式、工具链、镜像 digest、权限、网络和清理策略 |
| `budget`, `timeouts`, `retry_policy` | 实验开始前冻结的限制 |
| `evaluator_version`, `random_seed` | 判定版本与随机条件 |
| `instrumentation` | 观测实现版本及是否采集开销 |

`manifest.json` 可以在运行开始时先以临时文件建立，结束时补写 `run_state`、`finished_at` 后原子
发布。最终目录中的 `finished` 和 `interrupted` run 都必须有 `finished_at`。凭据只记录“已配置”
和来源类别，不记录值。

## 5. `events.jsonl`

Schema：[run-event.schema.json](../../schemas/run-v1/run-event.schema.json)。事件是原始事实记录；
指标和分析结果不得反向写回事件流。

### 5.1 公共 envelope

每个事件都包含：

```json
{
  "schema_version": "1.0",
  "run_id": "run-001",
  "event_id": "evt-000001",
  "sequence": 1,
  "event_type": "run_started",
  "timestamp": "2026-09-29T10:00:00Z",
  "monotonic_ms": 0,
  "worker_id": null,
  "task_id": "task-001",
  "parent_event_id": null,
  "related_fact_ids": [],
  "related_intent_ids": [],
  "related_artifact_ids": [],
  "token_usage": null,
  "cost_usd": null,
  "duration_ms": null,
  "payload": {}
}
```

- `sequence` 是写入器分配的连续序号，从 1 开始，是 run 内的规范总顺序。
- `timestamp` 用于跨系统对时；并发分析和 duration 使用 `monotonic_ms`。
- `parent_event_id` 表示直接因果父事件，只能引用更早的事件；其他关系使用 `related_*_ids`。
- `token_usage.source` 是 `provider` 或 `estimated`。不得把估算值伪装为 provider usage。
- 原始大文本、Prompt、响应、stdout/stderr 放入 Artifact，事件只保存引用和结构化摘要。

### 5.2 事件类型和最低 payload

| 事件 | 必需 payload | 说明 |
| --- | --- | --- |
| `run_started` | `system_version` | 必须是第一条事件 |
| `run_finished` | `termination_reason` | `finished` run 的最后一条事件 |
| `worker_started`, `worker_stopped` | `worker_type` | 必须设置 `worker_id` |
| `llm_call_started`, `llm_call_completed` | `call_id`, `model_id`, `phase` | complete 事件承载 usage、cost、duration |
| `tool_call_started`, `tool_call_completed` | `call_id`, `tool_name` | 参数和输出应使用 Artifact 引用 |
| `fact_created`, `fact_read`, `fact_referenced` | `fact_id` | 创建与消费必须分开记录 |
| `intent_created`, `intent_claimed`, `intent_completed`, `intent_abandoned` | `intent_id` | heartbeat 可在后续小版本加入独立类型 |
| `artifact_created`, `artifact_read` | `artifact_id` | ID 必须存在于 Artifact 索引 |
| `flag_candidate`, `flag_submitted`, `flag_accepted` | `submission_id` | 不要求在事件中保存明文 flag |
| `runtime_error` | `category`, `message`, `retryable` | message 必须经过凭据清理 |
| `budget_exhausted` | `budget_type`, `limit`, `observed` | 描述由 Harness 强制的预算 |

已知但当前无法从 Agent CLI 可靠取得的 tool/LLM 细粒度事件可以缺失；Manifest 必须使这一采集
限制可审计。不得合成未观测到的事件来填补序列。

## 6. `result.json`

Schema：[run-result.schema.json](../../schemas/run-v1/run-result.schema.json)。结果由固定版本的离线
evaluator 产生：

- `SOLVED`：`validity=VALID`，必须有 `accepted_submission`，invalid reason 必须为空。
- `UNSOLVED`：`validity=VALID`，accepted submission 与 invalid reason 都必须为空。
- `RUNTIME_INVALID`：`validity=INVALID`，必须使用 M2 固定的 invalid reason。

Cairn Project 的 `completed` 只是一项协议状态，不能直接产生 `SOLVED`。`termination_reason` 必须
与最后一条 `run_finished` 事件相同。`evaluator_version` 必须与 Manifest 和 Metrics 一致。

## 7. `metrics.json`

Schema：[run-metrics.schema.json](../../schemas/run-v1/run-metrics.schema.json)。v1 固定以下第一批
指标：

```text
time_to_flag_ms      tokens_total          tokens_to_flag
llm_calls            tool_calls            cost_total_usd
runtime_failures     facts_created         intents_created
intents_completed    intents_abandoned     artifacts_created
```

`derived_from.events_sha256` 必须匹配原始事件文件；`calculation_version` 标识计算逻辑。所有计数
必须由事件重新计算。缺少 provider usage 时 token/cost 指标写 `null`，不推断为零。

增加新指标需要新的 `metric_set_version`。改变已有指标定义还需要保留旧算法，以便历史数据可重算。

## 8. Artifact

Schema：[artifact-record.schema.json](../../schemas/run-v1/artifact-record.schema.json)。索引记录包括
Artifact ID、类型、相对路径、SHA-256、字节数、media type、生产 Worker/事件、时间和脱敏状态。

v1 类型包括 command output、Prompt、模型响应、exploit script、binary、pcap、source snippet、
scan result、screenshot、generated payload、evaluator output 和 `other`。每个索引项必须对应：

1. 一个实际存在且位于 `artifacts/` 内的普通文件；
2. 一条 `artifact_created` 事件；
3. 正确的内容哈希和字节数；
4. 一个已存在的 producer event。

Artifact 可以保存原始证据；Fact 继续保持 Cairn V0 的简洁描述，不增加 Worker 可消费字段。

## 9. `graph_snapshot.json`

Schema：[graph-snapshot.schema.json](../../schemas/run-v1/graph-snapshot.schema.json)。快照保留 Cairn
API 中的 Project、Fact、Intent 和 Hint，并增加 snapshot ID、类型、采集时间、来源 schema 与
`last_event_sequence`。

快照是状态视图，不能替代事件流。尤其不能只根据最终图推断哪个 Worker 在何时读取了某个 Fact。
Intent 的 `from` 必须引用快照中的 Fact；非空 `to` 必须引用 Fact；ID 在各自集合内必须唯一。

## 10. 隐私与敏感数据

Manifest、事件、结果和 Artifact 索引禁止出现保存凭据值的 key，例如 `api_key`、`password`、
`authorization`、`access_token`、`refresh_token`、`private_key` 和 `secret`。工具输出和模型响应
进入 Artifact 前也必须进行凭据扫描；执行过脱敏时记录 `redaction.applied=true` 和方法。

Flag 本身可能是评测秘密。事件和 `result.json` 应优先记录 submission ID、哈希和 evaluator 判定，
只有任务规则明确允许时才保存明文。

## 11. 版本兼容

- `1.x` 可以增加可选字段或枚举值；读取器必须忽略它理解范围外、由兼容版本允许的字段。
- 删除字段、改变字段含义、单位或必填性必须升级主版本。
- 静态 Schema 对当前 `1.0` 使用 `additionalProperties=false`，因此采用新字段的生产者必须同时
  发布对应小版本 Schema，不能把未知字段静默混入 `1.0`。
- 数据迁移写入新目录，保留原 run、原 schema version、迁移工具版本和源目录哈希。
- 历史 Schema 永久保留；不得用新定义覆盖旧文件。

## 12. 验证命令

从 Cairn 组件根目录（工作区的 `cairn/`）运行：

```bash
python -m experiments.protocol.validate runs/<run_id>
```

验证器不需要第三方依赖，检查：

- 六份 Schema 的字段和类型约束；
- 顶层 `run_id`、task、system 和 evaluator 版本一致性；
- event ID、连续 sequence、因果引用和单调时间；
- Artifact 路径安全、文件存在性、大小和哈希；
- result 状态组合与终止原因；
- Metrics 的事件哈希和可重算计数；
- 图 ID 与边引用；
- 禁止的 secret key。

验证完整样例：

```bash
python -m experiments.protocol.validate examples/run-v1/complete
```

退出码 `0` 表示通过，`1` 表示至少一项协议错误。

## 13. M3 完成标准

M3 在以下条件满足时完成：

- 本文、六份版本化 JSON Schema 和参考验证器进入版本控制；
- 提供一个完整、可验证的 run 示例；
- 测试证明有效示例通过，非法 sequence、状态组合、Artifact 路径和 secret key 被拒绝；
- 协议覆盖 M2 Manifest、观测、结果分类与 evaluator 隔离要求；
- Cairn 的运行源码、Prompt、依赖锁及既有语义没有变化；
- M4 Experiment Harness 以本协议 `schema_version=1.0` 作为唯一输出格式。
