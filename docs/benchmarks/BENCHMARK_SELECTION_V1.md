# Benchmark 选择与 Task Split 规划 V1

> 状态:裁决已确定(2026-09-29)。本文是 CRS 项目 failure-driven development 流程中
> Phase 4(Diagnostic Set)之前的 benchmark 选型裁决,覆盖:
> 候选比较 → contamination 分析 → Cairn 集成分析 → 四层 split 方案 → task admission protocol。
> 配套任务清单见 [BENCHMARK_TASK_REGISTRY_V1.json](BENCHMARK_TASK_REGISTRY_V1.json)。
>
> 本阶段**未**修改 Cairn 任何代码,**未**运行 benchmark,**未**阅读任何题目 solution。
> 调研来源以 arXiv 论文、官方 GitHub 仓库、官方 leaderboard 为主,关键数字均标注出处;
> 本地验证部分:Cybench 仓库本地克隆(commit `ca483c6`,2026-09-24)逐题 metadata 提取。

---

## 0. 最终裁决(摘要)

```text
Primary benchmark:        NYU CTF Bench(test split,200 题,冻结于官方 tag v20250206)
Diagnostic Set source:    admission pool = NYU CTF dev split(2013–2016,57 题,registry 已枚举)
                          ∪ Cybench difficulty ≥ 2 的可用题(上游验证过、本地克隆确认)
                          最终 5–10 题由 admission runs 从 pool 中筛出(§7)
Development Set:          同一 pool 的剩余题,目标 15–24 题,与 Diagnostic 不相交(§6.2)
Broad Benchmark:          NYU CTF Bench test split(200 题,官方冻结 test set;
                          只在候选修改通过 Diagnostic→Development 两层后运行)
Fresh / Sealed Holdout:   Tier A(sealed 静态):CSAW 2024/2025 quals+finals 自封装
                                + CVE-Bench(40 题,web CVE,zero-day 设定)
                          Tier B(fresh/live):CTFusion 方法论 —— live CTFd-hosted CTF
                                或自建 CTFd 私有冻结题,开发期绝不触碰
```

**是否需要组合多个 benchmark:需要。** NYU CTF Bench 是唯一的主干(能力刻度 + broad eval);
Cybench 只贡献难度标注和 subtask 元数据给 Diagnostic/Development 层;
CTFusion 只贡献 holdout 机制(不是题目来源);CyberGym 及其他候选全部不进入 V1(理由见 §4)。

---

## 1. 调研范围与关键事实修正

按要求调查了四个指定候选,并补充调查了 2025–2026 年新出现的 benchmark。先修正几个
广泛流传但错误的认知(本次调研中以一手来源证伪):

| 传闻 | 事实 |
| --- | --- |
| "Cybench 是当前最佳/最难的 CTF benchmark" | Cybench(40 题)对前沿模型已实质饱和:官方 leaderboard Claude Opus 4.7 = 96%(35 题子集)、Claude Mythos Preview = 100%;Opus 4.6 system card 明言其 cyber evals "no longer useful for tracking capability progression"。Dreadnode(arXiv 2607.21763)实测 22 个前沿模型在 23 题 medium 子集上 honest solve 仅 26.1%(pass rate 41.5%,37% 的通过涉及作弊) |
| "NYU CTF Bench train=2011–2021 / test=2022–2023" | 实际 split:dev = CSAW 2013–2016(README 称 55 题,main 分支索引实为 57 题,存在版本漂移),test = CSAW 2017–2023,共 200 题,dev/test 无重叠 |
| "Cybench 含 SquareCTF / 'Zenda's Restaurant'" | 40 题来自 HTB Cyber Apocalypse 2024(17)、SekaiCTF 2022+2023(12)、GlacierCTF 2023(9)、HKCERT CTF 2022(2);无 SquareCTF |
| "CyberGym ≈150 个 CVE、两个 level" | CyberGym(Berkeley,arXiv 2506.02548,ICLR 2026)实际 1507 个实例、188 个 OSS 项目、4 个难度 level;官方 SUBMISSION.md(2026-08)自述 Level 1 已"nearly saturated" |
| "CTFusion 是多源融合的静态数据集" | CTFusion(KAIST,arXiv 2605.11504,ICML 2026 AIWILD)是 **live CTF 流式评测框架**(CTFd + MCP server + 提交代理),不发布可重放的任务合集;"fusion"指多 agent 共享一个比赛账号 |
| "存在 PentestGym / CTF-Arena benchmark" | 均无法在任何一手来源验证存在(疑似记混);真实的近似物是 PentestEval(arXiv 2512.14233)和 AutoPenBench(arXiv 2410.03225) |

各候选的一手来源:NYU CTF Bench = arXiv 2406.05590(NeurIPS 2024 D&B)+ `github.com/NYU-LLM-CTF/NYU_CTF_Bench`;Cybench = arXiv 2408.08926(ICLR 2025 Oral)+ `github.com/andyzorigin/cybench` + `cybench.github.io` leaderboard CSV;CyberGym = arXiv 2506.02548 + `github.com/sunblaze-ucb/cybergym` + HF `sunblaze-ucb/cybergym`;CTFusion = arXiv 2605.11504 + `github.com/kaist-hacking/CTFusion`。

---

## 2. Benchmark 比较表

比较维度对应任务书七项。饱和度数字取可查的最强公开结果(pass@1 除注明外)。

| 维度 | NYU CTF Bench | Cybench | CTFusion | CyberGym |
| --- | --- | --- | --- | --- |
| **任务数** | test 200 + dev 55–57(CSAW 2013–2023;README 称 55,main 分支索引实为 57,registry 已逐一枚举) | 40(上游仓库实际缺 9 题 GlaciotCTF,见下) | 无自有任务:5 个 live 赛事 ≈176 题(2025.07–08,已结束且已公开);静态部分复用 NYU 180 题 | 1507 实例 / 188 项目(ARVO OSS-Fuzz) |
| **类别** | cry 52 / rev 51 / pwn 39 / msc 24 / web 19 / for 15(test,实证统计) | crypto 16 / web 8 / rev 6 / for 4 / misc 4 / **pwn 仅 2** | 取决于赛事(6 类齐全) | 无 CTF 类别:100% C/C++ 内存安全 PoC 复现 |
| **难度** | 无官方分级;CTF points 1–500;finals 显著难于 quals;CTFTiny 后验难度带可参考 | 官方 0–5 级 + human first-solve time(2 min → 24h54m);31 题共 129 个 subtask(均值 4.2) | CTFtime 权重标注赛事级难度;题目级仅 points/solves | Level 0–3(信息量递增);PoC >100 字节的前沿成功率骤降至 ~10% |
| **饱和度(2026-09)** | **未饱和**:EnIGMA 13.5%(2024)→ D-CIPHER 22%(2025.02)→ 59%(Claude 4.5 Opus,2026.04,单次);pwn 最好 41%;有 swarm 自报 200/200 但无协议,存疑 | **前沿已饱和**(93–100%,部分靠作弊);honest 口径 medium 子集 26–34%;对中低档模型(10–40%)仍有区分度 | live 最好 9.66%(EnIGMA+GPT-4.1,pass@3)—— 设计上远离饱和 | Level 1 官方自认近饱和(自报 89–93%,学术验证口径 22% GPT-5) |
| **可复现性** | pip `nyuctf` 下载数据集;每题 docker-compose;`up -d --force-recreate` / `down --volumes` 干净 reset;tag v20241008 / v20250206;无外部服务 | clone + Docker;18/40 有 compose 服务;**`run_task.py` 每题后执行 `docker system prune -a`(需 patch)**;无 release/tag,按 commit pin;上游缺 9 题,需用 0ca/cybench-patched 或 UK AISI inspect_evals 移植版(39 题,digest-pinned) | 依赖**正在进行的 CTFd 赛事 + API token**——live 不可重放;静态部分可跑但仓库为单次代码投放,无版本管理 | 每题 2 个镜像(-vul/-fix);HF 数据集 240GB / 全量 server ~10TB;必须本地部署 submit server;镜像按 OSS-Fuzz build ID pin |
| **Evaluator** | flag 静态存于 `challenge.json`,精确匹配,确定性;无官方 subtask;EnIGMA 失败分类(cost 82.5%)可参考 | `metadata.json` subtask answer 精确匹配(ACTUALLY `==`),确定性;**有 subtask/hints**,可做 partial progress;hints 是现成的干预旋钮 | 委托 CTFd 自带 checker;代理层做去重/作弊检测;binary 判定 | 差分 sanitizer oracle(vul 崩溃且 fix 不崩),自动化、可重跑;final-submission 口径必须用官方(防 brute force) |
| **实验成本** | 镜像小(60–318MB,`llmctf` 命名空间 288 个);每题秒级启动;已验证可 1600 次批量跑;LLM 成本为主要开销(Gemini 3 Flash 全集 $2.69,Claude 4.5 Opus $250) | agent 镜像 20.5GB;privileged dind;重复跑需 patch prune;体量适中 | 静态复用 NYU 成本;live 无重放概念 | 磁盘 240GB–10TB(本机 866GB 可用但紧张);论文全量 $40k API + 1000 H100 时;子集可降至 ~$3k/轮 |
| **Contamination** | **高**:题目 2017–2023 公开,flag 明文在仓库(CTFusion 抓到 agent `pip install nyuctf` 直接读 flag;web 搜索使 D-CIPHER 12.59%→24.07%;静态分约为 live 的 2.4 倍) | **高且已量化**:writeups 仓库公开(GlacierCTF 上游仓库名就叫 `GlacierCTF2023_writeups`),flag 明文在 `metadata.json`;Dreadnode:167 次作弊中 161 次是 web 检索 writeup | **机制上最干净**(评测时题目未发布);但 2025 赛事后已公开,那 176 题不再是 holdout | 公开 CVE + 公开 PoC(ARVO 镜像内含参考 PoC);论文自测 cutoff 前后无显著差异(p>0.1) |
| **研究价值(多步链/失败模式)** | 多步链充分;失败呈 "fast success / slow failure"(成功集中在 0–20 轮,失败 20–40 轮后 cost 耗尽);pwn/交互类最难;MITRE ATT&CK 映射现成;D-CIPHER 多 agent 先例(22%) | subtask 结构 + FST 难度标注是诊断利器;2024 模型在 pwn 0/2、misc 0/4、web 1/8 上全灭 → 交互/利用类失败模式的富矿 | 失败分类(costlimit/suspended/giveup)+ 逐 agent 隔离日志;45% 失败是 costlimit | repo 级推理链;但对 flag 型 CRS 语义错位(flag 只对 any-crash 颁发,前沿模型 any-crash ~99% vs 目标漏洞复现 ~85-90%,奖励信号失真) |

补充候选速览(详见 §4):

| 候选 | 任务 | 一句话裁决 |
| --- | --- | --- |
| CTF-Dojo(Amazon,arXiv 2508.18370) | 658 题 dockerized | 最大语料,但 leaderboard/集成信息薄;列为 Development 层未来扩容池,V1 不用 |
| CVE-Bench(UIUC,ICML 2025) | 40 题 web CVE,flag 型 | zero-day 设定、SOTA 30%;选入 Holdout Tier A |
| AutoPenBench(arXiv 2410.03225) | ~35 题 pentest,里程碑评分 | 任务分布是多主机渗透,与 flag-jeopardy 不同轴;V1 不用 |
| PentestEval(arXiv 2512.14233) | 346 题,6 阶段评分 | 阶段归因设计与本项目理念契合,但非 CTF 且需第二套 harness;V2 再评估 |
| InterCode-CTF(100 题 picoCTF) | — | 饱和 + 14.1% 答案泄漏(EnIGMA 实测);仅作 harness 冒烟测试,不入正式 split |
| CyberSecEval 3 CTF(5 subtasks) | — | 太小;仅冒烟测试 |
| EnIGMA HTB-50 | 50 题 | 不可再分发;只引用其数字 |

---

## 3. 可复现性与资源需求

### 3.1 各候选的运行形态

**NYU CTF Bench(选定为主干)**

- 获取:`pip install nyuctf` → `python3 -m nyuctf.download`(数据集落到 `~/.nyuctf/<tag>/`);
  镜像在 Docker Hub `llmctf/*` 命名空间(288 个 repo,2024-05 后未更新,属冻结状态,是优点)。
- 运行:读 `challenge.json` → 有 compose 的题 `docker compose up -d --force-recreate` →
  agent 侧容器加入同一网络 → 结束后 `down --volumes`。reset 语义干净,天然适合 seed 级重复。
- 版本:pin **tag v20250206**(PyPI `nyuctf==1.1.1` 对应);如需与 EnIGMA/D-CIPHER 数字
  严格对齐可退回 v20241008。main 分支 dev 索引与 README 口径存在漂移
  (README 55 题 / 索引 57 题,registry 按索引枚举),**一切以 tag 为准**。
- 已知损坏题(issues + CTFusion 独立发现 26/210 需修复):test 内
  `2021q-cry-crack_me`(README 曾泄 flag,#14)、`2023q-web-cookie_injection`(DNS 名不匹配,#19);
  dev 内 `2015f-pwn-hipster`(flag 为占位符 `flag{temp}`,#21)、`2015q-web-k_stairs`(flag 曾缺字符,#18 已修)。
  **措施:broad 运行前做一次 bring-up 巡检,产出本地 repair manifest;受影响题在 registry 中
  标注,修复前不进入任何 split。**

**Cybench(选定为 Diagnostic/Development 素材)**

- 本地克隆 `cybench_repo`(commit `ca483c6`)已完成 43 题的 metadata 提取(registry 已含);
  **task_list.txt 中的 9 题 GlacierCTF 上游从未入库**(全 552 commit 历史验证)。
  若需要这 9 题:用 `0ca/cybench-patched` 或 UK AISI `inspect_evals` 移植版(39 题,digest-pinned 镜像)。
  V1 决策:**只用本地可验证的题,不引入第三方 fork**,缺 9 题不影响诊断用途。
- 陷阱两条:上游 `run_task.py:209` 每题后 `docker system prune -a -f`(批量跑必须绕开,我们
  不用其 runner,自建 adapter 则天然规避);agent 镜像 `cybench/cybench` 20.5GB(我们用 Cairn 自己的
  worker 镜像,不需要它)。
- 我们只复用其**任务层**:`start_docker.sh`/compose + `init_script.sh`(分发文件)+
  `metadata/metadata.json`(prompts、target_host、subtask Q/A、hints)。不使用其 SimpleAgent。
  注意:本地克隆内含 `metadata/solution/`(14/40 题)——**该克隆只留在研究侧,
  严禁进入 worker 容器或 worker 可读路径**(本阶段任何人/agent 不得阅读其内容)。

**CyberGym(未选)**:240GB(HF 最小口径)到 10TB(全量 server);本地必须跑 submit server;
 仅 amd64。本机(866GB 空闲、15GB RAM)可跑小子集但与 flag 型 CRS 语义错位,不值。

**CTFusion(仅取机制)**:静态部分即 NYU;live 部分需要一个 CTFd 实例 + API token,
到事件发生时再搭。

### 3.2 本机前置条件(实测,2026-09-29)

```text
Docker:    当前 WSL 发行版未启用(需开 Docker Desktop WSL 集成或装 docker engine)  ← P0 前置
磁盘:      866GB 空闲(/)           — NYU 全集数 GB 级,绰绰有余
RAM:       15GB                    — NYU 单题 1–2 容器足够;Cybench dind 勉强;CyberGym 不够
CPU:       16 核                   — 足够并行多题(受 max_running_projects 约束)
```

结论:NYU 主干 + Cybench 素材在本机完全可行;CyberGym 不可行也不必要。

---

## 4. Contamination 分析与反污染协议

### 4.1 证据汇总

| Benchmark | 污染证据 | 定性 |
| --- | --- | --- |
| NYU CTF | flag 明文在 repo;CTFusion 实测:web 搜索使 12.59%→24.07%;71 次作弊尝试;静态分 ≈ live 分 × 2.4(GPT-4.1:16.94% vs 7.10%);EnIGMA 实测 flag leakage 2.7%;纯 prompt 消融(no-pretrained-knowledge)使 D-CIPHER 13.6%→9.7% | **高,但可控**:禁网 + 沙箱清理后主要剩"训练期记忆"分量;模型排序仍稳定(CTFusion 结论) |
| Cybench | writeups 仓库公开且上游目录名即 writeups;flag 明文;Dreadnode:pass 41.5% 中 honest 仅 26.1%,161/167 作弊是 web 检索 | **高**:禁网是硬前提;前沿模型可能已记住 writeup,绝对分数不可比 |
| CyberGym | 公开 CVE/PoC/patch;论文自测无显著 cutoff 效应 | 中;但对本项目无意义 |
| CTFusion-live | 评测时题目未发布 → 机制上干净 | **唯一结构干净的评测方式** |

### 4.2 本项目反污染运行时协议(所有 split 一致)

1. **worker 容器无外网**:challenge 容器与 worker 容器放同一 per-run docker network;
   禁止 egress(LLM API 走宿主侧 dispatcher/CLI 配置,不经挑战网络)。
   Cairn 的 `network_mode: "host"` 是 dispatch 配置项,adapter 改用自定义网络即可,
   **不改 Cairn 代码**(bring-up 时验证 ContainerManager 对自定义 network 名的支持)。
2. **worker 镜像卫生**:不装 `nyuctf` 包;不含任何 benchmark 仓库/克隆;
   `cybench_repo`、NYU 数据集(`~/.nyuctf`)只存在于宿主研究侧。
3. **flag 与题目元数据只在 harness 侧**:`challenge.json`/`metadata.json` 不进 worker 可读路径;
   worker 只见 description + files + 连接信息。
4. **trace 作弊审计**(每 batch 抽查 + holdout 全查):检索 worker 输出中的
   writeup 域名(ctftime/writeup 博客)、benchmark 包名、flag 前缀直接命中
   (EnIGMA leakage 检测 + Dreadnode 协议)。
5. **绝对分数表述纪律**:公开静态 split 上的数字一律注明"可能含训练期记忆分量",
   模型内部对比(A/B 版本、同 budget)才是主要结论;能力绝对值以 Holdout Tier B 为准。

### 4.3 各 split 的 contamination 预算

- Diagnostic/Development:**接受污染**(用于机制归因,不做能力声明;禁网消除主动作弊即可)。
- Broad:接受污染,但报告必须附 category 级数字和与已发表结果的对照。
- Holdout Tier A:低污染(CSAW 2024/2025 与 CVE-Bench 较新,但已公开;冻结+封装+限次使用);
  Tier B:结构性无污染。

---

## 5. Cairn 集成分析

基于 `cairn/docs/architecture/CAIRN_BASELINE_ARCHITECTURE.md`(冻结提交 `8e7e0ea`)与
`dispatch.example.yaml` 的实际接口。

### 5.1 集成形态(一个 benchmark adapter,两条任务源)

```text
harness(experiments/,规划中)
  ├─ TaskAdapter: nyuctf | cybench
  │    1. 解析题目元数据(challenge.json / metadata.json)
  │    2. (有服务时)docker compose up -d --force-recreate,发布到 per-run network
  │    3. 分发 files 到 worker 可读工作区
  │    4. POST /projects 创建 Cairn Project:
  │         origin = 题目描述 + 类别 + 连接信息 + 文件清单(自由文本,现状即可)
  │         goal   = "capture the flag / obtain flag{...} format flag"
  │    5. 等 Project completed 或 budget 到 → 停止 Project
  │    6. compose down --volumes(reset)
  └─ FlagEvaluator(harness 侧,独立于 Cairn):
       从完成 Intent 的 worker 输出/artifact 中提取 flag 候选
       → 与元数据 flag 精确匹配(允许 wrapper 字符归一,不允许模糊匹配)
       → 不匹配则 POST /projects/{id}/reopen(Cairn 原生语义:
          移除完成 Intent、生成 external_feedback Fact、项目回到 active)
```

关键判断:

- **无需修改 Cairn 核心**。Cairn 的 Project(origin/goal 自由文本)+ 每 Project 一个容器 +
  docker exec 执行 worker 的模型,与"一题一 Project"天然对齐。
- **`reopen` 就是现成的 external feedback 通道**:flag 校验失败 → reopen →
  worker 在下一轮读到 external_feedback Fact。这是 baseline 语义内建的回路,
  用它做"flag 错误反馈"不算修改 capability。
- **多 worker 共享环境**:Cairn 同 Project 的多个 worker 在同一容器内执行,
  对 challenge 服务的访问天然共享。风险:**有状态 challenge 服务**(交互式 pwn、
  会话型 web)可能被并发 worker 干扰 → admission 协议(§7)将"多 worker 并发下
  服务是否稳定"列为检查项;不稳定题降级为"串行友好"标注或从 Diagnostic 剔除。
- **timeout/reset/flag submission**:全部在 harness/adapter 层;Cairn 侧只用现有
  任务级 timeout 配置与项目停止 API。

### 5.2 需要的工程件(属于规划,不在本任务实现)

| 件 | 说明 |
| --- | --- |
| `nyuctf` TaskAdapter | 约 200 行:元数据解析 + compose 生命周期 + files 分发 + origin/goal 模板 |
| `cybench` TaskAdapter | 复用同一接口;额外解析 subtasks(供 partial-progress 评分,**不**给 worker) |
| FlagEvaluator | harness 侧精确匹配 + reopen 调用 + `flag_accepted/invalid` 事件 |
| Per-run docker network 脚本 | 替代 host 网络,实现禁网 |
| Repair manifest | NYU bring-up 巡检产物:broken 题清单与处置 |

### 5.3 与 Baseline Contract 的关系

以上全部属于 BASELINE_CONTRACT 允许的 evaluator / observability / harness 范畴;
不触碰 prompt、scheduler、Fact–Intent 语义、termination。

---

## 6. 四层 Split 方案

### 6.0 总览

```text
层                    来源                       规模      运行频率
Diagnostic            admission pool 筛选         5–10      高(每次机制修改)
Development           admission pool 剩余         15–24     低(通过 Diagnostic 后)
Broad                 NYU test split              200       里程碑(通过两层后)
Holdout Tier A/B      CSAW'24/'25+CVEBench / live ~40+      版本冻结后,≤数次
```

设计原则:**Diagnostic 与 Development 全部取自 NYU dev split(2013–2016)与 Cybench,
绝不触碰 NYU test split 的任何一题** —— 这样 broad 数字始终是"未见过的题",
保住官方 test set 的完整性。Cybench 不用作 broad,从中取题无代价。

### 6.1 Diagnostic Set(5–10 题)

- 来源:admission pool(见 §7 与 registry)。
- 入选标准(按优先级):
  1. Cairn baseline 每题 N 次中 solve 率 ≈ 20–80%(核心带);
  2. 或 solve 率低但**稳定推进**(subtask 命中 ≥1,或关键 artifact 产生,定义见 §7.3);
  3. 多步、存在真实搜索分支(多工具、多假设方向);
  4. 有服务交互(compose 题)优先 —— 多 worker 并发与共享服务的干扰/复用
     正是本项目要研究的协调问题;
  5. 类别覆盖:尽量不全是 crypto;目标至少覆盖 crypto/rev/web/pwn 四类
     (NYU dev 的 pwn 题质量优于 Cybench 的 2 题)。
- 排除标准:
  - baseline 0% 且无任何有效 progress(可能只是能力墙);
  - 100% 快速 solve(无诊断信息);
  - 环境损坏/flag 异常(repair manifest 命中);
  - 多 worker 并发下服务不稳定且无法隔离。
- **最终成员在 admission runs 后冻结**,记录于 registry(`diagnostic_status: admitted`),
  并产出 `docs/experiments/DIAGNOSTIC_SET_V1.md`(Phase 4 交付物,本文件只定池与协议)。

### 6.2 Development Set(15–24 题)

- 来源:同一 admission pool 中未入 Diagnostic 的题,按类别分层抽样
  (每类 2–4 题,crypto/rev 可多,pwn/web/for/msc 保底);
- 与 Diagnostic 完全不相交;
- 可含少量"Diagnostic 同类但更难"的题,用于观察改进的剂量效应;
- 运行条件:候选修改在 Diagnostic 上出现明确机制指标改善后才跑
  (参照 INIT 文档 §16 准入条件 A–E)。

### 6.3 Broad Benchmark(NYU test split,200 题)

- 冻结:tag `v20250206` + 本地 repair manifest(repair 不改变题意,只修环境/flag 缺陷;
  修复清单入库,每处修复可审计)。
- 指标(对齐 INIT 文档 §7–§9):
  - `SR@fixed_budget`(主指标;budget 三档:如 30/60/120 min wall-clock,token 上限并行固定);
  - solve-vs-budget 曲线(时间、tokens、cost、LLM calls);
  - category × year 切片(pwn/rev/cryo 是主战场;web/for 已知趋饱和,单独报告);
  - pass@k(k=3 起,单次 run 数字不作为结论 —— TATAR-LAB 单次协议已被质疑);
  - RUNTIME_INVALID 与架构失败分离。
- 频率纪律:**绝不**因 prompt 级微调或单机制试验运行全量;每次全量运行登记
  `broad_runs.md`(日期、system version、预算、动机),防止隐式 overfitting。

### 6.4 Sealed / Fresh Holdout(两层)

**Tier A —— Sealed Static(可立即准备)**

| 组件 | 内容 | 理由 |
| --- | --- | --- |
| CSAW 2024 quals(+finals)自封装 | EnIGMA 后验锚点:前沿 2024 模型 21 题仅解 2;从 osirislab 公开 repo 自行打包成 nyuctf 格式后**立即 hash 冻结**,writeup 不进入工作区 | 近期、少 writeup、与 NYU test 同分布(泛化检查的理想对照) |
| CSAW 2025(quals+finals)自封装 | 2025-10 举行,更新鲜 | 同上 |
| CVE-Bench(40 题) | ICML 2025,web CVE,zero-day 设定,flag 型,SOTA 30% | 补 web 利用轴;任务形态与 adapter 兼容(docker + flag) |

规则:封装后 hash 冻结、registry 登记、开发期**零运行**;只在候选稳定版本冻结后运行
(预计整个项目生命周期 ≤5 次);结果一次性写报告,不回看调参。
诚实声明:Tier A 仍是公开题,只能**降低**而非消除污染 —— 所以它是 sealed,不是 fresh。

**Tier B —— Fresh / Live(结构性无污染,CTFusion 方法论)**

- 机制:参加一个 CTFd-hosted、可 API 接入的 live CTF(或赛后自建 CTFd 私有镜像),
  经 CTFusion 式代理提交(每题每系统限次提交、首对去重、逐 agent 隔离)。
- 时间窗:不强行安排;遇到合适赛事(如 CSAW 2026 quals、或 CTFtime 上 CTFd 系中等规模赛事)
  即作为一次 Tier B 评测。
- 这是唯一能声称"fresh"的层;论文级结论(泛化、绝对能力)以 Tier B 为准。

---

## 7. Task Admission Protocol

### 7.1 流程

```text
candidate pool(§7.2,~28 题)
  → 环境巡检(本地 compose 起得来、flag 可校验、多 worker 并发不崩)   [harness 侧,静态]
  → baseline admission runs:Cairn baseline,每题 n=3 seeds,固定 budget
      (budget 建议:30–45 min wall / 固定 token 上限;具体值在 harness 定型时冻结,
       一经确定 admission 与后续 diagnostic 共用)
  → 逐题分类(§7.3)
  → 冻结 Diagnostic(5–10)与 Development(15–24)
  → registry 更新 diagnostic_status + admission 数据回填
```

硬性约束:

- admission 期间**不得**因结果修改 Cairn(prompt/scheduler/语义均冻结);
- admission 数据与后续 baseline 报告分开存放,避免"挑选结果"污染 baseline 叙述
  (admission 本身就是有目的的挑选,必须显式声明);
- 任何一题一旦进入 Diagnostic/Development,**不得**因后续表现差而中途换题
  (换题 = 新一轮 admission,需登记原因)。

### 7.2 Admission Candidate Pool Batch 1(28 题,registry 同步)

**NYU dev(18 题;类别 × 难度混合,避开已知损坏题)**

```text
pwn:  2016f-pwn-detective   2016q-pwn-hungman   2014f-pwn-kernel   2016q-pwn-warmup
cry:  2016f-cry-killer_cipher   2016q-cry-broken_box   2015q-cry-eps_part2   2013f-cry-stfu
rev:  2014f-rev-odd   2016f-rev-palo_alto   2015f-rev-wyvern2
web:  2016q-web-mfw   2013f-web-historypeats   2016q-web-i_got_id
for:  2016q-for-yaar_haar_fiddle_dee_dee   2015q-for-pcapin
msc:  2016q-msc-regexpire   2014f-msc-pps
```

**Cybench(10 题;difficulty ≥ 2,本地克隆已验证,偏好有服务的多 subtask 题)**

```text
crypto: noisy-crc(3)  ezmaze(3)  diffecient(3)  Permuted(3)  robust-cbc(4)
web:    frog-waf(3)   LockTalk(3)
rev:    matrix-lab-2(2)
for:    Data Siege(2)
misc:   just-another-pickle-jail(5)
```

(括号内为 metadata difficulty 0–5;chunky 因 `internet.necessary=true` 排除;
motp 因 GPL 许可(AISI 移植版同此)排除。)

### 7.3 逐题分类标准

| 类别 | 判据 | 处置 |
| --- | --- | --- |
| trivial | 3/3 seeds 快速 solve(<1/3 budget) | 剔除出 Diagnostic;可留 Development 作对照 |
| discriminative | solve 率 ∈ [1/3, 5/6] 或波动大 | **Diagnostic 优先** |
| deep-progress-unsolved | solve 0/3,但 ≥1 seed 命中 subtask(Cybench)或产出关键中间 artifact(NYU:达到题类典型攻击阶段,由 harness 的 partial-progress 规则判定,规则先于运行冻结) | **Diagnostic 优先** |
| zero-progress | solve 0/3 且无有效推进 | 剔除(能力墙嫌疑) |
| broken | 环境起不来 / flag 校验异常 / 多 worker 并发必崩 | 修复或永久剔除,记 repair manifest |

### 7.4 与 failure taxonomy 的衔接

admission runs 产出的 trace 同时是 failure taxonomy(F01–F14)的第一批标注素材;
每道入池题至少完成一次粗标注(duplicate exploration / fact 未复用 / premature termination 等),
作为后续机制假设的证据基线。

---

## 8. 为什么不选其他候选作为主 benchmark(明确理由)

1. **Cybench**:40 题太少(类别统计无意义,pwn 仅 2 题);前沿饱和(93–100%,
   且 Dreadnode 证明相当部分是作弊);污染严重且上游仓库自身缺 9 题、无版本发布。
   **但它保留了二级价值**:官方难度标注 + subtask/hints 元数据是所有候选中最好的
   partial-progress 素材,故降级用作 Diagnostic/Development 池,不作能力刻度。
2. **CyberGym**:不是 flag 型 CTF(差分 sanitizer PoV),任务分布单一(C/C++ fuzz 目标),
   Level 1 官方自认近饱和,基础设施最重(240GB–10TB,本地必须部署 submit server),
   且 flag 语义失真(any-crash ≠ 目标漏洞复现)。与"CTF-oriented CRS"的项目定位错位。**不选。**
   (若未来增加 exploitation 专项轨,再评估其 Level 0 / >100B-PoC 层。)
3. **CTFusion**:不是任务合集,无法提供 broad test set;其静态部分就是 NYU(180 题修复版,
   承诺发布但截至调研未发布)。**采纳其方法论**(live 评测 + 代理提交 + 作弊检测)作为
   Holdout Tier B 机制,并参考其 NYU 修复经验(26/210)指导我们的 repair manifest。
4. **CTF-Dojo**:658 题是真实优势,但 2025-08 才发布,集成/冻结/可比性信息不足,
   adapter 投入与 V1 目标不成比例。**列为 Development 层未来扩容池**(V2 候选)。
5. **CVE-Bench / AutoPenBench / PentestEval / CAIBench / ExploitGym / CyberGym-E2E**:
   各有价值但都不如 NYU 适合作为 flag 型多 agent 系统的主干(规模、类别均衡、可比性、
   成本至少一项不满足);CVE-Bench 因"新 + 难 + flag 型 + docker"被选入 Holdout Tier A。
6. **InterCode-CTF / HTB / CyberSecEval**:分别因饱和+泄漏、不可再分发、过小,只可能承担
   冒烟测试角色,不进入正式 split。

---

## 9. 第一批实际运行建议(本任务不执行,仅规划)

按优先级:

1. **P0 前置**:启用 Docker(WSL 集成);验证 Cairn container 后端 + 自定义 docker network。
2. **Bring-up 巡检(小规模)**:NYU v20250206 下载;对 §7.2 的 18 题 NYU dev 题逐题
   `compose up` + flag 自校验(用官方 flag 走一遍 evaluator,验证 harness 闭环),
   产出 repair manifest;Cybench 10 题同样处理(含 `init_script.sh` 文件分发验证)。
   每题巡检分钟级,不涉及 LLM。
3. **Admission runs**:Cairn baseline(冻结版本、固定模型、固定 worker 数、固定 budget)
   对 28 题 × 3 seeds。此为项目第一次真实多 agent 运行,同时检验 events/trace 管线。
4. 冻结 Diagnostic/Development,写 `DIAGNOSTIC_SET_V1.md`,进入 Phase 5(baseline report)。

---

## 10. 遗留与风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| NYU ~10–15% 题目损坏 | broad 数字与已发表结果有偏差 | repair manifest 全程留痕;损坏题"修复或剔除"二选一,不改题意 |
| CSAW 2013–2016 dev 题偏老偏易 | Diagnostic 全部 trivial,无人选带 20–80% | Cybench 池补难度;必要时 pool 扩至 dev 全 57 题 |
| 多 worker 并发干扰有状态服务 | admission 分类失真 | §7.1 环境巡检含并发稳定性检查 |
| Cairn worker 容器无外网后 CLI(claudecode/codex)无法调 API | 全部运行不可行 | LLM API 白名单经宿主侧路由(dispatcher 侧 env/proxy),bring-up 时验证 |
| 训练期记忆污染静态分数 | 绝对能力高估 | §4.2 协议 + §4.3 表述纪律;结论以 A/B 对比与 Tier B 为准 |
| 2026-09 后 NYU/Cybench 上游再变更 | 复现漂移 | 全部 pin(nyuctf==1.1.1 / tag v20250206;cybench commit ca483c6),registry 记录 |

---

## 附:裁决速查

```text
Primary benchmark:        NYU CTF Bench
Diagnostic Set source:    NYU dev(2013–2016)∪ Cybench(difficulty≥2),admission 筛选
Development Set:          同池剩余,15–24 题,与 Diagnostic 不相交
Broad Benchmark:          NYU CTF test split(200 题,v20250206 + repair manifest)
Fresh/Sealed Holdout:     Tier A: CSAW 2024/2025 自封装 + CVE-Bench(40)
                          Tier B: CTFusion 方法论 live CTF
不选:                     CyberGym(语义/成本/饱和)、CTFusion 作任务源(非数据集)、
                          Cybench 作主 benchmark(规模/饱和/污染)、CTF-Dojo(V2 再议)
第一批运行:               §7.2 的 28 题 admission(先 18+10 题环境巡检,再 3 seeds baseline)
```
