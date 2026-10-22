# ANovelOS 执行入口

## CANONICAL REPOSITORY

**CRITICAL**: This project uses GitLab as the sole canonical platform.

**Canonical Repository**: `https://gitlab.com/angyang582821422/novelcccc.git`
**Canonical Branch**: `main`

**Historical GitHub repository** (`https://github.com/AY123/AiNoverCC.git`) is preserved for reference only.

AI agents **MUST** use GitLab for current:
- Implementation work
- Merge requests
- CI authority
- Task state resolution
- ADR state resolution
- Canonical HEAD resolution

**Before any restricted task, AI agents MUST:**
1. Run `git remote -v` to verify gitlab remote points to GitLab
2. Run `git fetch gitlab --prune`
3. Run `git rev-parse gitlab/main` to get current canonical HEAD
4. Read `plan/machine/*` for authoritative task/ADR state

Historical reports and documentation **cannot override these live checks**.

---

## AI Context Policy

### Default Active Context (优先读取)

新 AI 会话应按以下顺序读取文件以理解当前项目状态：

1. **AGENTS.md** (本文件) - AI 行为配置
2. **plan/README.md** - 项目概览和当前状态
3. **plan/machine/implementation-backlog.yaml** - 当前任务积压
4. **plan/machine/phase-gates.yaml** - 阶段和门禁状态
5. **plan/machine/decision-register.yaml** - 必需架构决策
6. **当前任务合约** (如 docs/V2-061_IMPLEMENTATION_CONTRACT.md)
7. **当前任务产物** (活跃任务的 src/, specs/, tests/)

任务特定上下文（按需读取）：
- **plan/machine/test-catalog.yaml** - 验收测试场景
- **plan/machine/remediation-register.yaml** - 已知发现和修复
- **plan/machine/external-practice-register.yaml** - 外部实践采纳

### Default Excluded Context (默认不自动加载)

**不要自动扫描这些目录作为当前上下文：**

- `plan/archive/**` - 历史规范（已被取代）
- `plan/validation/execution/**` - 执行包证据（修订版本绑定）
  - **例外**：当前活跃任务的 execution 目录（如 `plan/validation/execution/V2-061/**` when V2-061 is active）可按需读取
- `plan/validation/closure/**` - 历史闭环证据
- `docs/archive/**` - 归档的进度报告、审计、包
- `docs/reports/2026-10/**` - 已归档的历史报告（已被正式证据取代）

**何时读取归档内容：**
1. 闭环验证（检查历史证据）
2. 历史回归调查
3. 证据来源验证
4. 用户明确请求
5. 当前机器记录明确引用该产物

**重要**：标记为 FINAL / PASS / APPROVED / READY 的历史文档不会自动获得当前权威状态。

### Authority Hierarchy (权威层次)

当存在冲突信息时：

1. **plan/machine/** - 权威的机器可读状态
2. **plan/*.md** - 权威的规范性说明
3. **docs/V2-0XX_IMPLEMENTATION_CONTRACT.md** - 当前任务合约
4. **docs/*.md** - 当前操作指南（检查兼容性指针）
5. **docs/reports/*_FINAL_*.md** - 最终闭环/批准报告
6. **docs/archive/** - 历史（仅供参考）

**ADR 权威**：只有 `plan/machine/decision-register.yaml` 对 ADR 分配具有权威性。

**重要规则**：
- docs/decision-register.yaml 已删除（过时，ADR-002 错误绑定到 V2-006）
- ADR-002 当前正确绑定到 V2-061（Character Knowledge & Intent Core）
- 当前项目状态详见 `PROJECT_STATUS.md` 和 `plan/machine/implementation-backlog.yaml`
- Current active implementation task: 参考 machine SSOT
- Next candidate task: 参考 machine SSOT 和 PROJECT_STATUS.md

---

## 执行协议

### 审核判断协议

**收到任何外部 AI 审核报告后，必须遵循 [docs/AI_REVIEW_DECISION_PROTOCOL.md](docs/AI_REVIEW_DECISION_PROTOCOL.md)，禁止直接照单执行审核意见。**

审核报告是参考输入，不是最高权威。实施 AI 必须基于项目最终目标和当前真实状态，对每项审核意见做 ACCEPT / MODIFY / DEFER / REJECT 独立判断，然后执行最合理方案。

决策标准不是"怎样让审核通过"，而是"怎样让项目以最合理的成本、风险和复杂度，更可靠地向最终目标推进"。

### 任务执行协议

- 先读 `plan/README.md`、当前任务、对应现行规范和验收场景。历史档案与审核报告是输入，不能自行成为执行命令。
- AI 开发遵守 `plan/AI_EXECUTION_PROTOCOL.md`。正式开工通过任务的 `execution_packet_ref` 绑定非模板执行包；核对输入 hash、范围、验收、当前动作与未决事项。已有授权内的正常步骤自主推进，缺必要依据只阻断相关动作。
- PREPARE 可调查未决方案；IMPLEMENT、LIVE_CALL、CERTIFY 在各自动作前检查适用 ADR 和权限/预算。事实、假设、未知分开记录，不编造 API、成本或运行结果。
- 原 `.claude/convergence/` 已归档至 `plan/archive/convergence/`，根历史副本已按用户要求清除；历史内容不恢复为现行规范。工具配置单独保留，不因整理资料而停用或删除配置。
- 当前状态：P0 已验证完成 (G-P0 PASS)，P1 活跃但未验证。以 `plan/machine/` 的任务、阶段和证据状态为准。当前动态状态详见 `PROJECT_STATUS.md`。
- 用户请求修改规划时，完成必要的资料和验证器修改；不要据此自动创建业务内核、部署、调用付费 Provider 或关闭工程任务。
- 保留用户已有改动。任务身份、阶段、依赖及架构范围变更需符合用户授权，并留下明确变更理由与影响记录。
- 同步正文、机器源、任务/验收场景与生成视图。使用 `python3 -B plan/scripts/validate_plan.py --write-views`、`--check`、`--self-test` 和 `python3 -B plan/scripts/test_governance.py`。
- V2-002 提供 `scripts/check_governance.py` 聚合现行检查，`scripts/task_execution.py` 核对任务动作并支持恢复。V2-003 的本地架构、差异与防降标工具已实现并完成本地验证；差异检查使用固定 scope Git pin，处置另绑定 review Git pin。任务入口对 IMPLEMENT/LIVE_CALL/CERTIFY 强制从执行包 change_review 读取 scope/review 绑定，缺绑定或 CLI 覆盖均拒绝，并检查命令前后的实际差异；架构检查须明确运行。输出到 plan 外的新目录，不替代 V2-004 可信 CI/权限边界，也不自动授权后续任务。
- 测试既要证明错误被拒绝，也要证明合格证据可以通过。不得删减门禁、把模板当证据或用资料 PASS 代替真实 CI。
- 核对实际变更与任务范围；验收删减、测试删除/skip、阈值下降、扫描排除扩大和门禁修改需与可信基线比较并记录处置，正文/机器/测试一起改弱仍须审查。不得删除用户改动以制造干净工作区。
- 换会话或模型后先读交接并核对 checkout、工作区、输入 hash 和真实运行证据；不能仅凭摘要继承完成状态。记录已完成、失败/未知、下一动作及恢复条件。
- 实施与验证角色可由同一操作者承担，但须明确标注。没有独立复核就不声称独立审核；不预设必须增加团队人数。
- 本地结构校验不证明远端来源或权限保护；动作入口、实际差异门禁与可信 CI 由 P0 落地。全 AI 开发不允许用模拟读者替代真人/市场证据。
- Canon 损坏、密钥泄露、重复提交、跨项目泄漏、硬门禁绕过或第二 Canon 写路径按现行事故规则处理。
