# ADR-009: Context Compilation and Budget Policy

**Status:** ACCEPTED  
**Date:** 2026-11-03  
**Approved:** 2026-11-03  
**Scope:** V2-018 Context Compiler  
**Related Tasks:** V2-018, V2-019, V2-020  
**Owner:** context-maintainer  
**Supersedes:** None  

---

## 问题与约束

V2-018 Context Compiler 将 ChapterContract、Canon snapshot、GenrePack、角色知识、前章实际结尾和可选检索内容组装成 ContextArtifact，供 Writer 使用。

需要决定：

1. **Mandatory vs Optional 分类**：哪些上下文项必须完整保留，哪些可以预算裁剪？
2. **预算溢出处理**：Mandatory 项超出 token 预算时如何处理？
3. **知识隔离边界**：如何保证角色知识、读者知识、审查者资料、未来剧情严格隔离？
4. **选择可解释性**：如何记录每项内容的纳入/排除原因？
5. **低相关性必需项**：语义检索相关度低但契约要求的内容如何处理？

约束：
- 不能静默截断关键事实（V2-018 acceptance criteria）
- 审查者资料不能通过缓存进入 Writer（scope isolation）
- 前章实际末段不能被可选检索挤出（continuity priority）
- 每项 inclusion 必须可解释（explainability requirement）

---

## 决定

### 1. Mandatory Context 定义

**Decision:** 以下上下文项分类为 Mandatory，**绝不**因 token 预算不足而裁剪：

- **ContinuityConstraint**: 前章实际结尾状态、previous_end_state（**第一章明确无前章**）
- **ChapterContract 全部约束**: required_transitions, prohibited_transitions, protected_facts, knowledge_boundaries
- **角色知识边界**: 当前章节每个登场角色的 known_facts（从 Canon 投影获得）
- **GenrePack 硬策略**: 当前 GenrePackBinding 引用的硬约束规则
- **Canon 必需事实**: Contract 中 fact_path 引用的所有 Canon 事实

**Rationale:**
- 这些项直接约束生成正确性，缺失会导致连续性断裂、知识泄漏或违反契约
- 语义相关度低不代表可以省略（例如前章末尾平淡但必须接续）
- 前章真实结尾和连续性约束优先保留（Owner requirement）

### 2. Optional Context 定义

**Decision:** 以下上下文项分类为 Optional，可根据 token 预算自适应选择：

- **检索摘要**: 从 Canon 或角色历史检索的相关场景摘要
- **背景扩展**: 世界观、次要角色背景等非当前章节关键的描述性内容
- **风格参考**: GenrePack 中的可选写作风格建议

**Rationale:**
- 这些项增强质量但不影响正确性
- 预算不足时优先保证 Mandatory 完整性

### 3. Mandatory Overflow 策略

**Decision:** **FAIL_FAST** — Mandatory 项总 token 数超出可用预算时，编译返回 `ContextCompilationError`，明确列出超出量和建议。

**可用预算计算:** `available_budget = total_budget - output_reserve - system_overhead`

**拒绝的替代方案:**
- ❌ **Silent Truncation**: 违反 acceptance criteria "预算溢出必需项时明确阻断"
- ❌ **Auto Budget Increase**: V2-018 不负责预算协商，由调用方（V2-020 Workflow）决定
- ❌ **Mandatory Summarization**: 总结可能丢失关键细节，不适用于契约约束
- ❌ **Guess Success**: 如果无法可靠证明必需内容处于预算以内，明确报错（Owner requirement）

**Implementation:**
```python
@dataclass(frozen=True)
class ContextCompilationError:
    error_type: Literal["mandatory_overflow"]
    mandatory_tokens: int
    available_budget: int  # total_budget - output_reserve
    overflow_amount: int
    suggested_budget: int
    affected_items: list[str]  # Which mandatory items present
```

### 4. Optional Budget Allocation

**Decision:** **Adaptive Selection** — 根据剩余预算（total_budget - mandatory_tokens - output_reserve），动态按以下因素决定优先级：

- **因果依赖**: 与当前章节必需转移直接相关的背景
- **章节需要**: Contract 引用但非强制的支持性信息
- **时间相关性**: 前章/近期事件 > 远期历史
- **信息重要性**: 角色核心动机 > 次要细节

不使用固定优先级排序（如"前章 > 角色 > 世界观"），而是根据实际 ChapterContract 内容动态评估。

**Rationale:**
- 固定比例分配（如 70/30）在 Mandatory 接近预算上限时浪费空间
- 固定优先级无法适应不同章节的实际需求差异
- 自适应分配最大化可用预算利用率（Owner requirement）

### 5. 知识隔离保证

**Decision:** **Strict Scope and Visibility** — 每个 ContextItem 标记：

```python
@dataclass(frozen=True)
class ContextItem:
    item_id: str
    content: str | dict
    source_type: Literal["canon", "contract", "genre_pack", "character_knowledge", "retrieval"]
    source_hash: str  # 来源内容哈希
    scope: str  # project_id
    visibility: Literal["writer", "character", "reader", "reviewer"]
    mandatory: bool
    token_count: int
    inclusion_reason: str  # 可解释性
```

编译时强制规则：
- `visibility == "reviewer"` 的项 **永不** 纳入 ContextArtifact
- `visibility == "reader"` 的项不进入角色知识
- 不同 `scope` 的项不混合
- 未来章节的 Canon 事实（chapter_number > current）排除

**Rationale:**
- 满足 "错项目未来知识无泄漏且每项 inclusion 可解释"
- 满足 "审查者专用事实不会通过缓存进入 Writer"

### 6. 可解释性与可审计性

**Decision:** **Deterministic and Explainable** — ContextArtifact 包含完整编译日志：

```python
@dataclass(frozen=True)
class ContextArtifact:
    artifact_id: str
    chapter_contract_id: str
    canon_parent: str
    genre_pack_hash: str
    created_at: datetime
    
    mandatory_items: list[ContextItem]
    optional_items: list[ContextItem]
    
    compilation_log: CompilationLog
```

```python
@dataclass(frozen=True)
class CompilationLog:
    total_budget: int
    mandatory_tokens: int
    optional_tokens: int
    output_reserve: int  # Reserved tokens for Writer output + system overhead
    excluded_optional_items: list[tuple[str, str]]  # (item_id, exclusion_reason)
    token_counting_method: str  # Model-specific tokenizer (e.g., "cl100k_base", "claude-tokenizer")
```

**Rationale:**
- 满足 "冻结输入在不调用生成模型时可编译 ContextArtifact"（离线可重现）
- 满足 P8 Context Inspector 审计需求（比较两次编译差异）
- **预留 Writer 输出、系统消息及协议开销的 Token 预算**（Owner requirement）
- **Token 计数采用目标模型兼容的 tokenizer**（Owner requirement）

---

## 影响与验证

### Schema/接口影响

新增：
- `src/anovel/context/models.py`: ContextArtifact, ContextItem, ContextCompilationError, CompilationLog
- `src/anovel/context/compiler.py`: ContextCompiler.compile_context()

依赖：
- `src/anovel/contracts/models.py`: ChapterContract (已存在)
- `src/anovel/planning/models.py`: GenrePackBinding (已存在)
- `src/anovel/canon/projection.py`: Canon snapshot 投影 (V2-012)

### 正例

1. **Mandatory 在预算内**: 所有 contract 约束 + 前章结尾 + 角色知识 = 8000 tokens，预算 32000 → 编译成功，剩余预算分配给检索摘要
2. **Mandatory 超预算**: 必需项 35000 tokens，预算 32000 → 返回 ContextCompilationError，建议预算 40000
3. **知识隔离**: 角色 A 不知道秘密 X，KnowledgeBoundary 标记 X.knowers = [B] → ContextArtifact 中 X 标记 visibility="reader"，不进入角色 A 的 character_knowledge 项

### 反例

1. ❌ Mandatory 项因预算不足被静默总结 → 违反 FAIL_FAST 策略
2. ❌ 审查者资料（如 planning rationale）进入 Writer context → 违反知识隔离
3. ❌ 未来章节 Canon 事实泄漏 → 违反 scope 过滤

### AT-V2-018 验证

```python
# tests/contract/test_v2_018.py

def test_mandatory_overflow_fails_explicitly():
    """Mandatory 项超预算时明确失败，不静默截断"""
    
def test_low_relevance_mandatory_included():
    """语义相关度低但 contract 要求的前章结尾必须保留"""
    
def test_reviewer_facts_excluded():
    """审查者专用资料不进入 ContextArtifact"""
    
def test_future_knowledge_leak_prevented():
    """未来章节事实和其他项目数据隔离"""
    
def test_offline_compilation_deterministic():
    """相同冻结输入离线编译结果一致，无 LLM 调用"""
```

---

## 生效与替代

**生效条件:** ADR-009 ACCEPTED 且 G-P4 VERIFIED 后，V2-018 实现可引用此决策。

**替代决定:** 无（V2-018 首次定义 Context 编译策略）

**机器登记更新:**
```yaml
# plan/machine/decision-register.yaml
- decision_id: ADR-009
  title: Context Compilation and Budget Policy
  status: PROPOSED  # Owner 批准后 → ACCEPTED
  first_applies: V2-018
  normative_file: plan/decisions/ADR-009_CONTEXT_COMPILATION_BUDGET_POLICY.md
```

---

## Owner 批准决议

**批准日期:** 2026-11-03

**批准的技术规则:**
- ✅ Mandatory Overflow → FAIL_FAST（不静默裁剪）
- ✅ Optional Budget → ADAPTIVE（动态因果依赖、章节需要、时间相关性、信息重要性）
- ✅ Knowledge Isolation → STRICT（角色、读者、Writer 规划与 Reviewer 专用资料明确隔离）
- ✅ Explainability → 必要来源、版本、纳入原因及预算处理可追踪
- ✅ Determinism → 相同冻结输入和策略可离线重现

**Owner 补充要求已纳入决策:**
1. 前章真实结尾和连续性约束优先保留；第一章明确无前章
2. Optional 优先级由因果依赖、章节需要、时间相关性和信息重要性动态决定
3. Token 计数采用目标模型兼容的 tokenizer（不将 cl100k_base 作为通用默认）
4. 无法可靠证明必需内容在预算内时明确报错
5. 预留 Writer 输出、系统消息及必要协议开销的 Token 预算

**生效:** V2-018 IMPLEMENT 可引用此决策（准入条件：PR #17 合并 + G-P4 VERIFIED）
