# ADR-005: 规范化字节哈希与原始正文身份

**Status**: REQUIRED  
**Decision Due**: V2-009  
**Owner**: canon-maintainer  
**Related Tasks**: V2-009, V2-010

## Context

03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md 54行要求：

> 正文原始 UTF-8 字节 hash 与结构化规范化 hash 分开。结构化哈希的精确算法、数字/时间/Unicode/列表语义和测试向量在 P2 首次实现前通过 ADR 确定；不得使用"语义需要的精度"等不能唯一决定字节的规则。

Artifact 身份需要明确的哈希语义以支持：
- 内容寻址存储
- 幂等提交检测
- 跨环境重建验证
- 血缘追踪

V2-009 首次实现 Canon persistence schema，必须在代码编写前明确哈希算法、规范化规则和测试向量。

## Decision

### 1. 原始正文哈希 (Raw Text Hash)

**算法**: SHA-256

**输入**: UTF-8 编码字节序列，保持原样

**用途**:
- 原始文件完整性校验
- 检测磁盘/传输损坏
- 证明原始输入未被篡改

**实现**:
```python
import hashlib

def raw_text_hash(text: str) -> str:
    """
    Compute SHA-256 hash of UTF-8 encoded text bytes.
    
    Args:
        text: Unicode string (Python str)
    
    Returns:
        Hex-encoded SHA-256 digest (64 characters)
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
```

**测试向量**:
```python
# Test 1: Empty string
assert raw_text_hash("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

# Test 2: ASCII text
assert raw_text_hash("Hello, World!") == "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"

# Test 3: Unicode (Chinese)
assert raw_text_hash("你好，世界！") == "fa65d94b3532d83fd24ada92dadecfc7ae5370e6dbf762133027a89c2e7202f1"

# Test 4: Newlines preserved
assert raw_text_hash("line1\nline2\n") == "2751a3a2f303ad21752038085e2b8c5f98ecff61a2e4ebbd43506a941725be80"
```

### 2. 结构化规范化哈希 (Canonical Structural Hash)

**算法**: SHA-256

**输入**: JSON 规范化后的 UTF-8 字节

**规范化规则**:

1. **Unicode 规范化**: NFC (Canonical Decomposition followed by Canonical Composition)
2. **数字表示**: 
   - **整数**: 无前导零，负数用 `-` 前缀（如: `0`, `42`, `-17`）
   - **浮点数**: IEEE 754 double precision，Python `json.dumps()` 默认序列化
     - 去除无意义尾随零: `1.0` → `1.0`, `1.50` → `1.5`
     - 科学计数法: 绝对值 < 1e-6 或 >= 1e21 时使用（如: `1e-7`, `1.23e21`）
     - 精度约束: Python double 精度（~15-17 十进制位）
     - **拒绝**: `NaN`, `Infinity`, `-Infinity` (序列化前验证，抛出错误)
   - **精确数值**: 金额、计数等必须精确的值使用整数或字符串
     - 推荐: `amount_cents: 2550` (整数 cents)
     - 可选: `amount: "25.50"` (字符串，保留精确小数)
3. **时间格式**: ISO 8601 UTC with Z suffix, no milliseconds unless non-zero
   - 格式: `YYYY-MM-DDTHH:MM:SSZ` or `YYYY-MM-DDTHH:MM:SS.sssZ`
   - 示例: `2026-10-20T03:15:30Z`
   - **验证责任**: 输入 Schema 必须保证时间戳格式正确，规范化哈希不执行运行时解析验证
   - **测试要求**: 必须包含格式错误时间戳的拒绝测试（在 Schema 验证层）
4. **列表**: 保持原始顺序，不排序
5. **字典**: 按键的 UTF-8 字节序排序
   - **键类型**: JSON 对象键只能是字符串（JSON 规范要求）
   - **重复键**: 规范化后重复键必须拒绝（已在 `_normalize_unicode` 中检测）
6. **布尔值**: `true` / `false` (小写)
7. **Null**: `null`
8. **字符串**: 保持原样，使用 JSON 转义 (`"`, `\`, control characters)
9. **空白**: 无空白，紧凑格式

**JSON 序列化**:
- 使用 `json.dumps(obj, ensure_ascii=False, separators=(',', ':'), sort_keys=True)`
- 不包含多余空格或换行

**实现**:
```python
import hashlib
import json
import math
import unicodedata
from typing import Any

def canonical_hash(obj: Any) -> str:
    """
    Compute SHA-256 hash of canonicalized structured data.
    
    Args:
        obj: JSON-serializable Python object
    
    Returns:
        Hex-encoded SHA-256 digest (64 characters)
    
    Raises:
        ValueError: If obj contains NaN or Infinity
    """
    # Validate no NaN/Infinity
    _validate_no_nan_infinity(obj)
    
    # Normalize Unicode strings recursively
    normalized = _normalize_unicode(obj)
    
    # Serialize to canonical JSON
    canonical_json = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True
    )
    
    # Hash UTF-8 bytes
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

def _validate_no_nan_infinity(obj: Any) -> None:
    """Reject NaN and Infinity values."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"NaN and Infinity are not allowed: {obj}")
    elif isinstance(obj, dict):
        for v in obj.values():
            _validate_no_nan_infinity(v)
    elif isinstance(obj, list):
        for item in obj:
            _validate_no_nan_infinity(item)

def _normalize_unicode(obj: Any) -> Any:
    """Recursively apply NFC normalization to all strings."""
    if isinstance(obj, str):
        return unicodedata.normalize('NFC', obj)
    elif isinstance(obj, dict):
        # Normalize keys AND check for collisions after normalization
        normalized_dict = {}
        for k, v in obj.items():
            normalized_key = _normalize_unicode(k)
            if normalized_key in normalized_dict:
                raise ValueError(f"Key collision after Unicode normalization: {k}")
            normalized_dict[normalized_key] = _normalize_unicode(v)
        return normalized_dict
    elif isinstance(obj, list):
        return [_normalize_unicode(item) for item in obj]
    else:
        return obj
```

**测试向量**:
```python
# Test 1: Simple object with key ordering
obj1 = {"b": 2, "a": 1}
assert canonical_hash(obj1) == canonical_hash({"a": 1, "b": 2})

# Test 2: Unicode normalization (é can be 1 or 2 codepoints)
obj2a = {"name": "é"}  # é as single codepoint
obj2b = {"name": "é"}  # e + combining acute
assert canonical_hash(obj2a) == canonical_hash(obj2b)

# Test 3: Number precision
obj3a = {"value": 1.0}
obj3b = {"value": 1.00}
assert canonical_hash(obj3a) == canonical_hash(obj3b)

# Test 4: List order matters
obj4a = {"items": [1, 2, 3]}
obj4b = {"items": [3, 2, 1]}
assert canonical_hash(obj4a) != canonical_hash(obj4b)

# Test 5: Nested structure
obj5 = {
    "project_id": "proj-001",
    "changes": [
        {"op": "SET_FACT", "path": "char.name", "value": "李明"},
        {"op": "SET_FACT", "path": "char.age", "value": 25}
    ],
    "timestamp": "2026-10-20T03:15:30Z"
}
assert canonical_hash(obj5) == "11ccd2f0c8afcc4f92fb899406608aaa0ce63e7ba06e0e379ac2f83ec5db643b"
```

### 3. 存储模式

Canon persistence schema 同时存储:

```sql
CREATE TABLE artifact_content (
    artifact_id UUID PRIMARY KEY,
    raw_text_hash VARCHAR(64) NOT NULL,  -- SHA-256 of UTF-8 bytes
    canonical_hash VARCHAR(64) NOT NULL, -- SHA-256 of canonical JSON
    raw_text TEXT NOT NULL,
    structured_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_artifact_raw_hash ON artifact_content(raw_text_hash);
CREATE INDEX idx_artifact_canonical_hash ON artifact_content(canonical_hash);
```

### 4. 幂等键与冲突检测

CanonCommitService 使用 **idempotency_key + payload_hash** 组合检测重复提交:

```python
# 幂等检测流程
existing_commit = find_by_idempotency_key(project_id, branch_name, idempotency_key)

if existing_commit:
    current_payload_hash = canonical_hash(changeset)
    if existing_commit.payload_hash == current_payload_hash:
        return existing_commit.receipt  # 幂等重试
    else:
        raise ConflictError("Same key, different payload")
```

**关键约束**:
- idempotency_key 必须由客户端生成（UUID v7 或稳定请求ID）
- payload_hash 使用 canonical_hash(changeset)
- 必须同时验证作用域 (project_id, branch_name)
- 不得仅凭 content hash 判定幂等（需要 key + scope + hash 三者）

**原始哈希用途**:
- 磁盘完整性校验
- 传输验证
- 审计追踪
- 原始文本身份（不参与幂等判定）

### 5. 跨环境测试

V2-009 集成测试必须包含:
1. 相同结构不同格式输入产生相同 canonical_hash
2. Unicode 规范化等价性
3. 数字精度边界
4. 时间格式严格性
5. 跨 Python/PostgreSQL 哈希一致性

## Consequences

### Positive

- 明确、可测试的哈希语义
- 跨环境可重现
- 支持幂等提交和冲突检测
- 原始与结构化分离满足不同需求

### Negative

- 需要严格的规范化实现
- Unicode/数字/时间处理增加复杂度
- 跨语言实现需要测试向量保证一致性

### Risks

- 浮点数精度: 15位有效数字可能不足以表示所有合法数值，但对叙事领域（年龄、距离、时间）足够
- Unicode 边缘情况: 某些罕见字符的 NFC 规范化可能产生意外结果
- 时间戳: 仅支持 UTC，不支持时区偏移

### Mitigation

- 提供参考实现和完整测试向量
- 在 V2-009 集成测试中验证所有边缘情况
- 文档化已知限制

## Verification

V2-009 acceptance criteria 必须包含:
- Python 参考实现通过所有测试向量
- PostgreSQL 存储正确索引两种哈希
- 幂等提交正确返回原收据
- 冲突检测正确拒绝同键异载荷

## References

- 03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §6
- V2-009 task specification
- [Unicode Normalization Forms](https://unicode.org/reports/tr15/)
- [RFC 8785 JSON Canonicalization Scheme](https://datatracker.ietf.org/doc/html/rfc8785)
