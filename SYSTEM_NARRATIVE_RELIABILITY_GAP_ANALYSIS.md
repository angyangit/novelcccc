# ANovelOS 系统级叙事可靠性差距分析与实施方案
## System-Level Narrative Reliability Gap Analysis & Implementation Plan

**Document Type**: System Analysis & Execution Plan  
**Date**: 2026-10-30  
**Canonical Repository**: `https://github.com/angyangit/novelcccc.git`  
**Current Branch**: `review/adr-008-and-fixtures-decision` (HEAD: 9d8dd08)  
**Canonical Branch**: `main`  
**Authority**: Owner Direction — 从测试小说修补转向正式系统级长篇叙事可靠性建设

---

## 执行摘要 (Executive Summary)

### 核心发现 (Core Finding)

三本30章实验小说暴露的**系统性叙事可靠性故障**均源于**生产流水线尚未实现**，而非已实现模块的设计缺陷。

**The fundamental narrative reliability failures discovered in the three 30-chapter experimental novels are caused by the absence of the production pipeline, not by defects in implemented foundation modules.**

### 已实现与未实现的边界 (Implemented vs. Missing Boundary)

| 层级 | 已实现 (P0-P3 VERIFIED) | 未实现 (P4-P9 NOT_VERIFIED) |
|------|------------------------|----------------------------|
| **Domain** | ✅ Entity Identity, Relationship, Knowledge, Events, Promises, NarrativeDelta | ❌ 无生产使用者 |
| **Canon** | ✅ Immutable commits, snapshots, isolation, idempotency | ❌ 无生产写入路径 |
| **Genre** | ✅ Extension loading, binding, policy validation | ❌ 无生产规则执行 |
| **Planning** | ❌ Contract Compiler (V2-017 NOT_STARTED) | ❌ Intent, transition plan |
| **Context** | ❌ Context Compiler (V2-018 NOT_STARTED) | ❌ 必需前文选择 |
| **Gateway** | ❌ Model Gateway (V2-019 NOT_STARTED) | ❌ Provider 调用 |
| **Workflow** | ❌ Single Chapter Workflow (V2-020 NOT_STARTED) | ❌ 候选生成编排 |
| **Extraction** | ❌ NarrativeDelta Extractor (V2-021 NOT_STARTED) | ❌ 新章节事实提取 |
| **Validation** | ❌ Q0-Q3 Validators (V2-022~025 NOT_STARTED) | ❌ 确定性与语义校验 |
| **Integration** | ❌ CommitPermit (V2-026 NOT_STARTED) | ❌ 验证-提交集成 |
| **Certification** | ❌ 10/30-Chapter Runners (V2-033~040 NOT_STARTED) | ❌ 端到端认证 |

**Current Status**: P0-P3 (Foundation) = VERIFIED, P4-P9 (Production) = NOT_STARTED

### 根本原因 (Root Cause)

三本小说的生成使用了**独立实验脚本**，完全绕过了正式ANovelOS架构：

1. **无Contract编译** → 章节意图、转折规划缺失
2. **无Context编译** → 旧章节重要事实未进入上下文
3. **无NarrativeDelta提取** → 新章节事实未录入Canon
4. **无Canon持续更新** → 每章独立生成，无状态累积
5. **无确定性验证** → 主角名称、人物关系、资源消耗未校验
6. **无语义验证** → 事件重复、因果断裂、时间线矛盾未检测
7. **无失败阻断** → 错误章节继续污染后续生成

**实验脚本的Prompt构造与验证逻辑均在ANovelOS架构之外，故障是预期结果。**

---

## 第一部分：当前代码能力盘点 (Current Implemented Capabilities)

### 1.1 已实现并验证的基础能力 (P0-P3 VERIFIED)

#### Domain Layer (P1 VERIFIED)

**V2-005: Entity Identity** (CLOSED)
- ✅ `EntityId` with scope, type, name, aliases
- ✅ Identity resolution across mentions
- **用途**: 识别"王林"、"林枫"等主角身份
- **限制**: 无生产使用者调用此能力

**V2-006: Entity Relationship** (CLOSED)
- ✅ `Relationship` types: romantic, hierarchical, alliance, conflict
- ✅ Bidirectional tracking with evidence
- **用途**: 追踪"道侣"vs"师妹"关系状态
- **限制**: 无生产使用者录入关系变化

**V2-061: Character Knowledge & Intent** (CLOSED)
- ✅ `KnowledgeItem` with temporal scope
- ✅ Intent modeling for goals and motivations
- **用途**: 追踪人物知识与目标
- **限制**: 无生产使用者更新知识库

**V2-007: Event Timeline & Promises** (CLOSED)
- ✅ `EventOccurrence` with timestamps
- ✅ `Promise` tracking for未完成事件
- **用途**: 时间线一致性、伏笔追踪
- **限制**: 无生产使用者填充时间线

**V2-008: NarrativeDelta** (CLOSED)
- ✅ Typed operations: ADD_CHARACTER, CHANGE_RELATIONSHIP, CONSUME_RESOURCE, ADVANCE_TIME, etc.
- ✅ Precondition validation framework
- **用途**: 表达章节产生的世界变化
- **限制**: 无生产Extractor从章节正文提取Delta

#### Canon Layer (P2 VERIFIED)

**V2-009: Canon Repository** (CLOSED)
- ✅ PostgreSQL persistence with migrations
- ✅ Immutable artifact storage with SHA-256 hashing
- ✅ Snapshot rebuild from commit log
- **用途**: 可信存储与历史追溯
- **限制**: 无生产提交路径使用

**V2-010: CanonCommitService** (CLOSED)
- ✅ Atomic commit with permit verification
- ✅ Idempotent recovery with conflict detection
- ✅ Receipt generation with full provenance
- **用途**: 事务性Canon更新
- **限制**: 测试中使用`TestPermitVerifier`，无生产Permit签发

**V2-011/012**: Not started (projection, serialization)

#### Genre Layer (P3 VERIFIED)

**V2-013: GenrePack Loader** (CLOSED)
- ✅ Extension identity verification
- ✅ Project binding and isolation
- ✅ Policy validation (advancement rules, resource constraints)
- **用途**: 题材规则加载与验证
- **限制**: 无生产Executor执行规则

**V2-014/015/016**: Not started (rule execution, composite policies)

### 1.2 已实现但缺乏端到端集成 (Implemented but Isolated)

**所有P1-P3模块**均通过单元测试与集成测试验证，但：

- ❌ 无生产级章节生成流程调用这些模块
- ❌ 无Context Compiler将Canon状态编译为Writer输入
- ❌ 无Delta Extractor将Writer输出录入Canon
- ❌ 无Validator在提交前执行检查

**结论**: 基础能力已证明可用，但**生产闭环不存在**。

---

## 第二部分：生产闭环的缺失环节 (Missing Production Pipeline)

### 2.1 目标工作流 (Target Production Workflow)

```
SeriesVision / StoryContract
    ↓
Canon Snapshot (当前世界状态)
    ↓
Context Compiler (选择必需前文)
    ↓
Chapter Intent / Transition Plan (本章目标)
    ↓
Prompt Construction (契约+上下文+意图)
    ↓
Writer (Model Gateway → Provider)
    ↓
Candidate Chapter (正文草稿)
    ↓
NarrativeDelta Extraction (提取事实变化)
    ↓
Q0 Validation (确定性: 主角名称、长度、格式)
    ↓
Q1 Validation (Canon一致性: 关系、资源、时间线)
    ↓
Q2 Validation (Genre规则: 境界合法性、商业逻辑)
    ↓
Q3 Validation (Transition质量: 因果承接、场景转移)
    ↓
CommitPermit Decision (通过/拒绝/修复)
    ↓
CanonCommit (事务性提交新Delta)
    ↓
Next Chapter (迭代)
```

### 2.2 当前缺失的关键组件 (Missing Critical Components)

#### 缺失组件1: Contract Compiler (V2-017, P4)

**职责**: 
- 定义章节级别的叙事契约(intent, tone, pacing)
- 规划章节转折与冲突
- 绑定Canon约束与Genre规则

**当前状态**: NOT_STARTED
- ADR-008 已接受(候选overlay与Contract编译绑定)
- 执行包: `validation/decisions/adr-008-acceptance-3a07441/`
- 规范: `plan/05_PRODUCTION_CONTEXT_QUALITY_REPAIR.md`

**影响**: 
- ❌ 无章节意图规划 → 情节跳跃、无因果推动
- ❌ 无转折设计 → 重复事件、缺乏冲突

#### 缺失组件2: Context Compiler (V2-018, P5)

**职责**:
- 从Canon快照提取当前世界状态
- 选择语义相关的历史章节与事实
- 处理必需集合溢出(超Token预算)
- 生成Writer可用的structured context

**当前状态**: NOT_STARTED
- ADR-009 REQUIRED (Context必需项溢出与选择解释)
- 规范: `plan/05_PRODUCTION_CONTEXT_QUALITY_REPAIR.md`

**影响**:
- ❌ 重要旧事实未进入上下文 → 前章结果被忽略
- ❌ 无语义相关性排序 → 关键信息被截断
- ❌ 无显式必需集合 → 人物关系、资源状态丢失

**三本小说的Context构造**:
- Novel A/B/C: 仅包含上一章正文 + 主角名称
- ❌ 无财务状态累积 → Novel A 340万资金缺口
- ❌ 无人物关系追踪 → Novel B 道侣/师妹矛盾
- ❌ 无事件去重 → Novel B 重复拍卖会

#### 缺失组件3: Model Gateway (V2-019, P5)

**职责**:
- Provider抽象(API调用、重试、超时)
- 预算管理与UNKNOWN处理
- 请求/响应日志与追踪

**当前状态**: NOT_STARTED
- ADR-010 REQUIRED (Provider UNKNOWN预算与逻辑请求身份)
- 规范: `plan/05_PRODUCTION_CONTEXT_QUALITY_REPAIR.md`

**影响**:
- ❌ 无统一Provider接口 → 实验脚本直接调API
- ❌ 无预算控制 → 无成本追踪
- ❌ 无调用追溯 → 无法定位生成问题章节的输入

#### 缺失组件4: Single Chapter Workflow (V2-020, P6)

**职责**:
- 编排完整单章生成流程
- 管理Draft/Candidate/Accepted状态
- 协调Compiler→Writer→Extractor→Validator

**当前状态**: NOT_STARTED
- 规范: `plan/05_PRODUCTION_CONTEXT_QUALITY_REPAIR.md`

**影响**:
- ❌ 无统一编排层 → 实验脚本各自实现
- ❌ 无状态管理 → Draft/Final混淆
- ❌ 无重试/检查点 → 失败无法恢复

#### 缺失组件5: NarrativeDelta Extractor (V2-021, P6)

**职责**:
- 从候选章节正文提取事实变化
- 生成typed NarrativeDelta操作
- 验证Delta前置条件

**当前状态**: NOT_STARTED
- 规范: `plan/05_PRODUCTION_CONTEXT_QUALITY_REPAIR.md`

**影响**:
- ❌ 新章节事实未录入Canon → 每章独立生成
- ❌ 无状态累积 → 后续章节无法获取前章结果
- ❌ 无自动检测 → 关系变化、资源消耗未追踪

**三本小说的Delta提取**:
- ❌ 完全缺失 → 所有章节孤立
- ❌ Novel A: 财务变化未追踪，导致340万缺口
- ❌ Novel B: 柳梦关系变化未记录，道侣→师妹无解释

#### 缺失组件6: Q0-Q3 Validators (V2-022~025, P7)

**Q0 - 确定性验证器 (V2-022)**:
- 主角名称一致性(真实NAME，非仅计数)
- 篇幅要求(中文字数、段落数)
- 格式合规(章节标题、结构)

**当前状态**: NOT_STARTED
- ADR-011 REQUIRED (必跑检查集与Permit授权)

**影响**:
- ❌ 主角名称未校验 → **Phase 3 Agent错误声称Ch11-15是不同主角**
- ❌ 实际问题: 验证仅计数"protagonist mentions"，未验证具体名称

**Q1 - Canon一致性验证器 (V2-023)**:
- 人物关系状态检查(关系类型变化需解释)
- 资源消耗合法性(不可重复消耗)
- 时间线一致性(事件顺序、时间跨度)
- 已完成事件去重

**当前状态**: NOT_STARTED

**影响**:
- ❌ Novel A: 340万资金缺口未检测
- ❌ Novel B: 道侣→师妹无解释未拒绝
- ❌ Novel B: 筑基丹三次消耗未检测
- ❌ Novel B: 重复拍卖会未检测

**Q2 - Genre规则验证器 (V2-024)**:
- 修炼境界合法性(progression rules)
- 商业逻辑合理性(business rules)
- 题材特定约束

**当前状态**: NOT_STARTED

**影响**:
- ❌ 境界突破缺乏依据未检测
- ❌ 商业交易不合理未拒绝

**Q3 - Transition质量验证器 (V2-025)**:
- 因果承接检查(前章关键结果是否被处理)
- 场景转移合理性
- 情节推动评估

**当前状态**: NOT_STARTED

**影响**:
- ❌ 前章结果被忽略未检测
- ❌ 无关情节突然插入未拒绝
- ❌ 缺乏因果的跳跃未检测

#### 缺失组件7: CommitPermit Integration (V2-026, P7)

**职责**:
- 聚合Q0-Q3验证结果
- 做出ACCEPT/REJECT/REPAIR决策
- 阻止错误章节提交Canon

**当前状态**: NOT_STARTED
- ADR-011 REQUIRED (必跑检查集与Permit授权)

**影响**:
- ❌ 验证失败章节仍被接受
- ❌ 错误继续污染后续章节
- ❌ 无修复/重试机制

---

## 第三部分：故障-任务映射 (Failure-to-Task Mapping)

### 3.1 三本小说暴露的核心缺陷与对应任务

| 缺陷类型 | 具体表现 | 缺失能力 | 对应任务 | 当前状态 |
|---------|---------|---------|---------|---------|
| **主角身份突变** | Phase 3 Agent错误报告Ch11-15不同主角(实际均为王林) | Q0: 主角NAME一致性验证 | V2-022 | NOT_STARTED |
| **人物关系无解释重置** | Novel B: 柳梦从"道侣"→"师妹"无过渡 | Q1: 关系变化检查 + Delta录入 | V2-021, V2-023 | NOT_STARTED |
| **资源重复消耗** | Novel B: 筑基丹三次消耗(Ch1/Ch2/Ch5) | Q1: 资源消耗追踪 | V2-021, V2-023 | NOT_STARTED |
| **事件重复生成** | Novel B: 两次天宝阁拍卖会 | Q1: 事件去重检查 | V2-021, V2-023 | NOT_STARTED |
| **财务/时间线缺口** | Novel A: 340万资金缺口无解释 | Q1: 资源状态累积 + Context Compiler | V2-018, V2-021, V2-023 | NOT_STARTED |
| **前章结果被忽略** | 所有小说: 旧章节事实未进入上下文 | Context Compiler必需集合 | V2-018 | NOT_STARTED |
| **情节因果断裂** | 新章节与前章无承接 | Q3: Transition检查 + Contract规划 | V2-017, V2-025 | NOT_STARTED |
| **错误章节通过验证** | 验证仅计数mentions，未验证NAME | Q0: 确定性验证 | V2-022 | NOT_STARTED |
| **错误污染后续章节** | 无阻断机制，错误累积 | CommitPermit决策 | V2-026 | NOT_STARTED |

### 3.2 验证器设计必须区分合理与错误

**正例必须通过**:
- ✅ 人物关系经情节发展改变(有事件触发)
- ✅ 合理的时间跳跃(明确交代)
- ✅ 多视角切换(有叙事标记)
- ✅ 不同时间的两次拍卖(时间线明确)
- ✅ 有伏笔支持的转折

**负例必须拒绝**:
- ❌ 人物关系无解释突变
- ❌ 不可重复资源再次消耗
- ❌ 同一事件被重复完成
- ❌ 主角名称突然改变
- ❌ 无因果的情节跳跃

**避免过度僵化**: 验证器不能扼杀文学创作自由，仅阻断明显的连续性错误。

---

## 第四部分：正式路线图覆盖度评估 (Roadmap Coverage Assessment)

### 4.1 当前路线图 vs. 核心产品要求

**路线图已覆盖的产品要求**:

| 产品要求 | 对应任务 | 阶段 | 状态 |
|---------|---------|------|------|
| 正确上下文获取 | V2-018 Context Compiler | P5 | NOT_STARTED |
| 人物与世界事实持续继承 | V2-021 Delta Extractor + V2-018 | P6+P5 | NOT_STARTED |
| 时间线和事件一致 | V2-023 Q1 Validators | P7 | NOT_STARTED |
| 不可重复资源消耗正确 | V2-023 Q1 Validators | P7 | NOT_STARTED |
| 人物知识与行为合理 | V2-023 Q1 Validators | P7 | NOT_STARTED |
| 重要事件因果承接 | V2-025 Q3 Validators | P7 | NOT_STARTED |
| 新章节冲突与行动合理发展 | V2-017 Contract + V2-025 Q3 | P4+P7 | NOT_STARTED |
| 无关故事跳转识别 | V2-022 Q0 + V2-025 Q3 | P7 | NOT_STARTED |
| 严重错误阻断Canon提交 | V2-026 CommitPermit | P7 | NOT_STARTED |
| 错误不污染后续章节 | V2-026 CommitPermit | P7 | NOT_STARTED |

**结论**: 当前路线图V2-017~026已规划所有核心要求，**无架构缺口**。

### 4.2 路线图未明确覆盖的产品要求

#### 要求A: 输入完整性证明

**产品要求**: "Context Compiler必须证明重要但语义相关性低的旧事实没有因截断而丢失"

**当前任务覆盖**:
- V2-018定义了Context必需集合
- ADR-009要求"溢出与选择解释"

**可能缺口**:
- ❓ 如何定义"必需"? (人物、关系、资源、承诺?)
- ❓ 如何量化"丢失风险"?
- ❓ 如何在Token预算内保证必需集合?

**建议**: ADR-009决策时明确必需集合的语义定义与优先级策略。

#### 要求B: 因果推动与场景转移

**产品要求**: "章节规划至少表达前章关键结果、当前人物目标、行动与冲突、本章重要变化、后续新问题"

**当前任务覆盖**:
- V2-017 Contract Compiler定义章节意图
- V2-025 Q3检查Transition质量

**可能缺口**:
- ❓ Contract如何形式化"前章关键结果"?
- ❓ Q3如何验证"关键结果被处理"?

**建议**: V2-017合约设计时明确Intent结构必须包含前章承接。

#### 要求C: 自动验证与文学评价分离

**产品要求**: "硬性规则由确定性或类型化校验负责，文学可读性作为独立质量层"

**当前任务覆盖**:
- Q0-Q2: 确定性与规则验证
- Q3: 语义合理性(可能需要模型评审)

**可能缺口**:
- ❓ Q3使用模型评审时，如何避免"模型自评当成无条件权威"?
- ❓ 文学吸引力评估在哪个阶段? (V2-028人工评阅?)

**建议**: Q3设计时明确模型评审仅提供证据，CommitPermit做最终裁决。V2-028独立评估文学质量。

### 4.3 路线图任务定义的充分性评估

#### V2-017 Contract Compiler

**当前定义** (从implementation-backlog.yaml):
- Goal: 类型化Contract与Canon/Genre绑定
- Exit Criteria: 双Story Fixture审定、Contract编译、章内候选协议

**充分性评估**:
- ✅ 覆盖章节意图定义
- ⚠️ 未明确规定Contract必须包含"前章关键结果承接"
- ⚠️ 未明确规定"本章目标与后续铺垫"

**建议补强**: 验收条件增加"Contract包含前章承接检查"。

#### V2-018 Context Compiler

**当前定义**:
- Goal: Context必需集合与预算失败正确
- ADR-009: 溢出与选择解释

**充分性评估**:
- ✅ 覆盖必需集合定义
- ✅ 覆盖Token预算处理
- ⚠️ 未明确规定"必需集合"的语义组成(人物/关系/资源/事件?)

**建议补强**: ADR-009决策时明确必需集合的类型与优先级。

#### V2-021 NarrativeDelta Extractor

**当前定义**:
- Goal: 从候选章节提取typed Delta

**充分性评估**:
- ✅ 覆盖Delta提取
- ⚠️ 未明确提取准确率要求(允许漏检比例?)
- ⚠️ 未明确提取错误的后果(修复?人工审核?)

**建议补强**: 验收条件增加"关键Delta类型(关系、资源)准确率阈值"。

#### V2-022 Q0 Validators

**当前定义**:
- Goal: 确定性验证器

**充分性评估**:
- ✅ 覆盖主角名称、篇幅、格式
- ✅ **已吸取Phase 3教训**: 必须验证NAME而非仅计数

**建议补强**: 验收条件明确"主角NAME一致性检查，拒绝任何NAME变化"。

#### V2-023 Q1 Validators

**当前定义**:
- Goal: Canon一致性验证器

**充分性评估**:
- ✅ 覆盖关系、资源、时间线、事件去重
- ⚠️ 未明确"关系变化需解释"的判定标准(Delta中有事件触发?)
- ⚠️ 未明确资源追踪的粒度(所有资源?仅关键资源?)

**建议补强**: 验收条件增加"关系变化必须有Delta.CHANGE_RELATIONSHIP且前提事件存在"。

#### V2-025 Q3 Validators

**当前定义**:
- Goal: Transition质量验证器

**充分性评估**:
- ✅ 覆盖因果承接、场景转移
- ⚠️ 未明确"前章关键结果"如何识别(Contract中标记?Delta中推断?)
- ⚠️ 未明确语义判断的实现方式(规则?模型评审?)

**建议补强**: 验收条件增加"前章Promise/Delta与本章Contract承接检查"。

#### V2-026 CommitPermit Integration

**当前定义**:
- Goal: 聚合验证结果与Permit决策
- ADR-011: 必跑检查集与授权

**充分性评估**:
- ✅ 覆盖验证聚合
- ✅ 覆盖ACCEPT/REJECT决策
- ⚠️ 未明确REPAIR路径(V2-030~032)的触发条件

**建议补强**: ADR-011明确各验证器失败时的决策规则(Q0 FAIL→REJECT, Q1 FAIL→REPAIR?)。

### 4.4 总体覆盖度结论

**核心生产闭环**: V2-017~026已规划，**架构完整**。

**可能补强项**:
1. ADR-009: 明确Context必需集合的语义定义
2. V2-017验收: 增加"Contract包含前章承接"
3. V2-021验收: 增加Delta提取准确率要求
4. V2-023验收: 增加关系变化解释检查
5. V2-025验收: 增加前章承接检查
6. ADR-011: 明确验证失败的决策规则

**无需新增任务**: 当前路线图已覆盖所有核心产品要求。

---

## 第五部分：最小必要架构补强 (Minimal Necessary Architecture Enhancement)

### 5.1 当前架构无需推倒重建

**已有架构优势**:
- ✅ Domain/Canon/Genre三层分离清晰
- ✅ NarrativeDelta作为统一变化语言
- ✅ Immutable Canon with transaction commits
- ✅ Genre extension机制支持题材规则

**无需改动**:
- ✅ 保留现有Domain模型(Entity, Relationship, Knowledge, Events)
- ✅ 保留Canon Repository与CommitService
- ✅ 保留GenrePack Loader
- ✅ 不建立第二套Canon写路径
- ✅ 不推倒P0-P3已验证成果

### 5.2 补强建议仅限验收条件明确化

**建议补强**均为**合约澄清**而非**架构变更**:

1. **ADR-009 (V2-018前)**: 明确Context必需集合语义
   - 定义: EntityState, RelationshipState, ResourceState, PromiseState
   - 优先级: 主角>核心关系>关键资源>未完成承诺>其他
   - 溢出策略: 必需集合优先，其他按语义相关性排序

2. **V2-017验收补充**: Contract结构明确化
   - Contract必须包含: `previous_chapter_key_outcomes`, `current_goals`, `conflicts`, `new_promises`
   - 验收测试: 前章有Promise，Contract必须包含处理意图

3. **V2-021验收补充**: Delta提取准确率
   - 关键类型(ADD_CHARACTER, CHANGE_RELATIONSHIP, CONSUME_RESOURCE): ≥95%召回率
   - 允许漏检次要描述性事实
   - 提取错误的Delta在Q1验证时被拒绝

4. **V2-022验收补充**: 主角NAME验证
   - 检查: 候选章节中的主角NAME必须与Canon中SeriesProtagonist.name完全匹配
   - 拒绝: 任何NAME变化(包括同音异字、简称/全称)
   - 回归测试: 使用Novel B Ch11-15作为负例(错误报告不同主角的场景)

5. **V2-023验收补充**: 关系变化解释检查
   - 检查: Delta.CHANGE_RELATIONSHIP必须有前置事件(Delta.EVENT_OCCURS或Promise.FULFILLED)
   - 拒绝: 关系类型变化无Delta解释
   - 回归测试: Novel B 道侣→师妹作为负例

6. **V2-025验收补充**: 前章承接检查
   - 检查: 前章Promise/Delta中的关键事项，Contract或候选正文必须处理
   - 拒绝: 前章重要结果被忽略
   - 实现方式: 规则检查(前章有CONSUME_RESOURCE，本章必须反映资源减少)

7. **ADR-011 (V2-026前)**: 验证失败决策规则
   - Q0 FAIL → REJECT (确定性错误不修复)
   - Q1 FAIL → REPAIR if fixable, else REJECT
   - Q2 FAIL → REPAIR (Genre规则可能过严)
   - Q3 FAIL → WARN (语义判断可能误报)
   - All PASS → ACCEPT

### 5.3 无需架构补强

**不需要**:
- ❌ 新增模块或子系统
- ❌ 修改Domain/Canon/Genre核心接口
- ❌ 引入新的持久化层
- ❌ 建立实时监控/报警系统(P7后再考虑)

---

## 第六部分：实施顺序与依赖 (Implementation Order & Dependencies)

### 6.1 Critical Path (P4-P7)

```
P4: V2-017 Contract Compiler
    ↓ (需要Contract定义)
P5: V2-018 Context Compiler → V2-019 Model Gateway
    ↓ (需要Context + Gateway)
P6: V2-020 Single Chapter Workflow → V2-021 Delta Extractor
    ↓ (需要Workflow + Delta)
P7: V2-022 Q0 → V2-023 Q1 → V2-024 Q2 → V2-025 Q3 → V2-026 CommitPermit
    ↓ (需要完整验证栈)
P7: V2-027 Retry & Checkpoint (并行实施)
```

### 6.2 阶段性验收里程碑

**M4 (P7完成)**: 单章完整闭环
- 输入: SeriesVision + Canon Snapshot
- 输出: 新章节Commit + Receipt
- 验证: Q0-Q3 PASS → CommitPermit ACCEPT

**M5 (P7完成)**: 三章连续生成
- 验证: 第二章Context包含第一章Delta
- 验证: 第三章Context包含第一、二章Delta
- 验证: 关系/资源状态累积正确

**M6 (P8完成)**: 双Genre十章认证
- 都市题材: 10章连续生成，财务/人物/事件一致
- 玄幻题材: 10章连续生成，修炼/资源/时间线一致
- 真人阅读评估(独立于自动验证)

**M7 (P9完成)**: 双Genre三十章认证
- 故事弧线、疲劳度、durable recovery

### 6.3 实际开发顺序

**Phase 1 (P4-P5)**: 规划与上下文
1. V2-017 Contract Compiler (2-3周)
   - 设计Contract Schema
   - 实现Contract与Canon/Genre绑定
   - Story Fixture审定
2. V2-018 Context Compiler (2-3周)
   - ADR-009决策: 必需集合定义
   - 实现Canon→Context转换
   - 溢出处理与选择解释
3. V2-019 Model Gateway (1-2周)
   - ADR-010决策: Provider抽象
   - 实现Provider接口与预算管理
   - UNKNOWN处理

**Phase 2 (P6)**: 编排与提取
4. V2-020 Single Chapter Workflow (2周)
   - 编排Contract→Context→Writer→Delta→Validator
   - Draft/Accepted状态管理
5. V2-021 Delta Extractor (3-4周)
   - 实现正文→Delta提取(可能需要模型辅助)
   - Delta验证与前置条件检查
6. V2-027 Retry & Checkpoint (1周)
   - 失败重试策略
   - 检查点恢复

**Phase 3 (P7)**: 验证与集成
7. V2-022 Q0 Validators (1周)
   - 主角NAME验证(Novel B Ch11-15回归测试)
   - 篇幅、格式验证
8. V2-023 Q1 Validators (2-3周)
   - 关系变化检查(Novel B 道侣→师妹回归测试)
   - 资源消耗检查(Novel B 筑基丹三次消耗回归测试)
   - 事件去重检查(Novel B 重复拍卖回归测试)
   - 时间线检查(Novel A 财务缺口回归测试)
9. V2-024 Q2 Validators (1-2周)
   - Genre规则验证(progression, business)
10. V2-025 Q3 Validators (2-3周)
    - 前章承接检查
    - 因果推动评估
11. V2-026 CommitPermit Integration (1周)
    - ADR-011决策: 验证失败决策规则
    - Q0-Q3聚合与Permit决策

**总计**: 约18-26周 (4.5-6.5个月)

---

## 第七部分:新小说端到端认证标准 (End-to-End Certification Criteria for New Novels)

### 7.1 M4: 单章闭环认证 (V2-020~026完成后)

**测试输入**:
- SeriesVision: 新都市题材
- GenrePack: business-rules-v1
- Protagonist: 张伟(male, 28岁, 互联网从业者)

**生成Ch1**:
- ✅ Contract生成成功(包含intent, conflicts)
- ✅ Context包含SeriesVision + GenrePack rules
- ✅ Writer生成候选正文
- ✅ Delta提取成功(ADD_CHARACTER张伟, ADD_LOCATION, etc.)
- ✅ Q0 PASS: 主角NAME="张伟", 篇幅≥2000字
- ✅ Q1 PASS: 无资源冲突(首章无前置状态)
- ✅ Q2 PASS: 符合都市题材规则
- ✅ Q3 PASS: 符合开篇转折要求
- ✅ CommitPermit ACCEPT
- ✅ CanonCommit成功, Receipt生成

**验收标准**: 单章流程无Manual intervention，所有组件正常协作。

### 7.2 M5: 三章连续认证 (V2-020~026完成后)

**生成Ch2**:
- ✅ Context包含Ch1 Delta(张伟状态、已发生事件)
- ✅ Contract包含Ch1关键结果承接
- ✅ Delta提取成功(CHANGE_LOCATION, ADD_RELATIONSHIP, etc.)
- ✅ Q1 PASS: 资源状态与Ch1一致
- ✅ Q3 PASS: 承接Ch1结局
- ✅ CommitPermit ACCEPT

**生成Ch3**:
- ✅ Context包含Ch1+Ch2 Delta
- ✅ Contract包含Ch2关键结果承接
- ✅ Q1 PASS: 关系状态累积正确(Ch1建立的关系在Ch2/Ch3可见)
- ✅ Q3 PASS: 承接Ch2结局

**验收标准**: 三章连续生成，状态累积无断裂。

### 7.3 M6: 双Genre十章认证 (P8完成)

**都市题材**:
- ✅ 10章连续生成
- ✅ 财务状态累积正确(收入-支出=余额)
- ✅ 人物关系演进合理(无无解释突变)
- ✅ 商业事件逻辑自洽(合同、投资、竞争)
- ✅ 无重复事件
- ✅ 真人阅读: 可读性评估(独立于自动验证)

**玄幻题材**:
- ✅ 10章连续生成
- ✅ 修炼境界演进合法(符合progression rules)
- ✅ 资源消耗正确(灵石、丹药不可重复消耗)
- ✅ 时间线一致(修炼时长、事件顺序)
- ✅ 无重复战斗/拍卖/洞府探索
- ✅ 真人阅读: 可读性评估

**验收标准**: 两个Genre各生成10章，无核心连续性错误(主角身份、关系突变、资源重复、事件重复)。允许次要描述性不一致。

### 7.4 M7: 三十章认证 (P9完成)

**目标**:
- ✅ 双Genre各30章
- ✅ 故事弧线完整(起-承-转-合)
- ✅ 角色成长可追溯
- ✅ 长期状态追踪正确(30章后的财务/修炼状态与历史一致)
- ✅ Durable recovery: 中断后恢复生成，状态无损

**验收标准**: 30章连续生成，工程可靠性与阅读体验独立评估。

### 7.5 阶段性停止条件

**P7完成后，如果M4/M5失败**:
- 🛑 停止P8认证
- 🔍 回溯P4-P7实施，修复根本问题
- ⚠️ 不通过增加Prompt调优或模型评审绕过确定性故障

**P8完成后，如果M6失败**:
- 🛑 停止P9认证
- 🔍 分析10章失败原因(Context溢出? Delta漏检? 验证器误报?)
- 📊 记录工程/成本/阅读三项独立结论
- 🤔 Owner决策: 继续投入 vs. 调整目标

---

## 第八部分:回归测试样本设计 (Regression Test Design from Historical Failures)

### 8.1 负例样本 (必须被拒绝)

**RT-001: 主角NAME突变**
- 输入: Canon有Protagonist.name="王林"
- 候选: 正文中出现"林轩开始修炼"
- 期望: Q0 REJECT, 理由"主角NAME不一致"

**RT-002: 关系无解释突变**
- 输入: Canon有Relationship(王林, 柳梦, type=ROMANTIC_PARTNER)
- 候选: 正文中"师兄，我先回去了"(师兄/师妹称呼)
- Delta: 无CHANGE_RELATIONSHIP操作
- 期望: Q1 REJECT, 理由"关系类型变化缺Delta"

**RT-003: 资源重复消耗**
- 输入: Canon有Delta.CONSUME_RESOURCE(item="筑基丹", consumed_at=Ch5)
- 候选: 正文中"王林取出筑基丹服下"
- Delta: CONSUME_RESOURCE(item="筑基丹")
- 期望: Q1 REJECT, 理由"筑基丹已在Ch5消耗"

**RT-004: 事件重复发生**
- 输入: Canon有EventOccurrence(type="天宝阁拍卖", occurred_at=Ch11)
- 候选: 正文中"王林来到天宝阁参加拍卖"
- Delta: EVENT_OCCURS(type="天宝阁拍卖")
- 期望: Q1 REJECT, 理由"天宝阁拍卖已在Ch11发生"(除非明确是不同时间的拍卖)

**RT-005: 财务状态断裂**
- 输入: Canon有ResourceState(type="银两", amount=380万, as_of=Ch10)
- 候选: Ch15正文中"账户余额110万"
- Delta: 无CONSUME_RESOURCE或TRANSFER解释中间变化
- 期望: Q1 REJECT, 理由"资源状态缺中间Delta"

**RT-006: 前章承诺被忽略**
- 输入: Canon有Promise(description="张明会见永辉高管谈合作", due_chapter=Ch15)
- 候选: Ch15正文中完全无相关内容
- Delta: 无Promise.FULFILLED或CANCELLED
- 期望: Q3 REJECT, 理由"前章Promise未处理"

### 8.2 正例样本 (必须通过)

**RT-101: 合理关系演进**
- 输入: Canon有Relationship(王林, 柳梦, type=ROMANTIC_PARTNER)
- 候选: 正文中"两人因理念不合分道扬镳"
- Delta: CHANGE_RELATIONSHIP(from=ROMANTIC_PARTNER, to=NEUTRAL, reason=EVENT_OCCURS("理念冲突"))
- 期望: Q1 PASS

**RT-102: 明确时间跳跃**
- 输入: Canon最后时间点=Day 100
- 候选: 正文中"三个月后..."
- Delta: ADVANCE_TIME(days=90)
- 期望: Q1 PASS

**RT-103: 多视角切换**
- 输入: Canon当前视角=王林
- 候选: 章节标题"第15章：柳梦的抉择"，正文切换到柳梦视角
- Delta: SWITCH_PERSPECTIVE(to="柳梦")
- 期望: Q0 PASS (允许多视角)

**RT-104: 不同时间的相似事件**
- 输入: Canon有EventOccurrence(type="拍卖会", location="天宝阁", occurred_at=Ch11, date=Day 50)
- 候选: 正文中"两个月后，天宝阁又举办了一场拍卖"
- Delta: EVENT_OCCURS(type="拍卖会", location="天宝阁", date=Day 110)
- 期望: Q1 PASS (不同时间点的重复事件类型合法)

**RT-105: 有伏笔支持的转折**
- 输入: Canon有Promise(description="神秘组织追杀王林", mentioned_at=Ch5)
- 候选: Ch10正文中"那个神秘组织终于现身"
- Delta: Promise.FULFILLED + EVENT_OCCURS("神秘组织现身")
- 期望: Q3 PASS

### 8.3 回归测试套件结构

```
tests/regression/
  narrative_continuity/
    test_protagonist_identity.py (RT-001, RT-101)
    test_relationship_consistency.py (RT-002, RT-101)
    test_resource_tracking.py (RT-003, RT-005)
    test_event_deduplication.py (RT-004, RT-104)
    test_promise_fulfillment.py (RT-006, RT-105)
    test_temporal_consistency.py (RT-102)
    test_perspective_switching.py (RT-103)
```

---

## 第九部分:当前可执行动作与授权边界 (Current Executable Actions & Authorization Boundary)

### 9.1 当前已授权动作 (Immediate Actions Authorized)

**只读分析与规划**:
- ✅ 读取plan/machine/* SSOT
- ✅ 读取现有Domain/Canon/Genre代码
- ✅ 分析P4-P7任务定义
- ✅ 审查ADR-009~011需求
- ✅ 设计回归测试样本

**文档交付**:
- ✅ 本差距分析文档
- ✅ 回归测试样本设计文档(如需独立文档)

### 9.2 当前未授权动作 (Requires Owner Authorization)

**代码实施**:
- ❌ 开始V2-017~026任何任务的IMPLEMENT阶段
- ❌ 修改src/anovel/任何生产代码
- ❌ 创建新模块(context/, gateway/, workflow/, validators/)
- ❌ 修改现有Domain/Canon/Genre接口

**测试实施**:
- ❌ 创建回归测试文件(tests/regression/)
- ❌ 修改验收测试(tests/acceptance/)

**ADR决策**:
- ❌ 起草ADR-009/010/011决策文档
- ❌ 将任何ADR标记为ACCEPTED

**任务状态变更**:
- ❌ 将V2-017~026任何任务标记为IN_PROGRESS或CLOSED
- ❌ 修改plan/machine/implementation-backlog.yaml
- ❌ 修改plan/machine/phase-gates.yaml

**付费API调用**:
- ❌ 调用任何Provider (Claude, GPT, etc.)
- ❌ 运行需要真实Model Gateway的测试

**部署与发布**:
- ❌ 合并任何PR到main
- ❌ 创建release tag
- ❌ 修改CI配置

### 9.3 后续授权请求路径

**如需开始P4-P7实施**:
1. Owner审阅本差距分析
2. Owner确认V2-017~026范围与优先级
3. Owner批准ADR-009~011决策路径
4. Owner授权V2-017 PREPARE阶段(调查未决项)
5. 后续任务逐个授权，按P4→P5→P6→P7顺序

**如需修改任务定义**:
1. 提出具体合约补强建议(如本文档第五部分)
2. Owner审阅并批准
3. 修改plan/machine/implementation-backlog.yaml
4. 运行`python3 plan/scripts/validate_plan.py --write-views`
5. 提交PR并等待Owner merge

---

## 第十部分:核心结论与Owner决策点 (Core Conclusions & Owner Decision Points)

### 10.1 核心结论

#### 结论1: 三本小说失败的根本原因

**三本30章实验小说的叙事可靠性故障根源于生产流水线完全缺失，而非已实现模块的设计缺陷。**

- ✅ P0-P3基础能力已实现并验证(Domain, Canon, Genre)
- ❌ P4-P7生产流水线完全未实现(Contract, Context, Workflow, Validators)
- ❌ 实验脚本绕过正式架构，直接调用API，无状态累积，无验证

#### 结论2: 正式路线图的充分性

**按现有正式路线图完整实施后，ANovelOS能够有效控制新小说中主角替换、状态断裂、重复事件及缺乏因果的情节跳转。**

核心证据:
- V2-018 Context Compiler → 解决"重要旧事实丢失"
- V2-021 Delta Extractor → 解决"状态无累积"
- V2-022 Q0 Validators → 解决"主角NAME替换"
- V2-023 Q1 Validators → 解决"关系突变、资源重复、事件重复、财务断裂"
- V2-025 Q3 Validators → 解决"因果断裂、前章结果被忽略"
- V2-026 CommitPermit → 解决"错误章节污染后续"

**无架构缺口，无需新增模块或子系统。**

#### 结论3: 任务定义的改进空间

**当前路线图任务定义基本充分，仅需验收条件明确化。**

建议补强(非架构变更):
1. ADR-009: 明确Context必需集合语义
2. V2-017验收: Contract包含前章承接
3. V2-021验收: Delta提取准确率要求
4. V2-022验收: 主角NAME一致性检查
5. V2-023验收: 关系变化解释检查
6. V2-025验收: 前章承接检查
7. ADR-011: 验证失败决策规则

### 10.2 Owner决策点

#### 决策点A: 是否继续旧三本小说的修补?

**建议: 停止修补，冻结作为回归测试输入。**

理由:
- 旧小说是独立脚本产物，修补无法验证正式系统
- 修补成本高(需人工重写矛盾章节)
- 修补后的小说无法证明ANovelOS自动生成能力

**替代方案**: 将旧小说故障提炼为回归测试样本(RT-001~006, RT-101~105)。

#### 决策点B: P4-P7实施优先级?

**建议: 按Critical Path顺序，P4→P5→P6→P7。**

理由:
- V2-017 Contract是后续所有组件的基础(定义章节意图)
- V2-018 Context + V2-019 Gateway是Writer的必需输入
- V2-020 Workflow编排所有组件
- V2-021 Delta提取是状态累积的核心
- V2-022~026 Validators是质量保障

**时间估算**: 18-26周(4.5-6.5个月)

#### 决策点C: M4/M5/M6/M7认证标准是否接受?

**建议: 接受分阶段认证策略。**

理由:
- M4(单章闭环)验证组件集成
- M5(三章连续)验证状态累积
- M6(十章)验证实际连续性
- M7(三十章)验证长期可靠性

**重要**: 工程可靠性、阅读体验、市场吸引力三项独立评估，不互相冒充。

#### 决策点D: 回归测试样本是否足够?

**建议: 接受RT-001~006(负例)+ RT-101~105(正例)作为最小回归套件。**

后续补充:
- P7实施时，根据实际验证器设计增加测试
- P8认证时，根据实际故障补充新样本

#### 决策点E: 是否授权开始P4实施?

**建议: Owner审阅本文档后，授权V2-017 PREPARE阶段。**

PREPARE阶段产物:
- Contract Schema设计
- Story Fixture审定方案
- ADR-008补充说明(如需)
- V2-017执行包(execution-packet.yaml)

**后续IMPLEMENT阶段需独立授权。**

---

## 附录A:三本小说故障证据索引 (Appendix A: Failure Evidence Index)

### Novel A (Urban: 资本博弈：创业者的抉择)

**故障**: 340万资金缺口
- **证据文件**: `/Users/angyang/anovel-pov-001/phase4_canonical/REPAIR_EXECUTION_RESULTS_CORRECTED.md` lines 14-85
- **缺失能力**: Context Compiler(V2-018), Delta Extractor(V2-021), Q1 Validators(V2-023)
- **回归测试**: RT-005 (财务状态断裂)

### Novel B (Fantasy: 逆天修仙：资源与抉择)

**故障1**: 柳梦关系 道侣→师妹
- **证据文件**: `/Users/angyang/anovel-pov-001/phase4_canonical/REPAIR_EXECUTION_RESULTS_CORRECTED.md` lines 130-147
- **缺失能力**: Delta Extractor(V2-021), Q1 Validators(V2-023)
- **回归测试**: RT-002 (关系无解释突变)

**故障2**: 筑基丹三次消耗
- **证据文件**: `/Users/angyang/anovel-pov-001/phase4_canonical/REPAIR_EXECUTION_RESULTS_CORRECTED.md` lines 149-156
- **缺失能力**: Q1 Validators(V2-023)
- **回归测试**: RT-003 (资源重复消耗)

**故障3**: 重复拍卖会
- **证据文件**: `/Users/angyang/anovel-pov-001/phase4_canonical/REPAIR_EXECUTION_RESULTS_CORRECTED.md` lines 158-171
- **缺失能力**: Q1 Validators(V2-023)
- **回归测试**: RT-004 (事件重复发生)

**故障4**: Agent错误报告主角替换
- **证据文件**: `/Users/angyang/anovel-pov-001/timeline_analysis_novel_b.md` (agent report, INCORRECT)
- **实际验证**: Phase 3 Ch11-15均为王林
- **缺失能力**: Q0 Validators(V2-022) - 验证仅计数mentions，未验证NAME
- **回归测试**: RT-001 (主角NAME突变)

### Novel C (Reference: 二十四岁的选择题)

**状态**: READY - 无核心连续性故障
- **证据文件**: `/Users/angyang/anovel-pov-001/phase4_canonical/REPAIR_EXECUTION_RESULTS_CORRECTED.md` lines 173-228
- **用途**: 作为正例参考，证明良好Prompt构造可避免部分故障(但不可扩展到长期连续)

---

## 附录B:关键文件路径索引 (Appendix B: Key File Path Index)

### 机器权威文件 (Machine Authority)
- `plan/machine/implementation-backlog.yaml` - 61任务定义
- `plan/machine/phase-gates.yaml` - P0-P14阶段状态
- `plan/machine/decision-register.yaml` - ADR状态
- `plan/machine/test-catalog.yaml` - 验收测试目录

### 规范文档 (Normative Specs)
- `plan/05_PRODUCTION_CONTEXT_QUALITY_REPAIR.md` - V2-017~027规范
- `plan/06_CERTIFICATION_AND_PRODUCT_EVALUATION.md` - V2-033~040规范
- `plan/AI_EXECUTION_PROTOCOL.md` - AI执行协议

### 已实现代码 (Implemented Code)
- `src/anovel/domain/` - P1 Domain模型
- `src/anovel/canon/` - P2 Canon持久化
- `src/anovel/genre/` - P3 Genre扩展

### 故障证据 (Failure Evidence)
- `/Users/angyang/anovel-pov-001/phase4_canonical/REPAIR_EXECUTION_RESULTS_CORRECTED.md` - 三本小说修复报告
- `/Users/angyang/anovel-pov-001/timeline_analysis_novel_b.md` - Novel B时间线分析(含错误)

### 验收测试 (Acceptance Tests)
- `tests/acceptance/` - 现有验收测试(V2-001~013)
- `tests/regression/` - 待建立回归测试

---

## 文档版本与审核记录 (Document Version & Review Record)

**Version**: 1.0  
**Date**: 2026-10-30  
**Author**: Claude Opus 5.5  
**Reviewed**: Pending Owner Review

**Changes**:
- Initial creation based on Owner direction "从测试小说修补转向正式系统级长篇叙事可靠性建设"

**Next Actions**:
1. Owner审阅本差距分析
2. Owner决策五个决策点(A-E)
3. 如批准P4实施，创建V2-017 execution packet
4. 后续按P4→P5→P6→P7顺序推进

---

**END OF ANALYSIS**
