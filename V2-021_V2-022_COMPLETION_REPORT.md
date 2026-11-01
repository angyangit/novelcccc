# V2-021 真实功能闭环 + V2-022 Q0 确定性验证器 - 完成报告

## 执行摘要

已完成 V2-021 NarrativeDelta Extractor 的真实功能实现和 V2-022 Q0 确定性验证器的集成。所有关键缺口已解决，端到端验证通过。

**状态**: ✅ 完成
**测试**: 25/25 通过 (V2-020: 6, V2-021: 8, V2-021功能: 5, V2-022: 6)
**演示**: 2个场景 + 端到端验证脚本

---

## 关键成果

### 1. OfflineExtractor 构造真实 Operations ✅

**问题**: 原实现返回空的 operations 元组
```python
# 之前
operations=(),  # Offline stub
```

**解决**: 构造真实的 SetFactOperation 对象
```python
# 现在
operation = SetFactOperation(
    operation_type=OperationType.SET_FACT,
    operation_version="1.0.0",
    subject=EntityId("protagonist"),
    scope=ProjectId(series_vision.series_id),
    path=get_fact_path(transition.fact_path),
    value=transition.target_value,
    precondition=ExpectAbsent(),
    evidence=EvidenceRef(
        source_type="TEXT",
        source_ref=f"{contract.chapter_id}:{start_pos}-{end_pos}",
        content_hash=prose_hash,
    ),
)
operation.validate_schema()  # 验证完整性
operations.append(operation)
```

**验证**:
- Operations 通过 `DeltaReducer.apply_delta()` 验证
- 所有字段完整且类型正确
- Evidence 绑定到 prose_hash

### 2. FactPath Registry 扩展 ✅

**扩展路径** (src/anovel/domain/delta.py):
```python
_FACT_PATH_REGISTRY_INTERNAL = {
    # 原有
    "age": FactPath("age", int),
    "is_alive": FactPath("is_alive", bool),
    "name": FactPath("name", str),
    "description": FactPath("description", str),
    # V2-021 测试路径
    "funding_amount": FactPath("funding_amount", int),
    "funding_round": FactPath("funding_round", str),
    "protagonist.realm": FactPath("protagonist.realm", str),
    "protagonist.cultivation_level": FactPath("protagonist.cultivation_level", int),
    "protagonist.location": FactPath("protagonist.location", str),
}
```

**Fail-Closed**: 未注册路径 → INCOMPLETE 状态 + 详细错误信息

### 3. 状态语义修正 ✅

**逻辑改进**:
```python
# 区分三种情况
if found_count < required_count:
    status = ExtractionStatus.INCOMPLETE
elif operations_constructed < found_count:
    # 发现证据但无法构造 operations
    status = ExtractionStatus.INCOMPLETE
    issues.append(f"Operations constructed: {operations_constructed}/{found_count}")
elif required_count == 0:
    status = ExtractionStatus.NO_CHANGES
else:
    status = ExtractionStatus.SUCCESS
```

**语义**: 明确区分 NO_CHANGES (合法无变化) vs INCOMPLETE (缺失) vs FAILED (错误)

### 4. V2-022 Q0 确定性验证器 ✅

**新文件**: `src/anovel/quality/q0.py`

**5项检查**:
1. **required_artifacts**: 所需制品存在 (prose, contract, extraction_result)
2. **prose_hash_match**: prose hash 匹配
3. **delta_evidence_hash**: delta provenance 包含 prose_hash
4. **operations_evidence**: 所有 operations 有有效 evidence
5. **evidence_locations_verified**: 所有 evidence locations 已验证

**Fail-Closed**: 任何检查失败 → `passed=False` + blocking_issues

**集成**: ChapterWorkflow 在质量验证阶段调用 Q0

### 5. 循环依赖解决 ✅

**问题**: workflow.py ↔ q0.py 循环导入

**解决**: 使用 TYPE_CHECKING + 延迟导入
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..quality.q0 import Q0Validator

def __init__(self, ..., q0_validator: "Q0Validator | None" = None):
    if q0_validator is None:
        from ..quality.q0 import Q0Validator  # 延迟导入
        q0_validator = Q0Validator()
    self.q0_validator = q0_validator
```

---

## 测试覆盖

### V2-020 Production Integrity (6 tests) ✅
- 质量失败阻止 canon commit
- 抽取失败阻止 canon commit
- Mock commit 清晰标记
- Prose hash 绑定
- Project ID 不硬编码
- Real mode 未实现

### V2-021 Acceptance Tests (8 tests) ✅
- AT-V2-021-01: Prose hash 不匹配必须阻止
- AT-V2-021-02: 抽取必需 transitions
- AT-V2-021-03: 检测缺失 transitions
- AT-V2-021-04: 区分 NO_CHANGES vs FAILED
- AT-V2-021-05: Evidence locations 验证
- AT-V2-021-06: Project ID 来自 series_vision
- AT-V2-021-07: Prose hash 在 provenance 中
- AT-V2-021-08: Mock prose marker 检测

### V2-021 Functional Tests (5 tests) ✅
- 抽取的 operations 是真实 SetFactOperation
- Operations 通过 DeltaReducer 验证
- Operations 有 evidence 和 prose_hash
- 无 required transitions → 空 operations
- 未注册 fact_path → issues + INCOMPLETE

### V2-022 Q0 Validator Tests (6 tests) ✅
- AT-V2-022-01: Prose hash 不匹配失败
- AT-V2-022-02: 缺失制品失败
- AT-V2-022-03: Delta provenance 缺 prose_hash 失败
- AT-V2-022-04: 未验证 evidence locations 失败
- AT-V2-022-05: 有效抽取通过所有检查
- AT-V2-022-06: Operations 缺 evidence 失败

---

## 演示验证

### 1. extraction_demo.py
- **场景 1**: Urban Business (funding 抽取)
- **场景 2**: Eastern Fantasy (cultivation breakthrough)
- **输出**: 显示 real operations, evidence, provenance

### 2. e2e_validation.py ✅
端到端验证流程:
```
Real prose → Extraction → Real Operations → DeltaReducer → Q0 → SUCCESS
```

**步骤**:
1. 从 prose 抽取状态变化
2. 验证 operations 是真实 SetFactOperation
3. Operations 通过 DeltaReducer 验证
4. Q0 确定性验证器通过
5. Evidence 绑定验证

**输出**: 所有检查通过 ✅

---

## 文件变更

### 修改文件
1. **src/anovel/domain/delta.py**
   - 扩展 FACT_PATH_REGISTRY (5个新路径)

2. **src/anovel/workflow/offline_extractor.py**
   - 导入 SetFactOperation, EvidenceRef, ExpectAbsent, get_fact_path
   - 构造真实 Operations
   - 状态逻辑改进 (区分 found vs constructed)

3. **src/anovel/workflow/workflow.py**
   - 导入 Q0Validator (TYPE_CHECKING + 延迟导入)
   - 添加 q0_validator 参数
   - 在 _validate_quality 中调用 Q0
   - 传递 full_extraction_result 到 Q0

### 新增文件
1. **src/anovel/quality/q0.py** (242 行)
   - Q0Validator 类
   - 5项确定性检查
   - Fail-closed 语义

2. **tests/contract/test_v2_021_functional.py** (282 行)
   - 5个功能测试
   - 验证 real Operations 构造
   - 验证 DeltaReducer 通过

3. **tests/contract/test_v2_022.py** (316 行)
   - 6个 Q0 验证器测试
   - 覆盖所有失败场景

4. **examples/e2e_validation.py** (191 行)
   - 端到端验证脚本
   - 5步验证流程

---

## 关键设计决策

### 1. Operations 构造策略
- **简化**: OfflineExtractor 使用 `EntityId("protagonist")` (真实 extractor 会从 prose 解析)
- **Precondition**: 默认 `ExpectAbsent()` (真实 extractor 会推断)
- **可扩展**: 结构支持未来添加语义判断 (belief vs fact, plan vs action)

### 2. Registry 扩展原则
- **最小扩展**: 仅添加测试/演示必需路径
- **类型安全**: 所有路径有明确类型
- **Fail-closed**: 未注册路径不会静默通过

### 3. Q0 集成策略
- **延迟导入**: 避免循环依赖
- **可选注入**: 支持测试时注入 mock
- **透明传递**: full_extraction_result 通过 delta_result._full_result 传递

### 4. 错误处理
- **分层**: Registry 错误 → issues + INCOMPLETE (不崩溃)
- **诊断**: 详细错误信息指出具体问题
- **Fail-closed**: 任何疑点 → 阻止进入下一阶段

---

## 未来工作 (超出当前范围)

### V2-021 增强
1. **语义判断**: belief vs fact, plan vs action, rumor vs confirmed
2. **Coverage 跟踪**: 真实覆盖率计算 (非固定 100.0)
3. **Evidence 验证**: 真实 prose offset 验证 (非 pattern match)
4. **冲突检测**: 多个证据指向不同值

### V2-022 扩展
1. **Q1-Q3 验证器**: LLM-based quality checks (ADR-011)
2. **Quality 配置**: 可配置检查启用/禁用
3. **Performance**: Q0 批量验证优化

### LLM Extractor
1. **实现 llm_extractor.py**: 使用 Claude 进行语义抽取
2. **Prompt 工程**: 针对不同 genre 的 prompt
3. **Confidence 评估**: 基于 LLM 输出的置信度

---

## 验证清单

✅ OfflineExtractor 返回真实 Operations (非空元组)
✅ Operations 包含所有必需字段 (subject, scope, path, value, precondition, evidence)
✅ Operations 通过 DeltaReducer.apply_delta() 验证
✅ Evidence 绑定到 prose_hash
✅ FactPath registry 扩展 (5个新路径)
✅ 未注册路径 fail-closed (INCOMPLETE + issues)
✅ 状态语义正确 (NO_CHANGES vs INCOMPLETE vs FAILED)
✅ Q0 确定性验证器实现 (5项检查)
✅ Q0 集成到 ChapterWorkflow
✅ 循环依赖解决 (TYPE_CHECKING + 延迟导入)
✅ 25个测试全部通过
✅ 端到端验证脚本通过
✅ 无 mock 绕过 (所有 Operations 真实构造)

---

## 结论

V2-021 和 V2-022 的核心功能已完整实现并验证。系统现在能够：

1. 从真实 prose 抽取状态变化
2. 构造合法的 Operation 对象
3. 通过 DeltaReducer 验证
4. 运行确定性 Q0 检查
5. Fail-closed 保证数据完整性

所有测试通过，端到端验证成功。代码已准备好进行下一阶段开发 (LLM extractor 或 Q1-Q3 validators)。

**交付物**:
- ✅ 真实 Operations 构造
- ✅ Q0 确定性验证器
- ✅ 25个测试 (100% 通过率)
- ✅ 端到端验证脚本
- ✅ 演示场景 (Urban Business + Eastern Fantasy)
