# ADR-004 — 有限变化语言与 Reducer 前置条件

**状态**: ACCEPTED

**关联任务**: V2-008, V2-010, V2-017

**责任角色**: domain-maintainer

**决策权威**: ARCHITECTURE DECISION

**Machine ADR Status**: ACCEPTED

**日期**: 2026-10-17

**首次适用**: Plan v1.3.1

---

## 问题与依据

### 触发场景

V2-008 (NarrativeDelta Implementation) 需要实现 plan/03 §2 定义的变化语言，但当前领域模型缺少关键语义基础：

1. **NarrativeDelta 身份未定义**：
   - NarrativeDelta 是提议（proposal）还是已提交事实（committed fact）？
   - 与 Canon 提交的关系未明确
   - 与 CanonCommitService 的集成边界未定

2. **操作语义未冻结**：
   - SET_FACT, END_FACT, UNDO_FACT 的精确语义未定
   - 必需字段（subject, scope, path, value, precondition, evidence）未明确
   - 未注册操作和错误类型载荷的拒绝规则未建立

3. **前置条件代数缺失**：
   - ExpectValue, ExpectAbsent, ExpectPresent, ExpectUnknown 语义未定
   - 是否允许 ExpectAny 或隐式覆写未决定
   - 前置条件失败的拒绝机制未实现

4. **UNKNOWN vs NO_CHANGE vs UNDO_FACT 未区分**：
   - 三种语义不同的状态混淆
   - null 不能同时代表未知/删除/无变化
   - 撤销操作的表达方式未定

5. **Reducer 契约未明确**：
   - 纯函数、确定性、版本化要求未强制
   - Fail-closed 语义未定义
   - Provider-independent 要求未落地

### 现有规范

- **plan/03 §2**：要求有限操作、明确前值条件、类型匹配、禁止未注册扩展
- **plan/03 §3**：Canon 唯一提交协议，幂等性要求
- **plan/03 §6**：Artifact 身份、hash 与血缘
- **ADR-002**: BASE/DERIVED/CACHE 分类，为 NarrativeDelta 提供模式参考
- **ADR-003**: Event/Promise 语义，确立 immutability 和 authority 模式
- **AT-V2-008**: 验收场景明确要求"SET_FACT 缺必要路径值证据被拒绝"和"未注册操作不能成为提交提议"

### 需要决定的边界

1. NarrativeDelta 的身份、生命周期、与 Canon 的关系
2. 有限操作注册表（REGISTERED, VERSIONED, TYPED）
3. 前置条件代数（四种 Expect 类型，禁止 ExpectAny）
4. SET_FACT/END_FACT/UNDO_FACT 精确契约
5. UNKNOWN vs NO_CHANGE vs UNDO_FACT 语义区分
6. Reducer 纯函数契约（pure, deterministic, versioned, fail-closed）
7. Type safety, scope safety, evidence requirements
8. Authority boundary（NarrativeDelta 是 proposal，不是 commit authority）

---

## 决定

### 核心原则

1. **NarrativeDelta 是提议，不是 Canon 状态**
2. **有限操作注册表**：REGISTERED, VERSIONED, TYPED，禁止自由字典
3. **前置条件代数**：ExpectValue/ExpectAbsent/ExpectPresent/ExpectUnknown，禁止 ExpectAny
4. **明确语义区分**：UNKNOWN ≠ NO_CHANGE ≠ UNDO_FACT
5. **Reducer 纯函数契约**：pure, deterministic, versioned, fail-closed, provider-independent
6. **Fail-closed 默认**：未知操作、类型不匹配、前置条件失败 → 拒绝提交
7. **Authority 边界**：NarrativeDelta 提议权限 ≠ Canon 提交权限

---

## 决策 A：NarrativeDelta 身份与生命周期

### NarrativeDelta 定义

```python
@dataclass(frozen=True)
class NarrativeDelta:
    """
    叙事状态变化提议（proposal），不是已提交 Canon 事实。
    
    NarrativeDelta 表达"希望发生的状态变化"，必须经过验证和授权后
    才能通过 CanonCommitService 提交为 Canon 事实。
    
    BASE fields (all persisted):
        delta_id: 唯一标识符 (UUID v4 format)
        project_id: 项目隔离边界
        operations: 操作列表（有限注册类型）
        source_chapter: 提议来源章节（可选）
        created_at: 提议创建时间
        authority: 提议来源标识
        provenance: 结构化出处元数据
    
    Invariants:
        - delta_id 必须 UUID v4 format
        - operations 中每个操作必须是已注册类型
        - 所有操作的 project_id 必须与 NarrativeDelta.project_id 一致
        - NarrativeDelta immutable（提议后不可修改，重提需新 delta_id）
    
    Authority:
        - NarrativeDelta 表达提议权限，不表达提交权限
        - 只有 CanonCommitService 有权将 Delta 转为 Canon 事实
        - Delta 可被拒绝、修改（新 Delta）或接受
    """
    delta_id: DeltaId  # NewType("DeltaId", str)
    project_id: ProjectId
    operations: list[Operation]
    source_chapter: str | None
    created_at: datetime
    authority: str
    provenance: dict[str, str]
```

### 生命周期

```
PROPOSED → VALIDATED → {ACCEPTED → COMMITTED | REJECTED}
```

- **PROPOSED**: Delta 提议已创建，未验证
- **VALIDATED**: 所有操作通过类型、前置条件、scope 检查
- **ACCEPTED**: 通过 Quality Gate 和 Permit
- **COMMITTED**: 已通过 CanonCommitService 提交为 Canon 事实
- **REJECTED**: 验证失败、Quality 阻断或授权拒绝

**关键语义**：
- NarrativeDelta 是 **proposal**，不是 Canon state
- COMMITTED 状态由 Canon commit receipt 证明，不由 Delta 自身状态表达
- Delta 可以被拒绝，拒绝不影响 Canon
- 同一 Delta 不可重复提交（idempotency 由 CanonCommitService 保证）

---

## 决策 B：有限操作注册表

### 操作注册原则

1. **REGISTERED**: 每种操作必须在全局注册表中定义
2. **VERSIONED**: 操作定义有版本，版本变更需迁移或 Retcon
3. **TYPED**: 操作有明确的 schema，载荷必须通过验证

### P1 注册的三种操作

```python
class OperationType(Enum):
    """
    V2-008 注册的有限操作类型。
    
    未注册操作不可成为提交提议。
    """
    SET_FACT = "SET_FACT"
    END_FACT = "END_FACT"
    UNDO_FACT = "UNDO_FACT"


@dataclass(frozen=True)
class Operation:
    """
    操作基类（抽象）。所有具体操作必须继承此类。
    
    Invariants:
        - operation_type 必须是已注册类型
        - 具体子类必须实现 validate_schema()
    """
    operation_type: OperationType
    operation_version: str  # Semantic version (e.g., "1.0.0")
    
    def validate_schema(self) -> None:
        """子类实现：验证操作载荷是否符合注册 schema"""
        raise NotImplementedError
```

### 拒绝未注册操作

```python
def validate_operation_registration(op: Operation) -> None:
    """
    验证操作是否已注册。
    
    未注册操作 → ValueError
    """
    if op.operation_type not in OperationType:
        raise ValueError(
            f"Operation type {op.operation_type} not registered. "
            f"Cannot include in commit proposal."
        )
```

---

## 决策 C：前置条件代数

### 四种 Expect 类型

```python
@dataclass(frozen=True)
class ExpectValue:
    """
    期望路径当前值等于指定值。
    
    语义：path 必须存在，且 current_value == expected_value
    失败：值不匹配 → 拒绝
    """
    expected_value: Any  # Typed value


@dataclass(frozen=True)
class ExpectAbsent:
    """
    期望路径不存在。
    
    语义：path 必须不存在于 Canon
    失败：路径已存在 → 拒绝
    用途：防止重复创建、冲突检测
    """
    pass  # No payload needed


@dataclass(frozen=True)
class ExpectPresent:
    """
    期望路径存在（不关心具体值）。
    
    语义：path 必须存在于 Canon
    失败：路径不存在 → 拒绝
    用途：更新操作的前置条件
    """
    pass  # No payload needed


@dataclass(frozen=True)
class ExpectUnknown:
    """
    期望路径状态为 UNKNOWN（非 null，非空值）。
    
    语义：path 曾被记录为 UNKNOWN，不是"不存在"或"已知值"
    失败：路径不存在或有确定值 → 拒绝
    用途：解决之前的 UNKNOWN，不允许覆盖已知事实
    """
    pass  # No payload needed


Precondition = ExpectValue | ExpectAbsent | ExpectPresent | ExpectUnknown
```

### 拒绝 ExpectAny 和隐式覆写

**不存在的类型**：
- ~~ExpectAny~~：不允许"无论当前值是什么都覆写"
- ~~ExpectNothing~~：不允许"不检查前置条件"
- ~~ExpectDefault~~：不允许"如果不存在则使用默认值"

**强制前置条件**：
- 所有 SET_FACT 必须包含 precondition
- 不允许省略 precondition（省略 → ValueError）
- 不允许隐式覆写（必须明确 ExpectValue 或其他）

```python
def validate_precondition_required(op: SetFactOperation) -> None:
    """
    SET_FACT 必须包含 precondition。
    
    缺失 precondition → ValueError
    """
    if op.precondition is None:
        raise ValueError(
            f"SET_FACT operation on {op.path} missing required precondition. "
            f"Cannot propose uncommitted overwrite."
        )
```

---

## 决策 D：SET_FACT 契约

### SET_FACT 定义

```python
@dataclass(frozen=True)
class SetFactOperation(Operation):
    """
    设置事实值操作。
    
    必需字段：
        subject: EntityId（事实所属实体）
        scope: ProjectId（项目隔离）
        path: FactPath（事实路径，如 "characters.alice.age"）
        value: Any（新值，必须可序列化、有类型）
        precondition: Precondition（前值条件，必需）
        evidence: EvidenceRef（正文位置或证据引用）
    
    Invariants:
        - subject 必须存在于同一 project
        - path 必须是合法 FactPath（不允许跨 project 引用）
        - value 不能是 None（None 用 END_FACT 表达）
        - precondition 必须存在（不允许隐式覆写）
        - evidence 必须指向有效正文位置或 Artifact
    
    验证规则：
        1. subject 存在性检查
        2. path 合法性检查（类型、scope）
        3. value 类型检查（符合 path schema）
        4. precondition 评估（当前 Canon 状态）
        5. evidence 可追溯性检查
    
    Fail-closed:
        - 任一检查失败 → 整个 Delta 被拒绝
        - 不允许部分成功、降级或忽略
    """
    operation_type: Literal[OperationType.SET_FACT] = OperationType.SET_FACT
    operation_version: str = "1.0.0"
    
    subject: EntityId
    scope: ProjectId
    path: FactPath
    value: Any
    precondition: Precondition
    evidence: EvidenceRef
    
    def validate_schema(self) -> None:
        """验证 SET_FACT 载荷完整性"""
        if self.subject is None:
            raise ValueError("SET_FACT missing required field: subject")
        if self.scope is None:
            raise ValueError("SET_FACT missing required field: scope")
        if self.path is None:
            raise ValueError("SET_FACT missing required field: path")
        if self.value is None:
            raise ValueError("SET_FACT value cannot be None (use END_FACT instead)")
        if self.precondition is None:
            raise ValueError("SET_FACT missing required field: precondition")
        if self.evidence is None:
            raise ValueError("SET_FACT missing required field: evidence")
```

### SET_FACT 验证流程

```python
def validate_set_fact(
    op: SetFactOperation,
    canon_state: CanonState,
) -> ValidationResult:
    """
    验证 SET_FACT 操作。
    
    步骤：
    1. Subject 存在性：subject 必须在 Canon 中存在
    2. Scope 隔离：subject 和 path 必须在同一 project
    3. Path 合法性：path 必须符合 FactPath schema
    4. Value 类型：value 必须符合 path 的类型要求
    5. Precondition 评估：当前 Canon 状态必须满足 precondition
    6. Evidence 可追溯：evidence 必须指向有效来源
    
    任一失败 → ValidationResult(pass=False, reason=...)
    全部通过 → ValidationResult(pass=True)
    """
    # 1. Subject existence
    if not canon_state.entity_exists(op.subject):
        return ValidationResult(
            pass_=False,
            reason=f"Subject {op.subject} does not exist in Canon"
        )
    
    # 2. Scope isolation
    if not canon_state.same_project(op.subject, op.scope):
        return ValidationResult(
            pass_=False,
            reason=f"Subject {op.subject} not in scope {op.scope}"
        )
    
    # 3. Path validity
    if not is_valid_fact_path(op.path):
        return ValidationResult(
            pass_=False,
            reason=f"Invalid FactPath: {op.path}"
        )
    
    # 4. Value type
    expected_type = get_path_type(op.path)
    if not isinstance(op.value, expected_type):
        return ValidationResult(
            pass_=False,
            reason=f"Value type mismatch: expected {expected_type}, got {type(op.value)}"
        )
    
    # 5. Precondition evaluation
    current_value = canon_state.get_value(op.subject, op.path)
    if not evaluate_precondition(op.precondition, current_value):
        return ValidationResult(
            pass_=False,
            reason=f"Precondition failed: {op.precondition} (current: {current_value})"
        )
    
    # 6. Evidence traceability
    if not is_valid_evidence_ref(op.evidence):
        return ValidationResult(
            pass_=False,
            reason=f"Invalid evidence reference: {op.evidence}"
        )
    
    return ValidationResult(pass_=True)
```

---

## 决策 E：END_FACT 契约

### END_FACT 定义

```python
@dataclass(frozen=True)
class EndFactOperation(Operation):
    """
    结束事实生命周期操作（tombstone，不是删除）。
    
    必需字段：
        subject: EntityId
        scope: ProjectId
        path: FactPath
        precondition: Precondition（必须 ExpectPresent 或 ExpectValue）
        evidence: EvidenceRef
    
    语义：
        - 标记事实生命周期结束（如角色死亡 → age 不再更新）
        - 不是物理删除（历史仍可查）
        - 后续 SET_FACT 在该 path 上应被拒绝（除非明确 Retcon）
    
    与 NULL 的区别：
        - END_FACT: 生命周期终止，历史保留
        - NULL in SET_FACT: 禁止（用 END_FACT 代替）
    
    前置条件约束：
        - 必须 ExpectPresent 或 ExpectValue（不能 END 不存在的事实）
        - 不允许 ExpectAbsent（逻辑矛盾）
    """
    operation_type: Literal[OperationType.END_FACT] = OperationType.END_FACT
    operation_version: str = "1.0.0"
    
    subject: EntityId
    scope: ProjectId
    path: FactPath
    precondition: Precondition
    evidence: EvidenceRef
    
    def validate_schema(self) -> None:
        """验证 END_FACT 载荷"""
        if self.subject is None:
            raise ValueError("END_FACT missing required field: subject")
        if self.scope is None:
            raise ValueError("END_FACT missing required field: scope")
        if self.path is None:
            raise ValueError("END_FACT missing required field: path")
        if self.precondition is None:
            raise ValueError("END_FACT missing required field: precondition")
        if isinstance(self.precondition, ExpectAbsent):
            raise ValueError("END_FACT cannot have ExpectAbsent precondition")
        if self.evidence is None:
            raise ValueError("END_FACT missing required field: evidence")
```

---

## 决策 F：UNDO_FACT 契约

### UNDO_FACT 定义

```python
@dataclass(frozen=True)
class UndoFactOperation(Operation):
    """
    撤销之前的事实设定操作（不是删除，不是 END）。
    
    必需字段：
        subject: EntityId
        scope: ProjectId
        path: FactPath
        original_commit_ref: CommitId（指向被撤销的 Canon commit）
        precondition: Precondition（当前值必须等于被撤销 commit 设定的值）
        evidence: EvidenceRef（撤销理由）
    
    语义：
        - 撤销特定 Canon commit 引入的事实
        - 恢复到该 commit 之前的状态
        - 不是通用"删除"，必须指向具体被撤销 commit
    
    与 END_FACT 的区别：
        - UNDO_FACT: 纠错，"之前的设定是错的"
        - END_FACT: 生命周期结束，"事实曾经正确，现在终止"
    
    前置条件约束：
        - 必须 ExpectValue（当前值等于被撤销 commit 的值）
        - 不允许其他 precondition（防止撤销已被覆盖的值）
    
    Idempotency:
        - 相同 (subject, path, original_commit_ref) → 返回原 receipt
        - 不同 original_commit_ref → 创建新 UNDO
    """
    operation_type: Literal[OperationType.UNDO_FACT] = OperationType.UNDO_FACT
    operation_version: str = "1.0.0"
    
    subject: EntityId
    scope: ProjectId
    path: FactPath
    original_commit_ref: CommitId
    precondition: ExpectValue  # Must match original commit's value
    evidence: EvidenceRef
    
    def validate_schema(self) -> None:
        """验证 UNDO_FACT 载荷"""
        if self.subject is None:
            raise ValueError("UNDO_FACT missing required field: subject")
        if self.scope is None:
            raise ValueError("UNDO_FACT missing required field: scope")
        if self.path is None:
            raise ValueError("UNDO_FACT missing required field: path")
        if self.original_commit_ref is None:
            raise ValueError("UNDO_FACT missing required field: original_commit_ref")
        if not isinstance(self.precondition, ExpectValue):
            raise ValueError("UNDO_FACT precondition must be ExpectValue")
        if self.evidence is None:
            raise ValueError("UNDO_FACT missing required field: evidence")
```

---

## 决策 G：UNKNOWN vs NO_CHANGE vs UNDO_FACT 语义区分

### 三种不同语义

| 概念 | 类型 | 语义 | 表达方式 | 示例 |
|------|------|------|---------|------|
| **UNKNOWN** | 状态值 | 事实存在但值未知 | SET_FACT with value=UNKNOWN | 角色年龄未揭示 |
| **NO_CHANGE** | Delta 结果 | 提议后发现无需变更 | 空 operations 列表 | 正文重复前章末尾 |
| **UNDO_FACT** | 操作类型 | 撤销之前的错误设定 | UNDO_FACT operation | 纠正角色名字拼写错误 |

### UNKNOWN 作为值

```python
class FactValue(Enum):
    """
    事实值的特殊状态。
    
    UNKNOWN: 事实存在但值未知（非 None，非空）
    """
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SetFactOperation:
    # ...
    value: Any  # Can be FactValue.UNKNOWN
    
    def validate_schema(self) -> None:
        # ...
        # value=UNKNOWN 是合法值，不是缺失字段
        # value=None 被禁止（用 END_FACT）
        pass
```

**UNKNOWN 语义**：
- 表示"我们知道这个事实应该存在，但具体值未知"
- 不等于 None（None 被禁止在 SET_FACT 中）
- 不等于"不存在"（不存在用 ExpectAbsent）
- 可以从 UNKNOWN 转为具体值（precondition: ExpectUnknown）
- 不能从具体值覆写为 UNKNOWN（防止信息丢失，除非明确授权）

### NO_CHANGE 作为 Delta 结果

```python
def extract_delta_from_text(
    text: str,
    current_canon: CanonState,
) -> NarrativeDelta:
    """
    从正文抽取 Delta。
    
    如果正文未引入任何状态变化（如重复前章收尾），
    返回空 operations 的 Delta（NO_CHANGE）。
    
    这不是错误，是合法的 Delta 结果。
    """
    operations = extract_operations(text, current_canon)
    
    if len(operations) == 0:
        # NO_CHANGE: valid Delta, empty operations
        return NarrativeDelta(
            delta_id=generate_delta_id(),
            project_id=current_canon.project_id,
            operations=[],  # Empty list = NO_CHANGE
            source_chapter=text.chapter_ref,
            created_at=datetime.now(UTC),
            authority="extractor",
            provenance={"text_hash": hash_text(text)},
        )
    
    return NarrativeDelta(
        delta_id=generate_delta_id(),
        project_id=current_canon.project_id,
        operations=operations,
        ...
    )
```

**NO_CHANGE 语义**：
- 表示"正文未引入新的状态变化"
- operations = [] （空列表，不是 None）
- 仍是合法 Delta，可提交到 Canon（产生"无变化"的 commit）
- 不影响 parent，不推进 HEAD（或产生 no-op commit）

### UNDO_FACT 作为操作

见决策 F。

**三者不可互换**：
- UNKNOWN 是值，NO_CHANGE 是结果，UNDO_FACT 是操作
- 不能用 UNKNOWN 表达"无变化"
- 不能用 NO_CHANGE 表达"值未知"
- 不能用 SET_FACT(value=None) 表达"撤销"

---

## 决策 H：Reducer 纯函数契约

### Reducer 定义

```python
class Reducer(Protocol):
    """
    Reducer 将 Operation 应用到 Canon 状态的纯函数。
    
    契约：
    1. Pure: 无副作用，不修改输入
    2. Deterministic: 相同输入 → 相同输出
    3. Versioned: Reducer 有版本，版本变更需迁移
    4. Fail-closed: 失败拒绝整个 Delta，不部分成功
    5. Provider-independent: 不依赖特定 LLM provider
    
    签名：
        (canon_state, operation) -> new_canon_state | Error
    
    不允许：
    - 修改 canon_state（immutable input）
    - 访问外部状态（数据库、API、文件系统）
    - 依赖随机数、当前时间（除非显式传入）
    - 部分应用操作（all-or-nothing）
    - 调用 LLM provider API
    """
    
    def apply(
        self,
        canon_state: CanonState,
        operation: Operation,
    ) -> CanonState:
        """
        应用操作到 Canon 状态。
        
        Args:
            canon_state: 当前 Canon 状态（immutable）
            operation: 待应用操作
        
        Returns:
            new_canon_state: 新状态（如成功）
        
        Raises:
            ReducerError: 操作失败（前置条件不满足、类型错误等）
        
        Invariants:
            - canon_state 不可变
            - 相同输入 → 相同输出
            - 失败 → 抛异常，不返回部分状态
        """
        raise NotImplementedError
```

### SET_FACT Reducer 实现示例

```python
class SetFactReducer(Reducer):
    """SET_FACT 操作的 Reducer"""
    
    version: str = "1.0.0"
    
    def apply(
        self,
        canon_state: CanonState,
        operation: SetFactOperation,
    ) -> CanonState:
        """
        应用 SET_FACT 操作。
        
        步骤：
        1. 验证操作 schema
        2. 评估 precondition
        3. 应用状态变更
        4. 返回新状态
        
        Fail-closed: 任一步骤失败 → ReducerError
        """
        # 1. Schema validation
        operation.validate_schema()
        
        # 2. Precondition evaluation
        current_value = canon_state.get_value(
            operation.subject,
            operation.path
        )
        
        if not evaluate_precondition(operation.precondition, current_value):
            raise ReducerError(
                f"Precondition failed: {operation.precondition} "
                f"(current: {current_value})"
            )
        
        # 3. Apply state change (pure function, returns new state)
        new_state = canon_state.set_value(
            subject=operation.subject,
            path=operation.path,
            value=operation.value,
            evidence=operation.evidence,
        )
        
        # 4. Return new state
        return new_state
```

### Fail-Closed 语义

**原则**：
- 任何验证失败 → 整个 Delta 被拒绝
- 不允许部分成功、降级或忽略错误
- 不允许"尽力而为"模式

**示例**：
```python
# ❌ 错误：部分成功
def apply_delta_partial_success(delta: NarrativeDelta) -> CanonState:
    new_state = initial_state
    for op in delta.operations:
        try:
            new_state = reducer.apply(new_state, op)
        except ReducerError:
            # 错误：跳过失败操作，继续下一个
            continue
    return new_state


# ✅ 正确：Fail-closed
def apply_delta_fail_closed(delta: NarrativeDelta) -> CanonState:
    new_state = initial_state
    for op in delta.operations:
        # 任一失败 → 抛异常，整个 Delta 被拒绝
        new_state = reducer.apply(new_state, op)
    return new_state
```

---

## 决策 I：Type Safety & Scope Safety

### Type Safety

```python
@dataclass(frozen=True)
class FactPath:
    """
    事实路径，带类型信息。
    
    示例：
        "characters.alice.age" → type=int
        "characters.bob.relationships" → type=list[RelationshipId]
    
    Invariants:
        - path 必须注册在 FactPath schema
        - 每个 path 有明确类型
        - SET_FACT 的 value 必须符合 path 类型
    """
    path: str
    expected_type: type
    
    def validate_value_type(self, value: Any) -> None:
        """验证 value 类型"""
        if not isinstance(value, self.expected_type):
            raise TypeError(
                f"Type mismatch for {self.path}: "
                f"expected {self.expected_type}, got {type(value)}"
            )


def get_fact_path(path_str: str) -> FactPath:
    """
    从 path 字符串获取 FactPath schema。
    
    未注册 path → ValueError
    """
    if path_str not in FACT_PATH_REGISTRY:
        raise ValueError(f"Unregistered FactPath: {path_str}")
    
    return FACT_PATH_REGISTRY[path_str]
```

### Scope Safety

```python
def validate_scope_isolation(
    operation: Operation,
    canon_state: CanonState,
) -> None:
    """
    验证操作不跨 project 引用。
    
    检查：
    1. operation.subject 必须在 operation.scope 中
    2. 所有引用的 EntityId 必须在同一 project
    3. 不允许跨 project 的 relationship
    
    违反 → ValueError
    """
    # 1. Subject in scope
    if not canon_state.entity_in_project(operation.subject, operation.scope):
        raise ValueError(
            f"Subject {operation.subject} not in scope {operation.scope}"
        )
    
    # 2. All referenced entities in same project
    if isinstance(operation, SetFactOperation):
        if is_entity_reference(operation.value):
            referenced_entities = extract_entity_refs(operation.value)
            for entity_id in referenced_entities:
                if not canon_state.entity_in_project(entity_id, operation.scope):
                    raise ValueError(
                        f"Cross-project reference: {entity_id} not in {operation.scope}"
                    )
```

---

## 决策 J：Evidence Requirements

### Evidence Reference

```python
@dataclass(frozen=True)
class EvidenceRef:
    """
    证据引用，指向正文位置或 Artifact。
    
    必需字段：
        source_type: 证据类型（TEXT | ARTIFACT）
        source_ref: 具体引用（章节+段落 或 artifact_id）
        content_hash: 来源内容 hash（可追溯性）
    
    Invariants:
        - source_ref 必须可解析
        - content_hash 必须可验证
        - 证据来源必须在 Canon 或 staging area
    """
    source_type: Literal["TEXT", "ARTIFACT"]
    source_ref: str  # e.g., "chapter_5:paragraph_3" or "artifact_abc123"
    content_hash: str  # SHA-256 of source content


def validate_evidence_ref(
    evidence: EvidenceRef,
    canon_state: CanonState,
) -> None:
    """
    验证证据引用可追溯。
    
    检查：
    1. source_ref 格式合法
    2. 引用的来源存在
    3. content_hash 匹配
    
    失败 → ValueError
    """
    if evidence.source_type == "TEXT":
        # Parse chapter:paragraph reference
        chapter_ref, paragraph_ref = parse_text_ref(evidence.source_ref)
        
        # Verify chapter exists
        if not canon_state.chapter_exists(chapter_ref):
            raise ValueError(f"Chapter {chapter_ref} does not exist")
        
        # Verify paragraph exists and hash matches
        paragraph_content = canon_state.get_paragraph(chapter_ref, paragraph_ref)
        if hash_content(paragraph_content) != evidence.content_hash:
            raise ValueError(
                f"Evidence hash mismatch: {evidence.source_ref}"
            )
    
    elif evidence.source_type == "ARTIFACT":
        # Verify artifact exists
        if not canon_state.artifact_exists(evidence.source_ref):
            raise ValueError(f"Artifact {evidence.source_ref} does not exist")
        
        # Verify hash matches
        artifact = canon_state.get_artifact(evidence.source_ref)
        if artifact.content_hash != evidence.content_hash:
            raise ValueError(
                f"Evidence hash mismatch: {evidence.source_ref}"
            )
```

### Evidence 与 Traceability

**要求**：
- 每个 Operation 必须有 evidence
- Evidence 必须指向可追溯来源（正文或 Artifact）
- Evidence hash 必须绑定来源内容
- 修改来源内容 → evidence 失效 → 重新抽取 Delta

**不允许**：
- 无 evidence 的 Operation
- 伪造 evidence（hash 不匹配）
- 引用不存在的来源
- 引用未 committed 的临时内容（除非在 staging area）

---

## 决策 K：Authority Boundary

### NarrativeDelta 提议权限 ≠ Canon 提交权限

**分层权限**：

| 层次 | 角色 | 权限 | 限制 |
|------|------|------|------|
| **Proposal** | Extractor, Planner, Human | 创建 NarrativeDelta | 不能直接修改 Canon |
| **Validation** | Quality Gate | 验证 Delta | 可拒绝，不能修改 Canon |
| **Authorization** | Permit Issuer | 签发 Permit | 可拒绝，不能修改 Canon |
| **Commit** | CanonCommitService | 提交 Delta 为 Canon | **唯一** 修改 Canon 的路径 |

**关键边界**：
- NarrativeDelta 是 **proposal**，不是 Canon state
- 只有 CanonCommitService 可以修改 Canon
- Extractor/Planner 只能提议，不能提交
- Quality Gate 可以拒绝，不能批准（批准权在 Permit Issuer）
- Permit Issuer 可以签发许可，不能直接提交

### 集成流程

```
Extractor/Planner
    ↓ creates
NarrativeDelta (PROPOSED)
    ↓ validates
Quality Gate
    ↓ (if pass)
NarrativeDelta (VALIDATED)
    ↓ requests authorization
Permit Issuer
    ↓ (if authorized)
Permit + NarrativeDelta (ACCEPTED)
    ↓ commits
CanonCommitService
    ↓ (atomic CAS)
Canon (COMMITTED)
```

**不允许的路径**：
- ~~Extractor → Canon~~（绕过验证）
- ~~Quality Gate → Canon~~（绕过授权）
- ~~Permit Issuer → Canon~~（绕过唯一提交路径）
- ~~NarrativeDelta.status = COMMITTED~~（Delta 不自证提交）

---

## 拒绝的备选方案

### Option A：自由字典变化语言

```python
# ❌ 拒绝
delta = {
    "changes": [
        {"path": "characters.alice.age", "value": 30},  # 无类型
        {"path": "unknown_field", "value": "anything"},  # 未注册
    ]
}
```

**拒绝理由**：
- 无类型安全
- 无前置条件
- 无 schema 验证
- 无版本控制
- 验证责任推给运行时或 Prompt

---

### Option B：ExpectAny 允许覆写

```python
# ❌ 拒绝
SetFactOperation(
    subject="alice",
    path="age",
    value=30,
    precondition=ExpectAny(),  # 无论当前值是什么都覆写
    ...
)
```

**拒绝理由**：
- 失去前置条件保护
- 可能覆盖重要事实
- 无法检测冲突
- 降低 Canon 可靠性

---

### Option C：NULL 表达删除

```python
# ❌ 拒绝
SetFactOperation(
    subject="alice",
    path="age",
    value=None,  # 用 None 表达删除
    ...
)
```

**拒绝理由**：
- NULL 语义不明确（删除？未知？无变化？）
- 与 Python None 混淆
- END_FACT 和 UNDO_FACT 提供明确语义
- 生命周期终止 ≠ 删除

---

### Option D：部分成功模式

```python
# ❌ 拒绝
def apply_delta(delta: NarrativeDelta) -> PartialResult:
    succeeded = []
    failed = []
    for op in delta.operations:
        try:
            apply(op)
            succeeded.append(op)
        except:
            failed.append(op)
    return PartialResult(succeeded, failed)
```

**拒绝理由**：
- 破坏事务性
- 部分成功 → 不一致状态
- 难以回滚
- 违反 Fail-closed 原则

---

### Option E：Provider-dependent Reducer

```python
# ❌ 拒绝
class LLMReducer(Reducer):
    def apply(self, canon_state, operation):
        # 调用 LLM 判断是否应用操作
        response = llm_client.call(...)
        if response.should_apply:
            return apply_op(canon_state, operation)
        else:
            return canon_state
```

**拒绝理由**：
- 非确定性
- 非纯函数
- 依赖外部 Provider
- 无法重建 Canon 状态

---

## 影响与验证

### 对 V2-005/V2-006/V2-061/V2-007 的影响

**无 Schema 变更**：
- NarrativeDelta 是新增能力
- 不修改已有 Entity/Relationship/Character/Event/Promise
- V2-008 消费这些现有类型，不替代它们

**集成点**：
- SetFactOperation.subject 使用 V2-005 EntityId
- SetFactOperation 可设置 V2-061 Character 的派生字段
- SetFactOperation 可设置 V2-007 Event 的 occurrence_chapter
- Scope isolation 复用 V2-005 ProjectId

### 对 Canon (V2-009/V2-010) 的影响

**重要说明**：以下描述的是 **未来 Canon integration 的语义要求**，不属于 V2-008 实现范围。

1. **Canon Commit 协议扩展**（V2-009/V2-010 实现）：
   - 需支持 NarrativeDelta 类型提交
   - 需支持 idempotent key（Delta + parent）
   - 需支持 CAS（compare-and-swap）

2. **Reducer Registry**（V2-009 实现）：
   - 维护 OperationType → Reducer 映射
   - 支持版本化 Reducer
   - 支持 Reducer 升级和迁移

3. **V2-008 职责边界**：
   - V2-008 定义 NarrativeDelta 领域语义和 hard invariants
   - V2-008 提供 in-memory domain model 和 validation
   - V2-008 不实现 persistence、不依赖 CanonCommitService
   - V2-008 提供 Reducer 接口和参考实现，persistence integration 由 V2-009 实现

### Schema 影响

**Schema 设计边界**（与 ADR-003 保持一致）：

以下 schema 文件 **不属于 V2-008 当前强制交付物**，除非正式更新 `plan/machine/implementation-backlog.yaml` 的 `artifacts` 列表：

- `specs/schemas/narrative-delta.schema.json`
- `specs/schemas/operation.schema.json`
- `specs/schemas/set-fact-operation.schema.json`
- `specs/schemas/end-fact-operation.schema.json`
- `specs/schemas/undo-fact-operation.schema.json`

**当前决策**：
- Schema artifacts = **DEFER**（延后到 schema contract formalization 任务）
- V2-008 定义 domain semantics，不强制要求 JSON Schema 输出
- 如需 schema validation，应作为独立任务或 V2-009 persistence layer 的一部分

**如实施 schema**，设计原则：
- 仅包含 BASE 字段（遵循 ADR-002 原则）
- `additionalProperties: false`
- UUID v4 format validation for all IDs
- Precondition union type validation

### 代码影响

**V2-008 authoritative artifacts**（根据 `plan/machine/implementation-backlog.yaml`）：
- `src/anovel/domain/narrative_delta.py`
- `tests/contract/test_v2_008.py`

**实现约束**：
- `test_v2_008.py` **必须存在**作为 authoritative acceptance contract
- 可增加辅助测试文件，但**不得替代** `test_v2_008.py`
- 如需拆分测试，`test_v2_008.py` 应至少包含核心 acceptance scenarios

**实现建议**（可在实现时调整）：
- `narrative_delta.py` 可包含 NarrativeDelta, Operation, Reducer 相关定义
- 如需拆分模块，须保持 `narrative_delta.py` 作为公开入口，或先走 governance 变更流程

### 数据库影响（V2-009 实现时）

**预期新表**（Schema 设计属于 V2-009）：
- `narrative_deltas`
- `operations`（或嵌入 Delta JSON）
- Reducer registry（可能在代码中，不一定建表）

**不在 ADR-004 范围**：
- 具体 column types
- Indexes
- Migration scripts

### 验收影响

**AT-V2-008 必须验证**：
1. SET_FACT 缺必要路径值证据被拒绝
2. UNKNOWN 与 NO_CHANGE 及撤销明确区分
3. 未注册操作和错类型载荷不能成为提交提议

**具体测试场景**：
- SET_FACT 缺 subject → ValueError
- SET_FACT 缺 precondition → ValueError
- SET_FACT value=None → ValueError（应用 END_FACT）
- 未注册 OperationType → ValueError
- 类型不匹配 → ValidationError
- 前置条件失败 → ReducerError
- UNKNOWN 作为值 → 合法
- NO_CHANGE (空 operations) → 合法
- UNDO_FACT 指向不存在的 commit → ValidationError

---

## 生效与替代

### 生效条件

1. **ADR-004 状态 = ACCEPTED**
2. **登记到 plan/machine/decision-register.yaml**
3. **V2-008 实现前置条件满足**

### 不替代其他 ADR

ADR-004 是独立决策，不替代 ADR-001/ADR-002/ADR-003。

### Machine 登记更新

```yaml
- id: ADR-004
  title: 有限变化语言与 reducer 前置条件
  status: ACCEPTED
  owner_role: domain-maintainer
  related_tasks:
  - V2-008
  - V2-010
  - V2-017
  decision_due_task: V2-008
  timing: before_interface_implementation
  decision_record: validation/execution/V2-008/adr-004-decision.yaml
  verification_refs: []
```

**说明**：
- `decision_record` 指向 decision evidence file
- Decision evidence 再通过 `artifacts` 字段引用 ADR 正文
- 这是统一的 provenance 结构

### V2-008 Implementation Constraints

V2-008 实现必须：
1. 严格遵循 ADR-004 定义的 NarrativeDelta/Operation/Reducer 语义
2. 实现所有 hard invariants 验证
3. 实现有限操作注册表（SET_FACT, END_FACT, UNDO_FACT）
4. 实现前置条件代数（四种 Expect 类型）
5. 明确区分 UNKNOWN/NO_CHANGE/UNDO_FACT
6. 提供 Reducer 纯函数参考实现
7. 不实现 persistence（Canon integration 属于 V2-009）
8. 提供 in-memory domain model 和 validation
9. 不依赖 LLM provider（Reducer 必须 provider-independent）
10. 保证 fail-closed 语义（任一验证失败 → 整个 Delta 拒绝）

---

## 后果

### 积极后果

1. **类型安全**：
   - 有限操作注册表防止未知操作
   - FactPath schema 防止类型错误
   - Precondition 防止冲突覆写

2. **语义清晰**：
   - NarrativeDelta 是 proposal，不是 Canon state
   - UNKNOWN/NO_CHANGE/UNDO_FACT 明确区分
   - SET_FACT/END_FACT/UNDO_FACT 各有清晰语义

3. **可验证性**：
   - Reducer 纯函数 → 可测试
   - Evidence 绑定 → 可追溯
   - Fail-closed → 不产生不一致状态

4. **架构边界明确**：
   - NarrativeDelta 提议权限 ≠ Canon 提交权限
   - CanonCommitService 是唯一 Canon 写路径
   - Quality Gate / Permit Issuer 权限清晰

5. **未来扩展友好**：
   - 可注册新 OperationType（需版本化）
   - Reducer 可升级（需迁移或 Retcon）
   - Precondition 可扩展（增加新 Expect 类型）

### 消极后果

1. **实现复杂度**：
   - 需要维护操作注册表
   - 需要实现前置条件评估引擎
   - 需要实现 Reducer registry

   **可接受**：换取类型安全和 fail-closed 保证

2. **灵活性受限**：
   - 禁止 ExpectAny
   - 禁止自由字典
   - 禁止未注册操作

   **可接受**：防止验证责任推给运行时

3. **Reducer 升级成本**：
   - Reducer 版本变更需迁移
   - 旧 Reducer 需保留以重建历史状态

   **可接受**：V2-009 承担迁移机制

### 风险

1. **如未来需要更复杂前置条件**：
   - ADR-004 定义四种基础 Expect 类型
   - 复杂条件可组合（AND/OR）或扩展新类型
   - 不阻塞当前决策

2. **如需要动态操作类型**：
   - ADR-004 要求操作注册
   - Genre 扩展通过注册机制参与
   - 不阻塞 V2-008 验收

---

## 验证要求

### 单元测试（V2-008 pure-domain 范围）

```python
def test_set_fact_missing_precondition():
    """SET_FACT 缺 precondition → ValueError"""
    with pytest.raises(ValueError, match="missing required field: precondition"):
        SetFactOperation(
            subject="alice",
            scope="project_1",
            path="age",
            value=30,
            precondition=None,  # 缺失
            evidence=EvidenceRef(...),
        )


def test_set_fact_value_none():
    """SET_FACT value=None → ValueError (应用 END_FACT)"""
    with pytest.raises(ValueError, match="value cannot be None"):
        SetFactOperation(
            subject="alice",
            scope="project_1",
            path="age",
            value=None,  # 禁止
            precondition=ExpectPresent(),
            evidence=EvidenceRef(...),
        )


def test_unregistered_operation():
    """未注册操作 → ValueError"""
    with pytest.raises(ValueError, match="not registered"):
        Operation(
            operation_type="UNKNOWN_OP",  # 未注册
            operation_version="1.0.0",
        )


def test_precondition_expect_value_mismatch():
    """前置条件失败 → ReducerError"""
    canon_state = CanonState(...)
    canon_state.set_value("alice", "age", 25)
    
    op = SetFactOperation(
        subject="alice",
        path="age",
        value=30,
        precondition=ExpectValue(expected_value=20),  # 不匹配
        ...
    )
    
    reducer = SetFactReducer()
    with pytest.raises(ReducerError, match="Precondition failed"):
        reducer.apply(canon_state, op)


def test_unknown_as_value():
    """UNKNOWN 作为值 → 合法"""
    op = SetFactOperation(
        subject="alice",
        path="age",
        value=FactValue.UNKNOWN,  # 合法
        precondition=ExpectAbsent(),
        evidence=EvidenceRef(...),
    )
    op.validate_schema()  # 应通过


def test_no_change_delta():
    """NO_CHANGE (空 operations) → 合法"""
    delta = NarrativeDelta(
        delta_id="delta_123",
        project_id="project_1",
        operations=[],  # 空列表 = NO_CHANGE
        source_chapter=None,
        created_at=datetime.now(UTC),
        authority="extractor",
        provenance={},
    )
    assert len(delta.operations) == 0  # 合法


def test_undo_fact_precondition_must_be_expect_value():
    """UNDO_FACT precondition 必须是 ExpectValue"""
    with pytest.raises(ValueError, match="must be ExpectValue"):
        UndoFactOperation(
            subject="alice",
            path="age",
            original_commit_ref="commit_123",
            precondition=ExpectAbsent(),  # 错误类型
            evidence=EvidenceRef(...),
        )


def test_reducer_pure_function():
    """Reducer 纯函数：相同输入 → 相同输出"""
    canon_state = CanonState(...)
    op = SetFactOperation(...)
    
    reducer = SetFactReducer()
    
    result_1 = reducer.apply(canon_state, op)
    result_2 = reducer.apply(canon_state, op)
    
    assert result_1 == result_2  # 确定性
    assert canon_state == canon_state  # 不修改输入（immutable）


def test_reducer_fail_closed():
    """Reducer fail-closed：失败拒绝整个 Delta"""
    canon_state = CanonState(...)
    
    delta = NarrativeDelta(
        operations=[
            SetFactOperation(...),  # 成功
            SetFactOperation(..., precondition=ExpectValue(999)),  # 失败
            SetFactOperation(...),  # 不执行
        ],
        ...
    )
    
    with pytest.raises(ReducerError):
        apply_delta_fail_closed(canon_state, delta)
    
    # Canon 状态未改变
    assert canon_state == original_state
```

### Contract 测试（V2-008 domain semantics）

```python
def test_v2_008_ac_01_set_fact_missing_evidence():
    """AC-01: SET_FACT 缺必要路径值证据被拒绝"""
    with pytest.raises(ValueError, match="missing required field"):
        SetFactOperation(
            subject="alice",
            scope="project_1",
            path="age",
            value=30,
            precondition=ExpectPresent(),
            evidence=None,  # 缺失
        )


def test_v2_008_ac_02_unknown_vs_no_change_vs_undo():
    """AC-02: UNKNOWN 与 NO_CHANGE 及撤销明确区分"""
    # UNKNOWN 作为值
    op_unknown = SetFactOperation(
        value=FactValue.UNKNOWN,
        ...
    )
    assert op_unknown.value == FactValue.UNKNOWN
    
    # NO_CHANGE 作为 Delta 结果
    delta_no_change = NarrativeDelta(
        operations=[],  # 空列表
        ...
    )
    assert len(delta_no_change.operations) == 0
    
    # UNDO_FACT 作为操作
    op_undo = UndoFactOperation(
        original_commit_ref="commit_123",
        ...
    )
    assert op_undo.operation_type == OperationType.UNDO_FACT
    
    # 三者不可互换
    assert op_unknown.value != delta_no_change.operations
    assert op_undo != op_unknown


def test_v2_008_ac_03_unregistered_operation_rejected():
    """AC-03: 未注册操作和错类型载荷不能成为提交提议"""
    # 未注册操作
    with pytest.raises(ValueError, match="not registered"):
        validate_operation_registration(
            Operation(operation_type="FAKE_OP", ...)
        )
    
    # 错类型载荷
    with pytest.raises(TypeError):
        SetFactOperation(
            path="age",
            value="thirty",  # 错误类型（应为 int）
            ...
        )
```

---

## 批准前提条件

1. **语义完整性**：NarrativeDelta/Operation/Reducer 语义明确且无歧义
2. **操作注册表完整**：SET_FACT/END_FACT/UNDO_FACT 契约明确
3. **前置条件代数明确**：四种 Expect 类型定义清晰，ExpectAny 被拒绝
4. **语义区分清晰**：UNKNOWN/NO_CHANGE/UNDO_FACT 不可混淆
5. **Reducer 契约明确**：pure, deterministic, versioned, fail-closed, provider-independent
6. **Authority 边界清晰**：NarrativeDelta proposal ≠ Canon commit authority
7. **V2-008 可实现**：实现约束明确，验收可测试
8. **无语义冲突**：与 ADR-001/ADR-002/ADR-003 及现有 Contract 无冲突

**当前状态**: ACCEPTED — 2026-10-17

---

## 参考

- plan/03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §2 (变化语言)
- plan/03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §3 (唯一提交协议)
- plan/03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §6 (Artifact 身份、hash 与血缘)
- ADR-002 (BASE/DERIVED/CACHE 分类原则)
- ADR-003 (Event/Promise 语义，immutability 和 authority 模式)
- V2-008 Task Definition (plan/machine/implementation-backlog.yaml)
- AT-V2-008 Acceptance Scenarios (plan/machine/test-catalog.yaml)
