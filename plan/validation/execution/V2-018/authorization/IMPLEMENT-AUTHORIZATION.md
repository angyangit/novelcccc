# V2-018 IMPLEMENT Authorization

**Authorization Date:** 2026-11-03  
**Status:** CONDITIONALLY GRANTED  
**Owner:** Project Owner

---

## Authorization Scope

**Authorized Work:** V2-018 Context Compiler Implementation

**Deliverables:**
1. `src/anovel/context/models.py` — ContextArtifact, ContextItem, ContextCompilationError, CompilationLog
2. `src/anovel/context/compiler.py` — ContextCompiler.compile_context()
3. `src/anovel/context/token_counter.py` — TokenCounter abstraction
4. `tests/contract/test_v2_018.py` — AT-V2-018 acceptance tests (5 test classes)

**Not Authorized:**
- Large context management frameworks
- Pre-optimization beyond acceptance criteria
- Additional abstraction layers not required for V2-018
- Code inflation to meet estimated line counts

---

## Implementation Conditions (MUST BE MET BEFORE MERGE)

### 1. PR #17 Merged ✅ or ❌
- Local HEAD fb5627a must be pushed to remote
- GitHub CI must pass (SCHEMA_CONTRACT, UNIT, STATIC, ARCH_FITNESS, etc.)
- Owner merge approval required

### 2. G-P4 Gate VERIFIED ✅ or ❌
- Phase gate validation complete
- Evidence recorded in plan/validation/closure/

### 3. ADR-009 ACCEPTED ✅
- Decision record finalized at plan/decisions/ADR-009_CONTEXT_COMPILATION_BUDGET_POLICY.md
- Registered in plan/machine/decision-register.yaml

---

## Implementation Requirements (from ADR-009 + Owner Decision)

### Mandatory Context Assembly
- ContinuityConstraint (前章实际结尾，第一章明确无前章)
- ChapterContract 全部约束
- 角色知识边界
- GenrePack 硬策略
- Canon 必需事实

### Budget Policy
- **FAIL_FAST** on mandatory overflow
- **Adaptive selection** for optional items (因果依赖、章节需要、时间相关性、信息重要性)
- Reserve tokens for Writer output + system overhead
- Model-specific tokenizer (不将 cl100k_base 作为通用默认)

### Knowledge Isolation
- Reviewer 资料永不进入 ContextArtifact
- 未来章节 Canon 事实排除
- 角色/读者/Writer 规划严格隔离
- Scope 隔离 (project_id)

### Explainability
- 每项 ContextItem 记录 source, source_hash, visibility, mandatory, inclusion_reason
- CompilationLog 记录 budget, token counts, excluded items with reasons
- 离线确定性编译 (无 LLM 调用)

---

## Product Validation (Dual-Fixture)

### 都市商业 Fixture
- 编译第一章 ContextArtifact 成功
- 验证商业谈判相关必需事实保留
- 验证角色商业知识不泄漏未来融资计划

### 东方玄幻 Fixture
- 编译第一章 ContextArtifact 成功
- 验证修炼体系约束保留
- 验证角色修为知识不泄漏未来突破路径

### 共同验证
- Mandatory overflow 明确失败
- 低相关度必要因果事实不丢失
- ContextArtifact 可直接转换为 Writer 输入格式

---

## Development Rhythm

```
PR #17 收尾 (Bundle push + CI pass)
  ↓
G-P4 VERIFIED
  ↓
V2-018 IMPLEMENT (此授权生效)
  ↓
V2-018 测试通过 + 双 Fixture 验证
  ↓
V2-019 Model Gateway (下一任务)
  ↓
V2-020 Chapter Workflow
  ↓
第一章真实小说初稿
```

---

## Implementation Forbidden

- ❌ 无关治理审计
- ❌ Repository Recovery 文档
- ❌ 重复项目审计
- ❌ 大型准备报告
- ❌ 预设必须达到 790 行代码
- ❌ 为满足估算行数而增加抽象

---

## Next Delivery Expectation

**Only Report:**
1. V2-018 实际代码 (files created, lines added)
2. AT-V2-018 测试结果 (5 tests pass/fail)
3. 双 Fixture ContextArtifact 示例 (都市商业 + 东方玄幻)
4. 距离 Writer 真实生成还缺什么 (V2-019, V2-020, V2-021 gap analysis)

**Do Not Report:**
- 治理成熟度评估
- 架构审计报告
- 历史整理文档
- 大型验收报告

---

## Authorization Validity

**Valid When:** All 3 conditions met (PR #17 merged + G-P4 VERIFIED + ADR-009 ACCEPTED)

**Current Status:** 
- PR #17: ❌ Pending bundle transfer + remote push
- G-P4: ❌ Pending V2-017 remote verification
- ADR-009: ✅ ACCEPTED 2026-11-03

**Implementation Start:** Authorized immediately upon condition fulfillment, no re-approval needed.
