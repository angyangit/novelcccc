# ADR-007: Genre 扩展命名空间与状态转移

**Status**: PROPOSED  
**Decision Due**: V2-013  
**Owner**: genre-maintainer  
**Related Tasks**: V2-013, V2-014, V2-015, V2-016

## Context

04_GENRE_AND_STORY_FIXTURES.md §1-2 和 03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §2 定义了 Genre Pack 的边界和扩展机制：

> 每个 Pack 有 ID/version/hash、世界机制、扩展命名空间/Schema、合法状态转移、资源与代价规则、可选叙事策略、质量 rubric、正反例和消费者。

> Genre 扩展通过注册并验证的接口参与，Core 不包含 cultivation_level 或公司财务专属字段。

ADR-007 必须在 V2-013 GenrePack loader 实现前决定：

1. **Pack Identity**: 如何唯一、确定性地标识和验证 GenrePack
2. **Extension Namespace**: Core Canon 与 Genre 专用状态的边界
3. **State Transition Contract**: Genre 如何表达类型化状态转移和前置条件
4. **Binding and Isolation**: 项目如何冻结 Pack 版本，防止污染和错配
5. **Failure Semantics**: 缺失 Pack、版本不匹配、扩展冲突如何明确拒绝

P3 首期冻结两个 Anchor：`urban.business.realistic` 和 `fantasy.eastern.progression`。

## Decision

### 1. GenrePack 稳定身份

**Pack Identity 由二元组 + 内容哈希确定**:
- `pack_id`: 稳定逻辑标识符，包含主版本标识 (例: `urban.business.realistic`)
- `version`: 语义版本 (例: `1.0.0`)
- `content_hash`: Pack 内容的 canonical hash (ADR-005)

**pack_id 语义**:
- 不包含版本后缀（错误: `urban.business.realistic.v1`）
- 正确格式: `{category}.{subcategory}.{variant}` (例: `urban.business.realistic`)
- 版本信息完全由 `version` 字段表达
- 避免 pack_id 中隐含版本导致的重复标识

**两个冻结 Anchor** (P3 首期):
- Pack ID: `urban.business.realistic`, Version: `1.0.0`
- Pack ID: `fantasy.eastern.progression`, Version: `1.0.0`

**不可变性约束**:
```python
@dataclass(frozen=True)
class GenrePackIdentity:
    """Immutable GenrePack identity triple."""
    pack_id: str  # Stable logical ID (e.g., "urban.business.realistic")
    version: str  # Semantic version (e.g., "1.0.0")
    content_hash: str  # SHA-256 canonical hash of pack content (64 hex chars)
```

**内容哈希计算**:

使用 `anovel.canon.hash.canonical_hash()` (ADR-005) 计算 Pack 内容的 SHA-256 哈希。

**输入集合** (Pack YAML 必须包含的字段):
```yaml
pack_id: "urban.business.realistic"
version: "1.0.0"
extension_schemas: [...]
transition_rules: [...]
world_mechanics: {...}
quality_rubric: {...}
```

**排除字段** (不参与哈希计算):
- `content_hash`: 哈希摘要本身（避免自引用）
- YAML 注释
- 文件元数据（修改时间、作者等）
- 外部文件路径（仅保留被引用内容的 hash）

**完整性保证 (Fail-Closed)**:

**三方一致性验证**:
1. **Registry 声明**: `(pack_id, version, content_hash)` 在 `specs/genres/registry.yaml`
2. **Pack 文件内容**: `specs/genres/{pack_file_path}` 的实际规范化内容
3. **调用方请求**: 项目绑定时提供的 `GenrePackIdentity`

**验证流程**:
```python
# Step 1: Registry 查询
registry_metadata = registry.get_pack(pack_id, version)
registry_hash = registry_metadata.identity.content_hash

# Step 2: Pack 文件加载与哈希计算
pack_content = load_yaml(registry_metadata.pack_file_path)
hashable_content = {
    "pack_id": pack_content["pack_id"],
    "version": pack_content["version"],
    "extension_schemas": pack_content.get("extension_schemas", []),
    "transition_rules": pack_content.get("transition_rules", []),
    "world_mechanics": pack_content.get("world_mechanics", {}),
    "quality_rubric": pack_content.get("quality_rubric", {})
}
file_hash = canonical_hash(hashable_content)

# Step 3: 调用方提供的 hash
caller_hash = pack_identity.content_hash

# Step 4: 三方一致性检查
if registry_hash != file_hash:
    raise RegistryPackFileMismatchError(
        f"Registry declares {registry_hash[:8]}..., "
        f"but Pack file computes to {file_hash[:8]}..."
    )
if caller_hash != registry_hash:
    raise GenrePackHashMismatchError(
        f"Caller expects {caller_hash[:8]}..., "
        f"but registry declares {registry_hash[:8]}..."
    )
# 只有三者完全一致才允许绑定
```

**未知字段处理 (强制拒绝)**:
```python
# Pack YAML 只能包含已知字段
KNOWN_PACK_FIELDS = {
    "pack_id", "version", "content_hash",
    "extension_schemas", "transition_rules",
    "world_mechanics", "quality_rubric"
}
unknown_fields = set(pack_content.keys()) - KNOWN_PACK_FIELDS
if unknown_fields:
    raise ValueError(f"Pack contains unknown top-level fields: {unknown_fields}")
```

**关键字段哈希覆盖**:
- ✅ **extension_schemas**: 定义扩展状态字段和类型
- ✅ **transition_rules**: 定义状态转移前置条件和代价
- ✅ **world_mechanics**: 定义世界规则和约束
- ✅ **quality_rubric**: 定义质量评估标准

**非哈希字段的验证**:
- `extension_namespaces`: 从 Pack YAML 独立声明中加载，验证与 extension_schemas 一致
- `world_anchors`: 从 Pack YAML 独立声明中加载，验证与项目绑定要求匹配
- 这些字段通过 Schema 一致性检查验证，不直接参与 content_hash 计算

**哈希算法**:
- 使用 `anovel.canon.hash.canonical_hash()` (ADR-005)
- 不引入第二套哈希算法
- NFC 规范化、确定性 JSON 序列化、SHA-256

**失败语义**:
- Registry vs. File 不一致 → 拒绝加载 Registry (配置错误)
- Caller vs. Registry 不一致 → 拒绝绑定 (版本不匹配或篡改)
- 未知字段存在 → 拒绝加载 Pack (Schema 违规)
- 缺少必需字段 → 拒绝加载 Pack (不完整)

**哈希计算过程**:
```python
# Step 1: Load Pack YAML
with open(pack_file, "r", encoding="utf-8") as f:
    pack_data = yaml.safe_load(f)

# Step 2: Extract hashable content (exclude content_hash field)
hashable_content = {
    "pack_id": pack_data["pack_id"],
    "version": pack_data["version"],
    "extension_schemas": pack_data.get("extension_schemas", []),
    "transition_rules": pack_data.get("transition_rules", []),
    "world_mechanics": pack_data.get("world_mechanics", {}),
    "quality_rubric": pack_data.get("quality_rubric", {})
}

# Step 3: Compute canonical hash using ADR-005
from anovel.canon.hash import canonical_hash
computed_hash = canonical_hash(hashable_content)

# Step 4: Verify against declared hash
if computed_hash != pack_data["content_hash"]:
    raise GenrePackHashMismatchError(pack_id, pack_data["content_hash"], computed_hash)
```

**验证时机**:
1. **Registry 加载时**: 可选快速校验（仅比较字符串）
2. **项目绑定时**: **强制校验**（重新计算 hash 并比对）
3. **Pack 首次使用时**: 再次校验确保文件未被篡改

**冲突检测**:
```python
# 场景1: 相同 pack_id + version，不同 content_hash → REJECT (GenrePackHashMismatchError)
# 场景2: 相同 pack_id + version，相同 content_hash → 幂等加载
# 场景3: 不同 pack_id 或 version → 独立 Pack
```

**可复现正反例**:

✅ **正例**: 相同内容产生相同哈希
```python
pack1 = {"pack_id": "test.v1", "version": "1.0.0", "extension_schemas": []}
pack2 = {"pack_id": "test.v1", "version": "1.0.0", "extension_schemas": []}
assert canonical_hash(pack1) == canonical_hash(pack2)  # 相同内容 → 相同哈希
```

❌ **反例1**: content_hash 字段不参与计算
```python
pack_with_hash = {
    "pack_id": "test.v1", 
    "version": "1.0.0",
    "extension_schemas": [],
    "content_hash": "abc123..."  # 此字段被排除
}
pack_without_hash = {
    "pack_id": "test.v1",
    "version": "1.0.0", 
    "extension_schemas": []
}
# 计算时都排除 content_hash，因此哈希相同
assert canonical_hash({k: v for k, v in pack_with_hash.items() if k != "content_hash"}) \
    == canonical_hash(pack_without_hash)
```

❌ **反例2**: 篡改检测
```python
declared_hash = "abc123..."
pack_data = {"pack_id": "test.v1", "version": "1.0.0", "extension_schemas": [{"modified": "tampered"}]}
computed_hash = canonical_hash(pack_data)
if computed_hash != declared_hash:
    raise GenrePackHashMismatchError("test.v1", declared_hash, computed_hash)  # 检测到篡改
```

### 2. Genre 扩展命名空间

**Core Canon 职责** (不扩展):
- EntityIdentity (V2-005): 通用实体身份、别名解析
- Relationship (V2-006): 通用关系三元组
- Character/Knowledge/Promise: 通用叙事结构
- Event/ChangeSet: 通用变化语言和事件流
- Commit/Persistence: 通用提交协议和版本控制

**Genre Extension 职责** (专用扩展):
- **World Mechanics**: 题材专属世界规则（修炼体系、商业制度）
- **Typed State**: 类型化状态字段（境界、公司股权、资源池）
- **Transition Rules**: 状态转移前置条件和代价规则
- **Policy Enforcement**: 世界机制一致性检查（V2-014）

**扩展注册机制**:

每个 GenrePack 在 `specs/genres/registry.yaml` 中注册：

```yaml
version: 1.0.0
packs:
  - pack_id: urban.business.realistic
    version: 1.0.0
    content_hash: "abc123..."
    extension_namespaces:
      - "urban.business.company"
      - "urban.business.finance"
    world_anchors:
      - "urban.business.realistic"
    pack_file: "urban_business_realistic_v1_0_0.yaml"
    
  - pack_id: fantasy.eastern.progression
    version: 1.0.0
    content_hash: "def456..."
    extension_namespaces:
      - "fantasy.eastern.cultivation"
      - "fantasy.eastern.realm"
    world_anchors:
      - "fantasy.eastern.progression"
    pack_file: "fantasy_eastern_progression_v1_0_0.yaml"
```

**命名空间隔离**:
- 扩展字段必须使用命名空间前缀：`{namespace}.{field_name}`
- 例：`fantasy.eastern.cultivation.realm_level`, `urban.business.company.equity_ratio`
- **未声明的扩展命名空间 → 抛出 UnknownExtensionNamespaceError**
- 不同 Pack 的扩展命名空间不能重叠

**扩展命名空间验证** (V2-013):
```python
# 场景1: 使用已声明的命名空间 → PASS
changeset = {
    "namespace": "fantasy.eastern.cultivation",  # 在 Pack 中已声明
    "field": "realm_level",
    ...
}
# ProjectGenreBindingService.validate_extension_namespace(project_id, namespace)
# → 不抛出异常，验证通过

# 场景2: 使用未声明的命名空间 → REJECT
changeset = {
    "namespace": "unknown.namespace",  # 未在 Pack 中声明
    "field": "some_field",
    ...
}
# ProjectGenreBindingService.validate_extension_namespace(project_id, namespace)
# → 抛出 UnknownExtensionNamespaceError
```

**AT-V2-013-02 验收要求**:
- 未知 Pack → `GenrePackNotFoundError` (明确拒绝)
- 未知 version → `GenrePackNotFoundError` (明确拒绝)
- 未声明扩展命名空间 → `UnknownExtensionNamespaceError` (明确拒绝)

### 3. 状态转移与合法性边界

**Genre 扩展状态转移契约**:

每个 GenrePack 定义 **Typed State Schema** 和 **Transition Rules**：

```yaml
# specs/genres/fantasy_eastern_progression_v1_0_0.yaml
pack_id: fantasy.eastern.progression
version: 1.0.0
content_hash: "def456..."

extension_schemas:
  - namespace: fantasy.eastern.cultivation
    state_fields:
      - name: realm_level
        type: enum
        values: [MORTAL, QI_REFINING, FOUNDATION, CORE_FORMATION, NASCENT_SOUL]
        description: "Current cultivation realm"
      
      - name: spiritual_root
        type: enum
        values: [NONE, INFERIOR, AVERAGE, SUPERIOR, HEAVEN_DEFYING]
        description: "Innate cultivation talent"
    
    resources:
      - name: spirit_stones
        type: integer
        min: 0
        description: "Cultivation currency"

transition_rules:
  - rule_id: realm_advancement
    from_state: { realm_level: QI_REFINING }
    to_state: { realm_level: FOUNDATION }
    preconditions:
      - sufficient_spiritual_energy: true
      - spiritual_root: [AVERAGE, SUPERIOR, HEAVEN_DEFYING]
    costs:
      - resource: spirit_stones
        amount: 1000
```

**都市商业 Pack 示例**:

```yaml
# specs/genres/urban_business_realistic_v1_0_0.yaml
pack_id: urban.business.realistic
version: 1.0.0
content_hash: "abc123..."

extension_schemas:
  - namespace: urban.business.company
    state_fields:
      - name: ownership_percentage
        type: float
        min: 0.0
        max: 100.0
        description: "Equity ownership in a company"
      
      - name: company_status
        type: enum
        values: [STARTUP, OPERATING, BANKRUPT, ACQUIRED]

  - namespace: urban.business.finance
    resources:
      - name: cash_rmb
        type: integer
        min: 0
        description: "Cash in RMB"

transition_rules:
  - rule_id: equity_transfer
    preconditions:
      - ownership_percentage_sum: <= 100.0  # Total equity cannot exceed 100%
      - legal_authorization: true
```

**V2-013 范围边界**:
- V2-013: 定义接口契约，加载和验证 Pack identity/schema 声明
- V2-014: 实现 Genre hard policy engine，执行 transition_rules
- V2-015/V2-016: 实现具体两个 Pack 的完整 Schema 和规则

### 4. 两个冻结 Anchor

**Anchor 1: `urban.business.realistic`**

允许表达：
- 商业组织、股权、资源流转
- 现代现实制度下的选择和代价
- 财富、关系、市场竞争

**必须阻断的污染**:
- 世界中实际存在修炼、法术等超自然能力
- 重生、系统等非现实机制（除非显式声明为 mechanics 组合）
- 将角色的幻想、梦境、阅读小说内容误判为真实世界事实

**Anchor 2: `fantasy.eastern.progression`**

允许表达：
- 东方幻想世界、境界、能力、资源
- 宗门/势力、交易制度
- 成长、代价、前置条件

**必须阻断的污染**:
- 未声明地套用都市公司股权/财务 Schema
- 将出现"商业""财富"等词汇自动判定为现代公司制度
- 将合法的商会、交易、资源流转误判为机制冲突

**边界判定职责**:
- V2-013: 确保 Pack ID/version/hash 不会错配
- V2-014: 检查扩展字段是否属于声明的命名空间
- V2-014: 语义裁决（梦境、引用、比喻 vs. 真实事实）

### 5. 显式 Pack 绑定与回退行为

**项目绑定契约**:

```python
@dataclass(frozen=True)
class ProjectGenreBinding:
    """Project's frozen GenrePack binding."""
    project_id: ProjectId
    pack_identity: GenrePackIdentity  # Frozen triple
    bound_at: datetime
    binding_hash: str  # Canonical hash of binding record
```

**绑定语义**:
1. **显式绑定**: 项目在初始化时显式声明 `pack_id`, `version`, `expected_hash`
2. **强制哈希校验**: 绑定时重新计算 Pack 内容哈希并验证（不仅比较字符串）
3. **冻结输入**: Pack 绑定后不能因关键词、检索排名、相似名称而改变
4. **版本隔离**: 不同项目可绑定不同 Pack 版本，不会交叉污染
5. **明确拒绝**: Pack 不存在、版本不匹配、hash 校验失败 → 明确失败

**绑定流程** (V2-013):
```python
def bind_pack(
    self,
    project_id: ProjectId,
    pack_identity: GenrePackIdentity
) -> ProjectGenreBinding:
    """
    Bind a GenrePack to a project with mandatory hash verification.
    
    Steps:
    1. Verify Pack exists in registry
    2. Verify hash by recomputing from Pack file (delegates to registry)
    3. If mismatch → raise GenrePackHashMismatchError
    4. If match → create frozen ProjectGenreBinding
    5. Record binding (V2-013: in-memory)
    """
    # Step 1: Verify Pack exists
    metadata = self._registry.get_pack(pack_identity.pack_id, pack_identity.version)
    
    # Step 2-3: Verify hash (delegates to registry's verified implementation)
    if not self._registry.verify_pack_hash(pack_identity):
        raise GenrePackHashMismatchError(
            pack_identity.pack_id,
            pack_identity.content_hash,
            "<actual_hash_from_registry>"
        )
    
    # Step 4: Create frozen binding
    bound_at = datetime.utcnow()
    binding_data = {
        "project_id": project_id,
        "pack_id": pack_identity.pack_id,
        "version": pack_identity.version,
        "content_hash": pack_identity.content_hash,
        "bound_at": bound_at.isoformat()
    }
    binding_hash = canonical_hash(binding_data)
    
    binding = ProjectGenreBinding(
        project_id=project_id,
        pack_identity=pack_identity,
        bound_at=bound_at,
        binding_hash=binding_hash
    )
    
    # Step 5: Persist binding (V2-013: in-memory)
    self._bindings[project_id] = binding
    return binding
```

**绑定记录可追溯性与恢复**:

V2-013 (P3 首期):
- **绑定存储**: 内存 dict (`self._bindings: dict[ProjectId, ProjectGenreBinding]`)
- **验收范围**: 单进程测试场景，验证绑定逻辑和隔离性
- **不持久化**: 满足 AT-V2-013 验收要求，进程重启后绑定不恢复
- **记录可追溯**: binding_hash 唯一标识绑定，包含所有关键字段
- **限制**: 无跨进程恢复能力，测试后丢失

未来持久化 (P4+ 需求明确后):
- **复用 Canon commit 机制**（不创建第二套提交体系）
- **方案**: 将 `ProjectGenreBinding` 作为 Canon 事件持久化
  ```python
  # 通过 CanonCommitService 提交绑定事件
  binding_event = {
      "event_type": "PROJECT_GENRE_BINDING_CREATED",
      "project_id": project_id,
      "pack_identity": {
          "pack_id": pack_identity.pack_id,
          "version": pack_identity.version,
          "content_hash": pack_identity.content_hash
      },
      "bound_at": bound_at.isoformat(),
      "binding_hash": binding_hash
  }
  # 需要扩展 CanonCommitService 以支持 binding event type
  # 当前 Canon 服务尚未实现此事件类型
  ```
- **恢复**: 从 Canon 事件流重建 `ProjectGenreBinding`
- **不引入新系统**: 复用 `canon_commit` 和 `canon_event` 表（ADR-006）
- **前置条件**: Canon 服务需要支持项目级绑定事件（当前未实现）

**V2-013 与持久化的明确边界**:
- ✅ V2-013 验证: 绑定身份、隔离性、hash 校验、冻结语义
- ❌ V2-013 不提供: 进程重启后恢复、跨会话持久化
- 🔮 未来扩展: 需要明确的进程重启恢复需求和 Canon 集成设计

**禁止的回退行为**:
```python
# ❌ 禁止: Pack 不存在时 fallback 到默认都市或玄幻
# ❌ 禁止: 根据关键词静默改写 Pack ID
# ❌ 禁止: 可选策略未命中时替换为第一条相近子流派
# ❌ 禁止: 检索内容与冻结 Pack 冲突时自动切换

# ✓ 正确: 明确失败，诊断信息指出缺失的 Pack/version/扩展
# ✓ 正确: 可选策略未命中 → 返回 "无匹配策略"，保留原 Pack
# ✓ 正确: Pack 升级 → 受控版本变更及重验证流程
```

**错误处理**:

```python
class GenrePackNotFoundError(Exception):
    """Requested GenrePack does not exist."""
    def __init__(self, pack_id: str, version: str):
        self.pack_id = pack_id
        self.version = version

class GenrePackHashMismatchError(Exception):
    """GenrePack content hash verification failed."""
    def __init__(self, pack_id: str, expected_hash: str, actual_hash: str):
        self.pack_id = pack_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash

class UnknownExtensionNamespaceError(Exception):
    """ChangeSet references undeclared extension namespace."""
    def __init__(self, namespace: str, declared_namespaces: list[str]):
        self.namespace = namespace
        self.declared_namespaces = declared_namespaces
```

### 6. 最小接口契约（V2-013）

**V2-013 必须实现的公共 API**:

```python
# src/anovel/genre/registry.py

@dataclass(frozen=True)
class GenrePackIdentity:
    """Immutable GenrePack identity."""
    pack_id: str
    version: str
    content_hash: str

@dataclass(frozen=True)
class GenrePackMetadata:
    """GenrePack metadata and extension declarations."""
    identity: GenrePackIdentity
    extension_namespaces: frozenset[str]
    world_anchors: frozenset[str]
    pack_file_path: str

class GenrePackRegistry:
    """Global read-only GenrePack registry."""
    
    def __init__(self, registry_path: str = "specs/genres/registry.yaml"):
        """Load registry from global read-only directory."""
        ...
    
    def get_pack(
        self, 
        pack_id: str, 
        version: str, 
        expected_hash: str | None = None
    ) -> GenrePackMetadata:
        """
        Retrieve GenrePack metadata with identity verification.
        
        Args:
            pack_id: Logical pack identifier
            version: Semantic version
            expected_hash: Optional content hash for verification
        
        Returns:
            GenrePackMetadata with verified identity
        
        Raises:
            GenrePackNotFoundError: Pack ID or version does not exist
            GenrePackHashMismatchError: Content hash verification failed
        """
        ...
    
    def verify_pack_hash(self, pack_identity: GenrePackIdentity) -> bool:
        """
        Verify Pack content hash by recomputing from source.
        
        Returns:
            True if hash matches, False otherwise
        """
        ...
    
    def list_available_packs(self) -> list[GenrePackIdentity]:
        """List all registered GenrePacks."""
        ...

class ProjectGenreBindingService:
    """Manage project-specific GenrePack bindings."""
    
    def bind_pack(
        self,
        project_id: ProjectId,
        pack_identity: GenrePackIdentity
    ) -> ProjectGenreBinding:
        """
        Bind a GenrePack to a project (frozen).
        
        Verifies Pack exists and hash is valid before binding.
        
        Raises:
            GenrePackNotFoundError: Pack does not exist
            GenrePackHashMismatchError: Hash verification failed
        """
        ...
    
    def get_binding(self, project_id: ProjectId) -> ProjectGenreBinding:
        """
        Retrieve project's frozen GenrePack binding.
        
        Raises:
            ProjectGenreBindingNotFoundError: Project has no binding
        """
        ...
    
    def validate_extension_namespace(
        self,
        project_id: ProjectId,
        namespace: str
    ) -> None:
        """
        Validate that namespace is declared in project's bound Pack.
        
        Args:
            project_id: Project identifier
            namespace: Extension namespace to validate
        
        Raises:
            ProjectGenreBindingNotFoundError: Project has no binding
            UnknownExtensionNamespaceError: Namespace not declared in Pack
        """
        binding = self.get_binding(project_id)
        pack_metadata = self._registry.get_pack(
            binding.pack_identity.pack_id,
            binding.pack_identity.version
        )
        
        if namespace not in pack_metadata.extension_namespaces:
            raise UnknownExtensionNamespaceError(
                namespace,
                pack_metadata.extension_namespaces
            )
```

### 7. 与 Canon Kernel 的接口复用

**复用现有 Canon 机制**:

1. **Identity**: 使用 V2-005 `EntityIdentity` 作为 Genre 扩展实体的基础身份
2. **Hashing**: 使用 ADR-005 `canonical_hash()` 计算 Pack content hash
3. **Commit Protocol**: Genre 状态通过 `CanonCommitService` 提交，不绕过 Canon
4. **Persistence**: Genre 扩展字段作为 Event payload 的一部分持久化
5. **Versioning**: Pack 版本绑定记录在 Canon commit metadata 中

**Genre 扩展不引入**:
- 第二套 Canon 状态持久化体系
- 第二套 Identity 机制
- 第二套 Hash 算法
- 绕过 CanonCommitService 的写路径

**扩展点**:
```python
# Genre-extended ChangeSet operation example
{
    "op": "UPDATE_ENTITY_STATE",
    "entity_id": "char-123",
    "namespace": "fantasy.eastern.cultivation",  # ← Genre extension namespace
    "field": "realm_level",
    "old_value": "QI_REFINING",
    "new_value": "FOUNDATION",
    "evidence": {
        "text_span": "...",
        "content_hash": "..."
    }
}
```

## Consequences

### Positive

- **明确身份**: Pack 三元组 (ID, version, hash) 防止版本混淆和内容篡改
- **清晰边界**: Core Canon 与 Genre 扩展职责明确分离
- **项目隔离**: 不同项目可使用不同 Pack 版本，不会交叉污染
- **明确失败**: 缺失 Pack、版本不匹配、扩展冲突均显式拒绝，不静默 fallback
- **复用基础设施**: 使用现有 Identity、Hash、Commit 机制，避免重复建设

### Negative

- Pack 版本升级需要显式迁移流程，不能自动更新旧项目
- 命名空间前缀增加字段名长度
- Pack 定义的 YAML Schema 需要工具支持和文档

### Risks

- Pack 定义格式需要稳定的 Schema 版本控制
- 命名空间冲突需要在 Pack 注册时检测
- Genre policy engine (V2-014) 实现复杂度可能高于预期

### Mitigation

- V2-013 先实现 Registry loader 和 identity 验证，不提前实现完整 policy engine
- Pack Schema 版本从 1.0.0 开始，采用语义版本控制
- 提供 Pack 定义工具和验证脚本
- 为两个 Anchor 提供详细的正反例和测试矩阵

## Verification

V2-013 acceptance criteria (AT-V2-013) 必须包含:

1. **Identity Binding**: ID、version、hash 均被绑定并核验
2. **Explicit Failure**: 未知 Pack 与扩展拒绝而非默认 fallback
3. **Traceability**: 全局只读目录绑定到项目后仍可追溯
4. **No Silent Replacement**: 显式 Pack 存在而可选策略无命中时保留原 ID/version/hash
5. **Content Verification**: Pack 内容 hash 被篡改时明确失败
6. **Namespace Isolation**: 未声明扩展命名空间被拒绝
7. **Project Isolation**: 两个项目使用不同 Pack 时不会交叉污染
8. **Version Stability**: Pack 版本升级不能静默改变既有作品

## Out of Scope (V2-013)

V2-013 **不实现**:
- 完整 Genre policy engine (V2-014)
- Transition rules 执行引擎 (V2-014)
- 都市商业和东方玄幻的完整 Schema (V2-015, V2-016)
- 语义裁决（梦境 vs. 真实事实）(V2-014)
- Pack 迁移和升级流程 (后续)
- 叙事策略查询和匹配 (后续)

V2-013 **仅实现**:
- GenrePackRegistry: 加载、查询、验证 Pack identity
- ProjectGenreBindingService: 项目 Pack 绑定和冻结
- Extension namespace 声明验证（是否声明，不验证语义正确性）
- 明确的错误诊断

## References

- 03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §2, §6
- 04_GENRE_AND_STORY_FIXTURES.md §1, §2, §6
- ADR-005: Canonical Hash (Pack content hash 复用)
- ADR-006: Root Commit Transaction (Canon commit 协议复用)
- V2-005: Entity Identity (Genre 实体身份基础)
