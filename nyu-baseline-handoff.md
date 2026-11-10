# 交接 Prompt：NYU dev 18 题 admission 基线启动（接手中断的诊断）

> **已过期（2026-10-14）**：这是过期交接记录。不要把它交给新会话，也不要按其中的身份链、门禁或基线步骤执行。当前工作方式见 `research_workspace/cairn/docs/experiments/PERSONAL_EXPLORATION.md`。

下文保留当时的诊断现场，供查阅。

---

## 1. 任务

在仓库 `D:\cairn-research\research_workspace\cairn`（WSL 路径 `/mnt/d/cairn-research/research_workspace/cairn`，分支 `research/cairn-component`）启动并跑完 **NYU dev split 18 题 × 3 seeds（43/44/59）× 双 Worker = 54 run 的无台账 admission 基线**，随后按 `docs/experiments/NYU_ADMISSION_V1.md` §5 的冻结判据出报告。

用户角色是 Researcher，全程用中文交流。上一会话已完成全部基础设施/合同/身份链准备，卡在最后一个运行时缺陷的诊断中途。

## 2. 环境与操作铁律（违反会浪费大量时间）

- Shell 工具必须带 `required_permissions: ["all"]`。PowerShell 内联引号易炸：**复杂命令一律写临时脚本**到 `/mnt/d/cairn-research/tmp_*.sh`（Write 工具产出 CRLF），执行用：
  `wsl -e bash -lc "tr -d '\r' < /mnt/d/cairn-research/tmp_xxx.sh > /tmp/x.sh && bash /tmp/x.sh"`
  会话结束前清理 `tmp_*.sh`。
- python 一律用 `cairn/.venv/bin/python`（3.14.4，满足 ≥3.12），`PYTHONPATH=cairn/src`，cwd = 仓库根。
- 真实 API key 在 `/mnt/d/cairn-research/.env` 的 `LLM_API_KEY`（运行时映射为 `EXPERIMENT_DEEPSEEK_API_KEY`）。
- 运行 I/O：进行中在 `~/cairn-runtime/active-runs/`，完成在 `~/cairn-runtime/finalized-runs/run-<ts>-*/`。诊断先看该 run 的 `events.jsonl`（`runtime_error` 事件）与 `artifacts/deepseek-egress.json`（bridge 线程异常）。
- 驱动脚本 `scripts/nyu_admission_baseline_runs.sh` 有 skip-if-exists 逻辑（run 目录存在即跳过）：**失败 run 目录必须移走**（保留到 `runs/nyu-admission-v1/_invalid-*/`，禁止删除——运行数据不可变）才会重跑。
- **当前 tmux 会话 `nyu-baseline` 正在跑驱动**，每个失败 run 烧 ~90 秒并产生废目录。接手第一步建议 `tmux kill-session -t nyu-baseline` 停掉，修完再重启。

## 3. 身份链机制（核心约束，勿破坏）

- `software_identity()`（`experiments/model_proxy/deepseek_contract.py` L20-26）= 对 `experiments/` 与 `cairn/src` 下所有 `.py/.md` + 若干固定文件求 sha。**configs/ 不在身份内**。
- 自引用收敛固定点：**先定稿全部 py/md（含测试里的路径常量）→ 跑 c54 → 把 acceptance.json 拷到 `smoke-results/<目录>/acceptance.json` → 回填 campaign config 的 `observed_evidence`（path+sha256）→ `require_observed("nyuadmission")` 校验 → 跑 admission（报告指针自动回填 `configs/experiments/admissions/deepseek-nyu-admission.json`）→ 重启驱动**。任何 py/md 改动都会使 acceptance 与 admission 全部过期，必须重走整条链。
- 教训：**改动测试文件（含 `OBSERVED_RELATIVE` 路径常量）必须在跑 c54 之前**，否则身份不匹配（曾因此浪费一轮 245s 的 c54）。
- 当前已收敛状态：身份 `d53c047aeb960352…`，acceptance sha `693e7101…`（`smoke-results/20261012-c54-v2-nyu-identity4/acceptance.json`），`require_observed` OK，**admission r5 PASSED（11/11 checks）**，指针指向 `smoke-results/20261012-201827-nyu-admission-r5/report.json`。
- 常用命令：
  - c54：`PYTHONPATH=cairn/src cairn/.venv/bin/python -m experiments.c54_observed --output runs/c54-observed-<ts>-nyu`（~4 分钟）
  - 准入：`PYTHONPATH=cairn/src cairn/.venv/bin/python -m experiments.deepseek_admission --env-file /mnt/d/cairn-research/.env --output smoke-results/<ts>-nyu-admission-rN --campaign nyuadmission`（注意 campaign 名是 `nyuadmission` 无连字符）
  - 校验：`python -m experiments.protocol.validate <run目录>`（每 run 完成后的协议门禁）

## 4. 已修复的缺陷（本轮已确认收敛，勿回退）

1. `experiments/runner.py`：加 `FILE_KINDS = ("files", "nyuctf")`，3 处 `== "files"` 改 `in FILE_KINDS`（nyuctf 题此前落进 mock evaluator，报 `expected_evidence`）。
2. `experiments/runtime/file_run.py` prepare 拆三分支：`kind=="nyuctf" and service` → ServiceFileSandbox；`kind=="nyuctf"` 无服务 → NyuctfTaskAdapter + 离线沙箱；其余原样。`from pathlib import Path, PurePosixPath`（close() 的服务 compose 归档曾 NameError）。
3. `cairn/src/cairn/dispatcher/workers/adapters/pi.py` `_models_json`：注入 `model["maxTokens"] = int(EXPERIMENT_MAX_OUTPUT_TOKENS)`。根因：pi-coding-agent 0.73.0 对自定义模型默认 `maxTokens ?? 16384`（`core/model-registry.js` L451），桥 `freeze_request` 校验 `max_tokens <= maximum(2048)` 必炸 → 502。**此修复已确认生效**（实测请求体里 `max_completion_tokens: 2048`）。
4. `experiments/model_proxy/deepseek_contract.py` CAMPAIGNS 加 `nyuadmission` 条目；新增 `experiments/tests/test_nyuadmission.py`（7 测试）。
5. 新增 configs：`campaigns/nyu-admission-v1.json`、`budgets/nyu-admission-45m.json`、`prices/deepseek-stable-nyu-admission.json`、`models/deepseek-flash-nyu-admission.json`、指针 `admissions/deepseek-nyu-admission.json`；驱动 `scripts/nyu_admission_baseline_runs.sh`。

## 5. 当前卡点（接手后第一件事：继续诊断）

**现象**：身份 `d53c047a` 下重启驱动后（r4 批），run 仍在首个 LLM 请求处 `RUNTIME_INVALID / provider_failure`，egress record：`error_type: "ValueError"`、`http_status: 502`、`request_sent: false`、`provider_received: null`。样例：`~/cairn-runtime/finalized-runs/run-20261012-9a18849db6d5`。

**已排除**（勿重复排查）：
- 请求体本身合规：`artifacts/proxy/call-0a2fc999…-request.json`（10159 字节，明文 JSON）= model `deepseek-flash`、`max_completion_tokens: 2048`、tools 全在 `offline_policy.TOOLS` 白名单、无额外字段、`store: false`。
- gateway 注入代码与宿主源码逐字节一致（`artifacts/gateway-code.json` 13 个文件全 SAME）。
- 同一 payload 在宿主 venv 本地跑 `freeze_request` **通过**。
- 凭据/端点/网络没问题（admission r5 四个真实请求 PASSED）。
- `admit()` 的 AdmissionDenied 不可能是 `error_type` 纯 `"ValueError"`（类名会不同）。

**剩余嫌疑（按优先级）**：
1. **邮箱 `row["body"]` 与落盘 request 的差异**：bridge `forward()` 用 `freeze_request(base64.b64decode(row["body"], validate=True), self.maximum)`（`deepseek_bridge.py` L388）。落盘的 request.json 是明文；邮箱里是 b64。核对 b64 解码字节是否与落盘一致（截断/双重编码/换行）。
2. **桥构造参数实际值**：`maximum=self.spec.model["parameters"]["max_output_tokens"]`——看 run 的 `resolved-spec.json` / `manifest.json` 里 model parameters 是否真为 2048（以及 `call_limit` 实际值，排除 L395 "固定出口尝试限额"）。
3. `validate_offline_payload` 在容器内行为差异（已基本排除，代码一致）。

**建议诊断法（最小成本）**：临时给 `deepseek_bridge.py` forward 的 except 分支（L446 附近 `record["error_type"] = type(exc).__name__`）加 `record["traceback"] = traceback.format_exc()`（traceback 已 import），跑一次诊断 run（首个请求即失败，真实 API 花费近乎零），从 `deepseek-egress.json` 读 traceback 定位确切行；废 run 移入 `runs/nyu-admission-v1/_invalid-provider-failure-r4/`。**注意：改 py 会破坏身份，诊断后必须还原或纳入定稿重走第 3 节收敛链。**

## 6. 卡点解决后的收尾流程

1. 若 py/md 有改动：重走身份链（c54 → 拷 acceptance → 回填 campaign → 改 `test_nyuadmission.py` 的 `OBSERVED_RELATIVE` 指向新目录（先改再跑 c54！）→ admission rN → 确认 PASSED）。
2. 清理 r4 废 run 目录（移入 `_invalid-*`，勿删），确认 `~/cairn-runtime/active-runs/` 干净。
3. 重启驱动：`tmux new-session -d -s nyu-baseline 'bash scripts/nyu_admission_baseline_runs.sh 2>&1 | tee /home/lqs/cairn-runtime/nyu-baseline.log'`。
4. 确认首个 run 产出正常（SOLVED/UNSOLVED，evaluator `flag-exact-v1` 正常产出），之后让 54 run 跑完（串行，单 run 预算上限 2700s/192 calls/$7.5）。监控：`runs/nyu-admission-v1/summary.tsv` 与 tmux `nyu-baseline`。
5. 全部完成后按 `docs/experiments/NYU_ADMISSION_V1.md` §5 的 3-seeds 分类标准出中文报告；报告与新增文档用中文。

## 7. 关键路径速查

- campaign：`configs/experiments/campaigns/nyu-admission-v1.json`（18 题 task_hashes、seeds [43,44,59]、run_order 54 项，格式 `{slug}-w2-s{seed}`）
- 驱动脚本：`scripts/nyu_admission_baseline_runs.sh`；summary：`runs/nyu-admission-v1/summary.tsv`（追加式，含历史废批注释）；per-run 日志：`runs/nyu-admission-v1/logs/<name>.log`
- 废 run 归档：`runs/nyu-admission-v1/_invalid-evaluator-failure/`、`_invalid-container-failure/`、`_invalid-provider-failure/`（r3 批）
- 文档：`docs/experiments/NYU_ADMISSION_V1.md`（判据冻结）、`NYU_ADMISSION_IDENTITY_CHAIN.md`、`C54_W2_RACE_BRIEF.md`、`C54_W2_RACE_ADJUDICATION.md`
- 桥/合同代码：`experiments/model_proxy/deepseek_bridge.py`（forward L367-455、freeze_request L71-88、`MODEL="deepseek-flash"` L27）、`offline_policy.py`（FIELDS/TOOLS 白名单）、`budget/ledger.py`（admit L77-105）
- pi 注入：`cairn/src/cairn/dispatcher/workers/adapters/pi.py`（`_models_json` L270-290、`BASE_TOOLS` L228）

## 8. 红线

- 运行数据不可变；废 run 只归档不删除；哈希不符不自动修哈希。
- 不改 Cairn 的 prompt / scheduler 语义 / Fact–Intent 行为；基线任务不得重新裁决 benchmark 选型。
- 报告本地验证结果，不得把未完成的验证说成已通过。
