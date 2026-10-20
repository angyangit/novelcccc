# ADR-006: 根提交、短事务、收据与保留闭包

**Status**: ACCEPTED  
**Decision Due**: V2-009  
**Owner**: canon-maintainer  
**Related Tasks**: V2-009, V2-010, V2-011, V2-012

## Context

03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §3-4 定义了唯一提交协议和根提交语义：

> 在短数据库事务中复核状态，通过 CAS 更新 HEAD，写 Canon 事件/提交/收据及必要的可靠投影触发记录。

> P2 用人工/测试初始输入经 CanonCommitService 创建唯一 root；空父提交的语义、并发唯一性、测试权限必须显式。

ADR-006 必须在 V2-009 Canon persistence 首次实现前决定：

1. **Root 唯一性**: 如何防止同一 project/branch 并发创建多个根提交
2. **短事务边界**: 哪些操作必须在同一 PostgreSQL 事务内原子完成
3. **HEAD CAS**: 如何用 Compare-And-Swap 防止并发提交冲突
4. **幂等性**: 相同请求重试如何返回原收据
5. **取消与提交次序**: 竞争条件下的原子决策
6. **Fencing 权限版本**: 如何防止过期执行产生新提交
7. **恢复证据闭包**: 持久化哪些数据以支持完整恢复

## Decision

### 1. 根提交唯一性约束

**问题**: 同一 project/branch 不能有多个 root commit

**方案**: Partial UNIQUE Index + 事务隔离 + 作用域复合外键

```sql
CREATE TABLE canon_commit (
    commit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    parent_commit_id UUID,
    idempotency_key VARCHAR(255) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,  -- Canonical hash from ADR-005
    changeset JSONB NOT NULL,
    permit_ref VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Project scope foreign key
    FOREIGN KEY (project_id) REFERENCES project(id),
    
    -- Idempotency: same key on same branch
    UNIQUE (project_id, branch_name, idempotency_key)
);

-- UNIQUE constraint for composite FK targets (required by PostgreSQL)
-- Must be created BEFORE adding composite FKs
CREATE UNIQUE INDEX idx_commit_scope_identity 
    ON canon_commit(project_id, branch_name, commit_id);

-- Root uniqueness: only one NULL parent per project/branch (Partial UNIQUE Index)
CREATE UNIQUE INDEX unique_root_per_branch 
    ON canon_commit (project_id, branch_name)
    WHERE parent_commit_id IS NULL;

-- NOW add parent scope FK (references idx_commit_scope_identity)
ALTER TABLE canon_commit
    ADD CONSTRAINT fk_parent_scope
    FOREIGN KEY (project_id, branch_name, parent_commit_id) 
    REFERENCES canon_commit(project_id, branch_name, commit_id);

CREATE INDEX idx_commit_branch_head ON canon_commit(project_id, branch_name, created_at DESC);
```

**创建根提交流程**:
1. 客户端提供 `project_id`, `branch_name`, `idempotency_key`, `payload`
2. 服务在 SERIALIZABLE 事务内:
   - 检查幂等性（已存在？）
   - 尝试插入 `parent_commit_id = NULL` 的 commit
   - Partial UNIQUE Index 违反 → 检查幂等（相同 key + hash → 返回原收据）
   - **Root HEAD 初始化**: 使用 INSERT (不是 UPDATE)
     ```sql
     INSERT INTO branch_head (project_id, branch_name, head_commit_id)
     VALUES ($project_id, $branch_name, $commit_id)
     ON CONFLICT (project_id, branch_name) DO NOTHING;
     ```
   - 检查插入行数: 0 = 已存在 root (另一个并发 root 胜出), 1 = 成功
3. 并发 root commits: Partial UNIQUE Index + branch_head PK 保证唯一性

**测试权限**: 
- 测试环境: 允许删除整个 project 重建
- 生产环境: 创建 root 需要 `PROJECT_INIT` 权限
- 不允许在已有提交的 branch 上重新创建 root

### 2. 短事务边界

**原子操作单元** (必须在同一 PostgreSQL 事务内):

```python
async def commit_to_canon(
    project_id: UUID,
    branch_name: str,
    parent_commit_id: UUID | None,
    idempotency_key: str,
    changeset: ChangeSet,
    permit_ref: str,
    execution_version: int
) -> CommitReceipt:
    """
    Commit to canon with idempotency, CAS, and fencing.
    
    Retry logic: caller must retry on SQLSTATE 40001 with SAME idempotency_key
    """
    async with db.transaction(isolation_level="SERIALIZABLE"):
        # CRITICAL: Check idempotency FIRST (before fencing check)
        # Reason: If commit already succeeded, return receipt even if execution was cancelled later
        existing = await find_commit_by_key(project_id, branch_name, idempotency_key)
        payload_hash = canonical_hash(changeset)
        
        if existing:
            if existing.payload_hash == payload_hash:
                # Idempotent retry: same key + same payload
                return existing.receipt  # Return original receipt
            else:
                # Conflict: same key + different payload
                raise ConflictError("Same idempotency key, different payload")
        
        # 1. Check execution version (fencing) - only if NOT idempotent retry
        # Lock execution_control row to prevent concurrent cancellation
        control = await db.fetch_one("""
            SELECT execution_version FROM execution_control
            WHERE project_id = $1 AND branch_name = $2
            FOR UPDATE
        """, project_id, branch_name)
        
        if control is None:
            raise ExecutionControlMissing("Execution control row must exist before commit")
        
        if control.execution_version != execution_version:
            # Version mismatch: execution was cancelled or version incorrect
            raise ExecutionCancelled(
                f"Execution version mismatch: expected {execution_version}, found {control.execution_version}"
            )
        
        # 2. CAS: Verify HEAD matches expected parent (for non-root commits)
        if parent_commit_id is not None:
            current_head = await get_branch_head(project_id, branch_name)
            if current_head != parent_commit_id:
                raise HeadMovedError(f"Expected parent {parent_commit_id}, found {current_head}")
        
        # 3. Write commit
        commit_id = gen_uuid()
        await insert_commit(
            commit_id=commit_id,
            project_id=project_id,
            branch_name=branch_name,
            parent_commit_id=parent_commit_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            changeset=changeset,
            permit_ref=permit_ref
        )
        
        # 4. Update or Initialize HEAD
        if parent_commit_id is None:
            # Root commit: INSERT branch_head
            rows = await db.execute("""
                INSERT INTO branch_head (project_id, branch_name, head_commit_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (project_id, branch_name) DO NOTHING
            """, project_id, branch_name, commit_id)
            if rows == 0:
                # Another concurrent root commit won
                raise RootAlreadyExistsError("Root commit already exists for this branch")
        else:
            # Non-root commit: UPDATE with CAS
            rows = await update_branch_head_cas(
                project_id, branch_name, 
                new_head=commit_id,
                expected_parent=parent_commit_id
            )
            if rows == 0:
                raise HeadMovedError("HEAD changed during commit (CAS failed)")
        
        # 5. Write events
        events = expand_changeset_to_events(changeset)
        await insert_events(commit_id, project_id, events)
        
        # 6. Generate receipt
        receipt = CommitReceipt(
            commit_id=commit_id,
            project_id=project_id,
            branch_name=branch_name,
            parent_commit_id=parent_commit_id,
            timestamp=now(),
            event_count=len(events),
            idempotency_key=idempotency_key,
            payload_hash=payload_hash
        )
        
        return receipt

async def update_branch_head_cas(
    project_id: UUID,
    branch_name: str,
    new_head: UUID,
    expected_parent: UUID
) -> int:
    """
    Update HEAD with CAS check (for non-root commits).
    
    Returns:
        Number of rows updated (0 = CAS failed, 1 = success)
    """
    result = await db.execute("""
        UPDATE branch_head
        SET head_commit_id = $1, updated_at = NOW()
        WHERE project_id = $2
          AND branch_name = $3
          AND head_commit_id = $4
    """, new_head, project_id, branch_name, expected_parent)
    
    return result.rowcount

# Transaction retry wrapper
MAX_RETRIES = 3

async def commit_with_retry(
    project_id: UUID,
    branch_name: str,
    parent_commit_id: UUID | None,
    idempotency_key: str,
    changeset: ChangeSet,
    permit_ref: str,
    execution_version: int
) -> CommitReceipt:
    """Retry on SERIALIZABLE conflict (SQLSTATE 40001)."""
    for attempt in range(MAX_RETRIES):
        try:
            return await commit_to_canon(
                project_id, branch_name, parent_commit_id,
                idempotency_key, changeset, permit_ref, execution_version
            )
        except SerializationError as e:
            if e.sqlstate == '40001' and attempt < MAX_RETRIES - 1:
                # Retry with SAME idempotency_key
                await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                continue
            raise
    
    raise MaxRetriesExceeded("Transaction retry limit exceeded")
```

**事务外操作** (不持有数据库锁):
- 模型调用
- 全文抽取
- 长时间质量检查
- 异步投影更新

### 3. HEAD CAS 实现

**问题**: 防止并发提交覆盖彼此

**方案**: Optimistic locking with parent verification

```sql
CREATE TABLE branch_head (
    project_id UUID NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    head_commit_id UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (project_id, branch_name),
    
    -- HEAD must reference commit in same project/branch (scope isolation)
    -- References idx_commit_scope_identity UNIQUE index
    FOREIGN KEY (project_id, branch_name, head_commit_id)
        REFERENCES canon_commit(project_id, branch_name, commit_id)
);
```

**并发场景**:
- 两个提交 A、B 同时基于 parent P
- A 先提交: HEAD: P → A (成功)
- B 后提交: HEAD 已是 A，期望 P → CAS 失败
- B 客户端重新基于 A 重试

### 4. 幂等性与收据恢复

**幂等键语义**:
- 唯一标识一次逻辑提交意图
- 格式: `{request_id}` (不包含 attempt_id)
- 客户端生成: UUID v7 或带时间戳的稳定 ID
- 重试/重启使用相同幂等键

**收据恢复**:
```python
# 场景1: 网络超时，客户端不知道是否成功
receipt = await commit_to_canon(
    idempotency_key="req-12345",
    payload=changeset_v1
)
# → 成功，返回 receipt_1

# 场景2: 客户端重试（相同 key + payload）
receipt = await commit_to_canon(
    idempotency_key="req-12345",
    payload=changeset_v1  # 相同载荷
)
# → 返回 receipt_1 (幂等)

# 场景3: 客户端错误重试（相同 key + 不同 payload）
receipt = await commit_to_canon(
    idempotency_key="req-12345",
    payload=changeset_v2  # 不同载荷
)
# → ConflictError: "Same key, different payload"
```

**收据内容**:
```python
@dataclass
class CommitReceipt:
    commit_id: UUID
    project_id: UUID
    branch_name: str
    parent_commit_id: UUID | None
    timestamp: datetime
    event_count: int
    idempotency_key: str
    payload_hash: str
```

### 5. 取消与提交的原子次序

**问题**: 执行中的 Worker 产生结果，同时操作者请求取消，谁优先？

**决策**: **Commit-Wins with Fencing**

提交和取消通过 execution_version 实现 fencing，在 SERIALIZABLE 事务内原子检查和更新 execution_control 行。

```sql
CREATE TABLE execution_control (
    project_id UUID NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    execution_version INT NOT NULL DEFAULT 1,
    cancelled_at TIMESTAMPTZ,
    PRIMARY KEY (project_id, branch_name)
);
```

**原子协议**:

1. **提交时检查版本**:
   ```sql
   -- 在 SERIALIZABLE 事务内，执行版本必须精确匹配
   SELECT execution_version FROM execution_control
   WHERE project_id = $1 AND branch_name = $2
   FOR UPDATE;  -- 锁定行，防止并发取消
   
   -- 如果 execution_version != expected_version: 执行已被取消
   -- 如果行不存在: 拒绝提交（需要先初始化）
   ```

2. **取消时递增版本**:
   ```sql
   -- 在独立事务内更新版本（行已存在时）
   UPDATE execution_control
   SET execution_version = execution_version + 1,
       cancelled_at = NOW()
   WHERE project_id = $1 AND branch_name = $2;
   
   -- 如果 UPDATE 返回 0 行（行不存在），则 INSERT 初始版本
   -- 注意：初始化与取消是两个独立操作，不使用 UPSERT 避免重复递增
   ```

**次序规则**:

1. **取消先到达**:
   ```python
   await cancel_execution(project_id, branch_name)
   # → execution_version: 1 → 2
   
   # Worker later attempts commit with old version
   await commit_to_canon(..., execution_version=1)
   # → SELECT execution_version FOR UPDATE → 发现版本 = 2
   # → 1 != 2, raise ExecutionCancelled
   ```

2. **提交先成功**:
   ```python
   # Worker commits successfully (locks execution_control row with FOR UPDATE)
   receipt = await commit_to_canon(..., execution_version=1)
   # → SELECT ... FOR UPDATE (version = 1, matches)
   # → 成功，HEAD 推进，事务提交，释放锁
   
   # User then requests cancel (在提交事务完成后)
   await cancel_execution(project_id, branch_name)
   # → execution_version: 1 → 2
   # → 但不能撤销已成功的提交
   # → 返回: "Commit already succeeded, cancel affects future executions only"
   ```

3. **并发到达**:
   - 提交事务先获得 FOR UPDATE 锁 → 版本匹配，提交成功，取消无效
   - 取消先更新版本 → 提交事务读到新版本，版本不匹配，提交被拒绝
   - SERIALIZABLE + FOR UPDATE 保证全序

**关键约束**:
- 取消不能回滚已成功的提交（Canon 是追加日志）
- 已取消的执行不能产生新提交（版本精确匹配检查）
- 幂等重试恢复原收据（检查在 fencing 之前）
- 缺少 execution_control 行时拒绝提交（安全默认）

**UI 状态**:
- 取消请求处理中: "Cancellation pending..."
- 已取消但提交成功: "Commit succeeded before cancellation"
- 已取消且未提交: "Execution cancelled"

### 6. Fencing 权限版本实现

**执行版本号 (Execution Version)**:
- 每次开始新执行: 记录当前 version
- 每次取消: version += 1
- 提交时: 验证 version 未变

```python
# Worker启动时获取版本
execution_version = await get_execution_version(project_id, branch_name)

# 执行工作（可能很长时间）
result = await long_running_work()

# 提交时携带版本
try:
    receipt = await commit_to_canon(
        ...,
        execution_version=execution_version
    )
except ExecutionCancelled:
    # 执行已被取消，丢弃结果
    return
```

**版本管理**:
```sql
-- 开始新执行（初始化 execution_control 行）
INSERT INTO execution_control (project_id, branch_name, execution_version)
VALUES ($1, $2, 1)
ON CONFLICT (project_id, branch_name) DO NOTHING;

-- 取消执行（递增版本）
UPDATE execution_control
SET execution_version = execution_version + 1,
    cancelled_at = NOW()
WHERE project_id = $1 AND branch_name = $2;

-- 提交时验证（在 commit_to_canon 事务内）
SELECT execution_version FROM execution_control
WHERE project_id = $1 AND branch_name = $2
FOR UPDATE;
-- 如果版本不匹配 → ExecutionCancelled
-- 如果行不存在 → ExecutionControlMissing
```

### 7. 最小恢复证据闭包

**必须持久化的数据** (不可丢失):

```sql
-- 1. Project (if not exists)
CREATE TABLE project (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. 权威提交记录 (defined above with scope constraints)
-- canon_commit table with composite FK for parent scope isolation

-- 3. 分支 HEAD 指针 (defined above with scope constraints)
-- branch_head table with composite FK for HEAD scope isolation

-- 4. 执行控制 (fencing)
CREATE TABLE execution_control (
    project_id UUID NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    execution_version INT NOT NULL DEFAULT 1,
    cancelled_at TIMESTAMPTZ,
    PRIMARY KEY (project_id, branch_name)
);

-- UNIQUE constraint for (project_id, commit_id) - MUST exist before composite FKs
CREATE UNIQUE INDEX idx_commit_project_identity ON canon_commit(project_id, commit_id);

-- 5. 权威事件流
CREATE TABLE canon_event (
    event_id UUID PRIMARY KEY,
    commit_id UUID NOT NULL,
    project_id UUID NOT NULL,  -- Denormalized for scope verification
    event_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    event_data JSONB NOT NULL,
    sequence_number INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- NOW add scope isolation FK (references idx_commit_project_identity UNIQUE index)
ALTER TABLE canon_event
    ADD CONSTRAINT fk_event_commit_scope
    FOREIGN KEY (project_id, commit_id) 
    REFERENCES canon_commit(project_id, commit_id);

CREATE INDEX idx_event_commit ON canon_event(commit_id, sequence_number);

-- 6. 原始正文（如适用，P2最小可选）
CREATE TABLE artifact_content (
    artifact_id UUID PRIMARY KEY,
    commit_id UUID NOT NULL,
    project_id UUID NOT NULL,  -- Denormalized for scope verification
    raw_text TEXT NOT NULL,
    raw_text_hash VARCHAR(64) NOT NULL,
    canonical_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- NOW add scope isolation FK (references idx_commit_project_identity UNIQUE index)
ALTER TABLE artifact_content
    ADD CONSTRAINT fk_artifact_commit_scope
    FOREIGN KEY (project_id, commit_id)
    REFERENCES canon_commit(project_id, commit_id);
```

**可重建的投影** (可从事件流重建，允许延迟/失败重试):
- 当前状态快照 (latest entity states)
- 全文搜索索引
- 统计聚合
- 缓存

**恢复流程**:
```python
async def recover_commit(commit_id: UUID) -> bool:
    """
    验证提交完整性并重建投影 (V2-009 范围)
    
    V2-009 恢复能力:
    - ✓ 提交记录和 ChangeSet
    - ✓ 事件流
    - ✓ 幂等键和 payload hash
    - ✓ Permit 引用 (字符串)
    - ✗ Policy binding 详情 (V2-010+)
    - ✗ Permit evidence 详情 (V2-010+)
    
    V2-010+ 将添加 commit_policy_binding 和 commit_permit_evidence 表
    """
    # 1. 读取提交记录
    commit = await load_commit(commit_id)
    
    # 2. 验证 ChangeSet hash
    assert canonical_hash(commit.changeset) == commit.payload_hash
    
    # 3. 验证事件流完整
    events = await load_events(commit_id)
    assert events_match_changeset(events, commit.changeset)
    
    # 4. 验证 permit 引用存在 (V2-009: 仅字符串引用)
    assert commit.permit_ref is not None
    # Note: permit 证据详情由 V2-010 commit_permit_evidence 表提供
    
    # 5. 重建投影（幂等）
    await rebuild_projections_from_events(events)
    
    return True
```

**V2-009 不包含**:
- `commit_policy_binding`: 政策版本绑定 (V2-010)
- `commit_permit_evidence`: 许可检查快照 (V2-010)

**V2-009 提供**:
- 提交幂等性和收据恢复
- 事件流完整性
- Permit 引用 (字符串，用于外部查询)
- 基础投影重建

**保留期限**:
- 权威数据: 永久保留（除非项目删除）
- Permit 引用: 永久保留 (V2-009)
- Permit 证据快照: V2-010+ 添加
- 原始正文: 永久保留
- 投影: 可按需重建，无固定期限

## Consequences

### Positive

- Root 唯一性通过数据库约束保证，无竞争
- 短事务边界清晰，CAS 防止并发冲突
- 幂等性支持安全重试
- Commit-Wins 语义明确，fencing 防止过期提交
- 恢复证据闭包完整，支持审计和灾难恢复

### Negative

- SERIALIZABLE 隔离级别可能增加事务重试
- 执行版本需要客户端正确传递
- 取消与提交的竞争条件需要清晰文档

### Risks

- SERIALIZABLE 隔离级别在高并发下可能导致事务重试 (SQLSTATE 40001)
- Fencing token 管理需要客户端正确传递 execution_version
- 大型 ChangeSet 可能导致事务过长
- 复合外键需要对应的 UNIQUE 索引支持

### Mitigation

- 实现事务重试逻辑: 捕获 SQLSTATE 40001，使用相同 idempotency_key 重试
- 监控事务冲突率，如过高考虑 READ COMMITTED + 显式锁
- 提供客户端 SDK 封装执行版本管理
- 限制单次提交的 ChangeSet 大小（如最多 1000 个操作）
- 为复合外键创建必要的支持索引

## Verification

V2-009/V2-010 acceptance criteria 必须包含:

1. **Root 唯一性**: 并发创建同一 project/branch 的 root，只有一个成功
2. **作用域隔离**: 跨 project 或跨 branch 的 parent 引用被数据库拒绝
3. **CAS 正确性**: 并发提交基于相同 parent，只有一个成功
4. **幂等性**: 网络超时重试返回原收据
5. **冲突检测**: 相同 key 不同 payload 报告冲突
6. **取消 fencing**: 已取消的执行（execution_version 过期）无法提交
7. **Commit-Wins**: 已成功提交后的取消无效
8. **事务回滚**: 事务失败不留下半提交记录
9. **SERIALIZABLE 重试**: 正确处理 40001 错误并保持幂等性

## References

- 03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §3, §4, §9
- ADR-005: Canonical Hash (幂等键 hash 依赖)
- [PostgreSQL SERIALIZABLE Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [Fencing Tokens in Distributed Systems](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
