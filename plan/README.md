# ANovelOS 正式架构建设实施资料

Plan Version：1.3.1；更新日期：2026-10-08；历史资料来源基线：`5cffff8`。本目录是正式实施入口。审核报告的版本不替代本计划版本。

v1.3.1 是治理修订：V2-006 任务身份调和（范围拆分与重新归属），正式将任务数从 60 更新为 61。见 [v1.3.1 变更记录](changes/2026-10-08_V2_006_TASK_IDENTITY_RECONCILIATION.md)。

v1.3.0 将全 AI 推进的六项措施落实为[执行协议](AI_EXECUTION_PROTOCOL.md)、执行包 Schema、交接模板、本地检查及 P0 验收要求。见 [v1.3.0 变更与验证说明](changes/2026-09-22_AI_EXECUTION_GOVERNANCE.md)。

P0—P14、双 Anchor 架构保持不变。61 个任务身份/阶段/依赖按机器源记录。验收场景按机器源分别记录实施和验证状态。本地回归不是业务运行或可信 CI 认证。

保留 [v1.2.2](changes/2026-09-21_REVIEW_ROUND3_ADOPTION.md)、[v1.2.1](changes/2026-09-21_REVIEW_REFRESH_ADOPTION.md)、[v1.2](changes/2026-09-21_REVIEW_ADOPTION.md)和 [v1.1](changes/2026-09-20_EXTERNAL_PRACTICES_ADOPTION.md)的历史变更记录；旧版本数字与结论只适用于其声明时点。

**当前状态：P0 阶段已完成并验证（V2-001 through V2-004 CLOSED）。P1 阶段活跃（V2-005, V2-006, V2-061, V2-007 CLOSED; V2-008 OPEN, requires ADR-004）。** Plan v1.3.1，61 任务。文档校验通过只说明本资料包内部检查通过，不代表 CI、数据库或真实模型已经通过。

开工前清理已按用户授权完成：根目录旧资料的重复副本已删除，独有文件补充归档；旧根 ZIP 的 Git 恢复依据和逐文件去向保存在项目根下 `docs/archive/remediation/repository-layout-migration.md` / `.json`。来源登记中的 `origin` 是历史位置，不要求根副本继续存在。

V2-001 已 CLOSED：具备最小 Python 骨架、锁定安装、本地真实 PostgreSQL 测试和远端 CI 验证。P0 已通过 G-P0 出口审核。见[执行包](validation/execution/V2-001/execution-packet.yaml)及 [ADR-001](decisions/ADR-001_RUNTIME_AND_LOCKING.md)。

## 阅读与执行顺序

1. [治理与资料权威](00_GOVERNANCE_AND_SOURCE_AUTHORITY.md)：确定什么是现行规范，如何处理旧资料。
2. [目标、首期范围与成功口径](01_PRODUCT_SCOPE_AND_SUCCESS.md)、[架构基线](02_ARCHITECTURE_BASELINE.md)：掌握产品边界及模块职责。
3. [路线与门禁](08_ROADMAP_AND_GATES.md)、[阶段任务表](generated/PHASE_TASK_REGISTRY.md)：按被冻结的 P0—P14 路线工作。
4. [P0 执行方案](PHASE_0_REPOSITORY_BOOTSTRAP_EXECUTION.md)：P0 已验证完成（V2-001～004 CLOSED）。
5. 开始具体任务前，阅读[AI 执行协议](AI_EXECUTION_PROTOCOL.md)、相应规范、[任务执行规则](09_TASK_EXECUTION_GUIDE.md)与[决策和整改说明](10_DECISIONS_AND_REMEDIATION.md)。准备与实施动作分开，正式执行包必须在 `validation/` 下留存，不能用模板作开工凭证。

## 现行规范

| 文件 | 职责 |
|---|---|
| [00](00_GOVERNANCE_AND_SOURCE_AUTHORITY.md) | 权威、替代关系、术语和证据语义 |
| [01](01_PRODUCT_SCOPE_AND_SUCCESS.md) | 中文网文目标、范围、自动化和成本口径 |
| [02](02_ARCHITECTURE_BASELINE.md) | 模块化单体、边界、依赖、技术选择策略 |
| [03](03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md) | Narrative、Canon、Artifact、权限、幂等与历史证据 |
| [04](04_GENRE_AND_STORY_FIXTURES.md) | 双 Anchor、合法边界、标准测试书与叙事持续性 |
| [05](05_PRODUCTION_CONTEXT_QUALITY_REPAIR.md) | Contract、Context、Gateway、Workflow、Q0–Q3、Repair |
| [06](06_CERTIFICATION_AND_PRODUCT_EVALUATION.md) | 连续章节、真人阅读、版本绑定和认证证据 |
| [07](07_PLATFORM_SECURITY_AND_DELIVERY.md) | 工程、隔离、CI、安全、恢复与阶段启用 |
| [08](08_ROADMAP_AND_GATES.md) | 阶段准入/退出与里程碑完成条件 |
| [09](09_TASK_EXECUTION_GUIDE.md) | OPEN→CLOSED、执行/证据规则与复现命令 |
| [10](10_DECISIONS_AND_REMEDIATION.md) | 已采纳决定、未决 ADR、审核整改归属 |
| [AI 执行协议](AI_EXECUTION_PROTOCOL.md) | 全程 AI 开发的任务边界、动作前提、证据与交接；不新增业务架构 |

## 机器资料

- [最低治理义务](machine/governance-baseline.yaml)、[类型化执行证据](schemas/evidence-record.schema.json)、[基础来源历史索引](machine/foundational-reference-register.yaml)。
- [AI 执行约束登记](machine/ai-execution-policy.yaml)：六项措施的责任、场景与实际实现边界；[执行包 Schema](schemas/execution-packet.schema.json)、[执行包模板](templates/EXECUTION_PACKET.yaml)、[交接模板](templates/AI_HANDOFF_RECORD.yaml)。
- [任务清单](machine/implementation-backlog.yaml)：61 个任务的唯一身份、阶段、依赖和验收映射。
- [阶段门禁](machine/phase-gates.yaml)、[里程碑](machine/milestones.yaml)、[CI 门禁](machine/ci-gates.yaml)。
- [验收场景目录](machine/test-catalog.yaml)：逐套件记录状态与实际执行证据，未实施场景仍为计划。
- [决策登记](machine/decision-register.yaml)、[整改登记](machine/remediation-register.yaml)。
- [权限与证据政策](machine/authority-policy.yaml)、[来源登记](machine/source-register.yaml)。
- [外部经验采纳登记](machine/external-practice-register.yaml)：公开来源、证据局限、本地改造、关联任务/验收场景及暂缓范围。
- [机器结构约束](schemas/implementation-task.schema.json)、[校验程序](scripts/validate_plan.py)、[校验结果](validation/plan-validation.json)。

`machine/` 保存事实，`generated/` 是其只读视图。运行 `python3 plan/scripts/validate_plan.py --write-views` 更新视图；运行 `python3 plan/scripts/validate_plan.py --check` 检查一致性。PyYAML、jsonschema 已随 V2-001 纳入根 `uv.lock`；使用锁定环境。活动执行包必须在计划变动后核对来源并更新快照/hash。

## 历史资料与实施状态

[archive/](archive/) 保留来源快照；内部的 NORMATIVE、FINAL、READY、PASS 等标签都是历史内容，不构成当前授权。旧 Schema 不进入生产验证器的自动扫描路径，需经任务修正、正反例测试后进入未来的 `specs/`。

**实施状态（当前）**：V2-001 through V2-004 通过 [G-P0 出口审核](validation/closure/G-P0-38b0c57/)（M0、4 任务、16 个实施契约、146 步验收）。V2-005, V2-006, V2-061, V2-007 已 CLOSED。V2-008 (NarrativeDelta Implementation) 及更高任务 OPEN。下一步为 ADR-004 formal decision；完成 ADR-004 后才准备 V2-008 execution packet。实施历史记录见 validation/execution/。

规划验证还需运行 `python3 -B plan/scripts/test_governance.py` 与 `python3 -B plan/scripts/test_ai_execution.py`。最低义务基线不可由 `--write-views` 自动放宽；原始审核和新复测结果分开保留。V2-003 的 `scripts/check_architecture.py` 扫描完整生产包并区分 Canon 公共提交服务与内部写能力；`scripts/check_changes.py` 使用固定 scope/review Git pin 审查实际变化，`task_execution.py` 对受限动作按执行包绑定强制运行命令前后差异检查。用法见[任务执行指南](09_TASK_EXECUTION_GUIDE.md)。这些本地工具不能抵抗共享写权限者修改检查器，可信 CI 和有效权限保护仍须 V2-004 实施。V2-017 的[设计执行包](task-packets/V2-017_PLANNING_CONTRACT_PACKET.md)在 P4 消费，不替代任务开工时的正式记录。
