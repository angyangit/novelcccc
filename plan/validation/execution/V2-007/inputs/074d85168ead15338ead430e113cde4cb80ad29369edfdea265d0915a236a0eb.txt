# ADR-003 — Event Occurrence 与 Promise 时序语义

**状态**: ACCEPTED

**关联任务**: V2-007

**责任角色**: domain-maintainer

**决策权威**: ARCHITECTURE DECISION

**Machine ADR Status**: ACCEPTED

**日期**: 2026-10-14

**首次适用**: Plan v1.3.1

---

## 问题与依据

### 触发场景

V2-007 (Event Timeline Promise Core) 需要实现"同章多事件与插叙的时间顺序可区分"和"Promise 有承诺兑现窗口和生命周期"，但当前领域模型缺少必要的语义基础：

1. **Event 语义未定义**：
   - V2-061 已创建 `PlannedAction.occurred_event_ref: str | None`，但 Event 本身的语义、occurrence 定义、immutability 尚未建立
   - 无法区分"事件发生"与"章节叙述事件"
   - 无法表达插叙、回忆、未来预告的时间关系

2. **Promise 语义未定义**：
   - Promise 是小说叙事承诺（伏笔、读者预期、剧情承诺），不是 Character Goal
   - Promise 与 Event 的关系未明确（1:1, 1:N, N:1, N:N）
   - Fulfillment 判断标准不清晰

3. **时序模型缺失**：
   - 需要区分 story_time（小说世界时间）、narrative_time（章节呈现顺序）、system_time（系统记录时间）
   - 需要支持精确时间、时间区间、相对顺序
   - 需要支持插叙：事件在故事时间上发生于过去，但在叙述上晚于主线

4. **Canon 集成未明确**：
   - Event occurrence 的 authority 归属未定
   - Promise fulfillment 的 truth authority 未定
   - Idempotency 和 replay safety 未保证

### 现有规范

- **plan/03 §1**：要求 P1 实现 Event/Timeline/Promise，Event 身份与 occurrence 在 V2-007 决定
- **plan/03 §3**：Canon 唯一提交协议，不得引入第二真相存储
- **V2-061 Contract**: 明确 `PlannedAction.occurred_event_ref` 是引用，occurrence authority 属于 V2-007
- **ADR-002**: 建立了 BASE/DERIVED/CACHE 分类，为 ADR-003 提供了模式参考
- **历史归档**: plan/archive/gptdoc/ANovel_V2_Narrative_Domain_Spec_v1.0 提供了设计参考（§28-35），但需要基于 P1 真实需求裁剪

### 需要决定的边界

1. Event 的身份、occurrence 语义、immutability
2. Promise 的身份、类型、生命周期
3. Event ↔ Promise 关系模型（基数、fulfillment 判断）
4. 时间模型（story_time 表达方式）
5. Timeline 语义（有序 Event 集合，支持插叙）
6. Hard invariants vs soft quality policies
7. Canon ownership 和 idempotency 保证

---

## 决定

### 核心原则

1. **Event 和 Promise 是叙事语义概念**，不是通用任务调度系统
2. **Event occurrence 属于 Canon truth authority**，immutable by default
3. **Promise 是叙事层承诺**，不是 Character Goal（Goal 已在 V2-061 定义）
4. **支持非线性叙事**：插叙、回忆、预告的时间关系可区分
5. **Idempotency 和 replay safety**：重放不产生重复 occurrence，重试不双重兑现
6. **Hard invariants 与 soft policies 分离**：兑现节奏评估属于 quality 层，不硬编码进 domain schema

---

### 决策 A：Event Occurrence 语义

#### Event 定义

```python
@dataclass(frozen=True)
class Event:
    """
    小说世界中已发生事实的权威表示。
    
    BASE fields (all persisted):
        event_id: 唯一稳定标识符 (UUID v4 format)
        project_id: 项目隔离边界
        event_type: 事件类型标识符
        story_time: 事件在小说世界中的发生时间
        participants: 参与实体列表
        occurrence_chapter: 事件首次被叙述的章节引用（可选）
        description: 人类可读描述
        created_at: Canon 提交时间（system_time）
        authority: 权威来源标识
        provenance: 结构化出处元数据
    
    Invariants:
        - event_id 必须 UUID v4 format
        - Event occurrence immutable（修正通过 Retcon，V2-007 不实现）
        - story_time 一旦确定不可修改（除非 Retcon）
        - participants 引用的 EntityId 必须存在于同一 project
    """
    event_id: EventId  # NewType("EventId", str)
    project_id: ProjectId
    event_type: str
    story_time: StoryTime
    participants: list[EntityId]
    occurrence_chapter: str | None
    description: str
    created_at: datetime
    authority: str
    provenance: dict[str, str]
```

#### Story Time 模型

支持三种时间表达：

```python
@dataclass(frozen=True)
class PreciseTime:
    """精确时间点（如已知具体日期时间）"""
    timestamp: str  # ISO 8601 format or story-world calendar
    precision: Literal["year", "month", "day", "hour", "minute"]

@dataclass(frozen=True)
class IntervalTime:
    """时间区间（如"春天"、"三个月内"）"""
    earliest: str
    latest: str
    description: str  # "spring 2013", "within 3 months"

@dataclass(frozen=True)
class RelativeTime:
    """相对时间（相对于另一事件或叙述点）"""
    anchor_event_id: EventId | None
    offset_description: str  # "3 days after X", "before story begins"
    relative_order: Literal["before", "after", "during", "concurrent"]

StoryTime = PreciseTime | IntervalTime | RelativeTime
```

#### 关键语义

1. **Occurrence vs Disclosure**：
   - **Occurrence**：事件在小说世界时间（story_time）发生
   - **Disclosure**：事件在叙述中被揭示（occurrence_chapter）
   - 插叙场景：Event.story_time = "10 years ago", occurrence_chapter = 80

2. **Immutability**：
   - Event 一旦提交到 Canon，默认 immutable
   - 修正通过 Retcon Event（V2-007 不实现，延期到后续任务）

3. **Authority**：
   - Event occurrence 的唯一 truth authority = Canon
   - PlannedAction.occurred_event_ref 是引用，不是 occurrence authority

---

### 决策 B：Promise 语义

#### Promise 定义

```python
@dataclass(frozen=True)
class Promise:
    """
    叙事层面对读者的承诺（伏笔、预期、剧情承诺）。
    
    BASE fields (all persisted):
        promise_id: 唯一稳定标识符 (UUID v4 format)
        project_id: 项目隔离边界
        promise_type: 承诺类型（枚举或扩展标识符）
        opened_at_chapter: 承诺建立的章节引用
        target_entities: 相关实体（可选）
        target_window: 期望兑现的时间窗口（story_time，可选）
        terminal_disposition: 明确的不可逆终态标记（FAILED | ABANDONED | None）
        description: 人类可读承诺描述
        created_at: Canon 提交时间
        authority: 权威来源标识
        provenance: 结构化出处元数据
    
    Invariants:
        - promise_id 必须 UUID v4 format
        - terminal_disposition = FAILED/ABANDONED 时不可回退到 None
        - terminal_disposition = FAILED/ABANDONED 与 PRIMARY/COMPLETE fulfillment Link 互斥
        - 已存在 PRIMARY/COMPLETE Link 时不允许设置 terminal_disposition = FAILED/ABANDONED
        - terminal_disposition = FAILED/ABANDONED 时不允许新增 PRIMARY/COMPLETE Link
        - target_entities 引用的 EntityId 必须存在于同一 project
    
    Status Authority:
        - terminal_disposition (BASE): 明确的不可逆终态由 Canon 持久化
        - status (DERIVED): 通过显式纯函数从 terminal_disposition + PromiseFulfillmentLink 推导
        - 避免双重真相：active 状态 (OPEN/FULFILLED) 由 Link 集合推导，不单独持久化
        - Promise dataclass 本身不包含 status 字段或 @property，避免污染 pure domain object
    """
    promise_id: PromiseId  # NewType("PromiseId", str)
    project_id: ProjectId
    promise_type: str
    opened_at_chapter: str
    target_entities: list[EntityId]
    target_window: StoryTime | None
    terminal_disposition: Literal["FAILED", "ABANDONED"] | None
    description: str
    created_at: datetime
    authority: str
    provenance: dict[str, str]


def derive_promise_status(
    promise: Promise,
    fulfillment_links: Sequence[PromiseFulfillmentLink],
) -> PromiseStatus:
    """
    纯函数推导 Promise 当前状态。
    
    V2-007 pure-domain 要求：
    - 不查询外部 Link store / repository / database
    - 调用方显式传入相关 Links
    - 确定性推导，无副作用
    
    推导规则：
    1. 如果 terminal_disposition = FAILED → PromiseStatus.FAILED
    2. 如果 terminal_disposition = ABANDONED → PromiseStatus.ABANDONED
    3. 如果 terminal_disposition = None：
       - 存在至少一个 PRIMARY/COMPLETE Link → PromiseStatus.FULFILLED
       - 否则 → PromiseStatus.OPEN
    
    参数：
        promise: Promise domain object
        fulfillment_links: 与该 Promise 相关的所有 PromiseFulfillmentLink
    
    返回：
        PromiseStatus (OPEN / FULFILLED / FAILED / ABANDONED)
    """
    if promise.terminal_disposition == "FAILED":
        return PromiseStatus.FAILED
    if promise.terminal_disposition == "ABANDONED":
        return PromiseStatus.ABANDONED
    
    # Active 状态：从 Link 集合推导
    has_completion = any(
        link.contribution_role in [ContributionRole.PRIMARY, ContributionRole.COMPLETE]
        for link in fulfillment_links
        if link.promise_id == promise.promise_id
    )
    return PromiseStatus.FULFILLED if has_completion else PromiseStatus.OPEN
```

#### Promise Lifecycle

```python
class PromiseStatus(Enum):
    """
    Promise 生命周期状态（DERIVED，从 terminal_disposition + Link 推导）。
    
    OPEN: 承诺已建立，尚未兑现，仍在活跃追踪中
    FULFILLED: 承诺已完全兑现（存在 PRIMARY/COMPLETE Link）
    FAILED: 承诺在世界内已确定无法兑现
    ABANDONED: 承诺因叙事方向改变而不再追踪
    """
    OPEN = "OPEN"
    FULFILLED = "FULFILLED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"
```

**状态语义澄清**：

| 状态 | 语义层次 | 判断依据 | 示例 | 是否可逆 |
|------|---------|---------|------|---------|
| **OPEN** | Active | 无 terminal_disposition，无 PRIMARY/COMPLETE Link | 复仇承诺刚建立 | 可转 FULFILLED/FAILED/ABANDONED |
| **FULFILLED** | Final (Derived) | 无 terminal_disposition，存在 PRIMARY/COMPLETE Link | 复仇成功，Link 关联复仇事件 | **不可转** FAILED/ABANDONED（互斥终局） |
| **FAILED** | Terminal | terminal_disposition = FAILED，有 world evidence | 角色死亡 → 复仇承诺无法兑现 | 不可逆 |
| **ABANDONED** | Terminal | terminal_disposition = ABANDONED，planning 决策 | 支线被砍，承诺不再追踪 | 不可逆 |

**三种终局互斥原则**：

```
OPEN (无终态标记，无完整兑现证据)
 ├─→ FULFILLED (存在 PRIMARY/COMPLETE 兑现证据)
 ├─→ FAILED (世界内确定无法兑现)
 └─→ ABANDONED (叙事层放弃追踪)
```

**硬约束**：
1. **已 FULFILLED 不可进入 FAILED/ABANDONED**
   - 原因：已有 PRIMARY/COMPLETE Link 证明兑现已发生
   - 不允许用 terminal_disposition 遮掉已存在的 reader-facing 兑现事实
   - 实施：有 PRIMARY/COMPLETE Link 时，禁止设置 terminal_disposition = FAILED/ABANDONED

2. **已 FAILED/ABANDONED 不可进入 FULFILLED**
   - 原因：terminal_disposition 是不可逆终态
   - 不允许在 FAILED/ABANDONED 后新增 PRIMARY/COMPLETE Link
   - 实施：terminal_disposition = FAILED/ABANDONED 时，拒绝新增 PRIMARY/COMPLETE Link

3. **SUPPORTING Link 不受互斥约束**
   - SUPPORTING Link 可作为历史部分兑现证据存在
   - 即使 Promise 进入 FAILED/ABANDONED，已有的 SUPPORTING Link 仍保留
   - 但不能因 SUPPORTING Link 将状态判定为 FULFILLED

4. **FULFILLED 与 ABANDONED 不兼容**（订正）
   - 原 ADR 允许 "FULFILLED → ABANDONED（但不建议）"
   - **现修正为：已 FULFILLED 则互斥 ABANDONED**
   - Reader-facing 承诺一旦兑现，不应事后声明"不再追踪"

**FAILED vs ABANDONED 区分**：

**FAILED（世界内失败）**：
- **定义**：叙事承诺在世界内已确定无法兑现
- **必须条件**：有明确的 world evidence（Event）支撑
- **示例**：
  - Promise: "角色 A 将完成对 B 的复仇"
  - Event: "角色 A 在决战中死亡"
  - Disposition: FAILED（复仇主体消失，承诺世界内不可能兑现）
  
  - Promise: "角色将找到传说中的宝藏"
  - Event: "宝藏被毁灭"
  - Disposition: FAILED（目标物消失，承诺无法兑现）

**ABANDONED（叙事层放弃）**：
- **定义**：叙事方向改变，承诺不再追踪，但世界内并非不可能
- **判断依据**：作者/planning 层决策，不需要 world evidence
- **示例**：
  - Promise: "支线角色 C 与 D 的感情发展"
  - 叙事决策：支线篇幅压缩，不再展开
  - Disposition: ABANDONED（非世界内失败，只是不再讲述）

**与 Character Goal 的三层区分**：

| 层次 | 概念 | 示例：复仇场景 | Authority |
|------|------|--------------|-----------|
| **World state** | Event outcome | 角色 A 死亡（Event） | V2-007 Event |
| **Narrative disposition** | Promise terminal state | "A 将复仇" Promise → FAILED | V2-007 Promise.terminal_disposition |
| **Planning state** | Character Goal status | A 的复仇 Goal → 失败 | V2-061 Character.goals |

**关键区别**：
- **Event FAILED**: 不存在此概念，Event 是不可变事实（"发生" 或 "未发生"）
- **Promise FAILED**: 叙事承诺在世界内确定无法兑现
- **Goal failed**: 角色目标未达成（角色视角的失败）

**说明**：
- **不包含** `REINFORCED`, `DELAYED`, `PARTIAL`：这些属于 soft quality evaluation，不是 hard state
- **FULFILLED** 从 Link 集合推导，不单独持久化（避免双重真相）
- **FAILED** 和 **ABANDONED** 是明确的 terminal disposition，需持久化

#### Promise 与 Character Goal 的区分

| 维度 | Promise (V2-007) | Goal (V2-061) |
|------|------------------|---------------|
| 定义 | 叙事层面对读者的承诺 | 角色内心的目标 |
| 作用域 | 跨角色、全局叙事 | 单个角色 |
| 评估者 | 读者、叙事规划层 | 角色本身 |
| 示例 | "这段感情会发展" | 角色：我要追求她 |
| 权威 | V2-007 | V2-061 |
| 失败语义 | 叙事承诺在世界内无法兑现（FAILED）或叙事层不再追踪（ABANDONED） | 角色目标未达成 |
| 失败依据 | World evidence (Event) 或 planning 决策 | 角色视角的成功/失败判断 |

---

### 决策 C：Event ↔ Promise Fulfillment 模型

采用 **独立建模 + Link 表达关系** 方案（Option C）。

#### Fulfillment Link 定义

```python
@dataclass(frozen=True)
class PromiseFulfillmentLink:
    """
    Promise 与 Event 之间的兑现关系链接。
    
    BASE fields (all persisted):
        link_id: 唯一标识符 (UUID v4 format)
        promise_id: 关联的 Promise
        event_id: 兑现承诺的 Event
        contribution_role: 此事件对承诺兑现的贡献角色
        created_at: 链接建立时间
        authority: 权威来源
        provenance: 出处元数据
    
    Invariants:
        - 同一 (promise_id, event_id) 对不可重复创建（idempotency）
        - promise_id 和 event_id 必须存在于同一 project
        - event_id 必须已提交到 Canon
    """
    link_id: str  # UUID v4
    promise_id: PromiseId
    event_id: EventId
    contribution_role: ContributionRole
    created_at: datetime
    authority: str
    provenance: dict[str, str]

class ContributionRole(Enum):
    """
    Event 对 Promise 兑现的贡献角色。
    
    PRIMARY: 主要兑现事件（如复仇成功）
    SUPPORTING: 支持性事件（如渐进式感情发展中的一次帮助）
    COMPLETE: 单一完整兑现（一个事件即完全兑现承诺）
    """
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    COMPLETE = "COMPLETE"
```

#### Fulfillment 判断逻辑

1. **Promise.status 推导规则**：
   - 如果 `terminal_disposition = FAILED` → `PromiseStatus.FAILED`
   - 如果 `terminal_disposition = ABANDONED` → `PromiseStatus.ABANDONED`
   - 如果 `terminal_disposition = None`：
     - 存在至少一个 `PromiseFulfillmentLink` 其中 `contribution_role = COMPLETE`，或
     - 存在至少一个 `contribution_role = PRIMARY` 的 Link
     - → `PromiseStatus.FULFILLED`
     - 否则 → `PromiseStatus.OPEN`

2. **部分兑现**：
   - 多个 `contribution_role = SUPPORTING` 的 Link
   - Promise.status 仍为 OPEN，直到有 PRIMARY 或 COMPLETE Link

3. **Idempotency Semantics**（V2-007 定义，V2-009 实现）：
   - **V2-007 uniqueness invariant**：相同 `(promise_id, event_id)` 对不可重复存在
   - Duplicate pair 违反 domain uniqueness constraint
   - **V2-009 persistence retry behavior**（future）：
     - 重试相同 Link 创建请求应返回已存在的 Link
     - 不创建新记录，不报错
     - 这是 idempotency 机制实现，不属于 V2-007 pure-domain 范围

4. **Status Authority**：
   - `terminal_disposition` (BASE): 由 Canon 持久化，不可从其他数据推导
   - `status` (DERIVED): 从 `terminal_disposition` + `PromiseFulfillmentLink` 确定性推导
   - 避免双重真相：OPEN/FULFILLED 状态不单独持久化

#### 支持的兑现模式

| 场景 | Event 数量 | Link 配置 | 说明 |
|------|-----------|----------|------|
| 简单兑现 | 1 | 1 COMPLETE | 一个事件完全兑现（如复仇成功） |
| 渐进兑现 | N | N-1 SUPPORTING + 1 PRIMARY | 多事件累计（如感情发展） |
| 一事多诺 | 1 | 多个 Promise 各有 Link | 高潮事件兑现多个承诺 |
| 多事一诺 | N | 指向同一 Promise | 复杂兑现（如多步骤复仇计划） |

---

### 决策 D：Timeline 语义

#### Timeline 定义

```python
@dataclass(frozen=True)
class Timeline:
    """
    有序 Event 集合，支持非线性叙事。
    
    BASE fields (all persisted):
        timeline_id: 唯一标识符
        project_id: 项目隔离边界
        name: Timeline 名称（如 "主线", "角色A回忆线"）
        events: Event ID 列表（确定性 presentation linearization，符合已知 story-time 约束）
        narrative_sequence: Event ID 列表（按 occurrence_chapter 排序，可选）
        created_at: 创建时间
        authority: 权威来源
    
    Invariants:
        - events 中的 Event 必须属于同一 project
        - events 列表按 story_time 的已知可比较关系排序
        - 支持 partial order：当 story_time 无法确定顺序时，保持 planning 层指定排列
        - **重要**：list position between incomparable events is NOT temporal truth
        - narrative_sequence（如存在）按 occurrence_chapter 排序
    """
    timeline_id: str  # UUID v4
    project_id: ProjectId
    name: str
    events: list[EventId]  # deterministic presentation linearization
    narrative_sequence: list[EventId] | None  # occurrence_chapter order
    created_at: datetime
    authority: str
```

#### Timeline 语义

1. **Story Order**：
   - `Timeline.events` 提供确定性 presentation linearization，符合已知 story-time 约束
   - 支持 **partial order**：当两个 Event 的 story_time 无法确定先后关系时，保持 planning 层指定的排列
   - 不要求 total order（全序）
   - **重要**：planning 指定的排列只是 presentation hint，不代表 canonical temporal fact
   - **关键**：list position between incomparable events is NOT temporal truth

2. **Narrative Order**：
   - `Timeline.narrative_sequence` 按叙述顺序（occurrence_chapter）排序
   - 可选字段，用于明确追踪插叙、倒叙

3. **插叙支持**：
   - Event X: story_time="10 years ago", occurrence_chapter=80
   - Event Y: story_time="现在", occurrence_chapter=5
   - Story order: [X, Y]
   - Narrative order: [Y, X]

4. **Ordering 规则（修正）**：
   
   **PreciseTime 比较**：
   - 按 timestamp 直接比较
   - 可建立确定的 BEFORE / AFTER / EQUAL 关系
   
   **IntervalTime 比较**（订正错误规则）：
   - **禁止按 earliest 简单排序**
   - 正确规则：
     ```
     A BEFORE B  iff  A.latest < B.earliest
     A AFTER B   iff  A.earliest > B.latest
     Otherwise        OVERLAP / UNKNOWN
     ```
   - 示例：
     ```
     A = [Jan 1, Dec 31]
     B = [Jun 1, Jun 2]
     
     A.earliest < B.earliest  但不能推断 A BEFORE B
     实际：A 与 B OVERLAP（B 完全包含在 A 内）
     ```
   - 无法确定顺序时，不强制排序，保持 partial order
   
   **RelativeTime 比较**：
   - 按 anchor 递归解析（如 anchor 本身可比较）
   - 如 anchor 也是 relative 或 interval，可能仍无法确定
   - 无完整 constraint solver 时，允许 UNKNOWN 关系
   
   **无法比较时的处理**：
   - 保持 planning 层指定的排列作为 **presentation order / tie-break hint**
   - **该顺序不升级为 canonical story-time fact**
   - 不得因 list position 推断 "Event A 在 Event B 之前发生"
   - Timeline query 应支持返回 "partial order" 或 "unknown temporal relation"

5. **不要求完整约束求解**：
   - V2-007 不实现 temporal constraint solver
   - 支持人工/planning 层指定 presentation order
   - 冲突检测属于 quality 层，不阻塞提交
   - Partial order 是合法的 Timeline 状态

---

### 决策 E：Hard Invariants

以下为 **必须由 domain 层强制执行** 的 hard invariants：

1. **Identity Uniqueness**：
   - `Event.event_id` 全局唯一
   - `Promise.promise_id` 全局唯一
   - `PromiseFulfillmentLink` 的 `(promise_id, event_id)` 对唯一

2. **Occurrence Immutability**：
   - Event 提交后，`event_id`, `story_time`, `event_type`, `participants` 不可修改
   - 修正通过 Retcon Event（V2-007 不实现）

3. **Fulfillment Evidence**：
   - `Promise.status = FULFILLED` 当且仅当 `terminal_disposition = None` 且存在至少一个 PRIMARY/COMPLETE Link
   - Link 指向的 Event 必须已提交到 Canon
   - `terminal_disposition = FAILED/ABANDONED` 时，status 不依赖 Link

4. **Project Isolation**：
   - Event, Promise, Link 不可跨 project 引用
   - 所有 EntityId 引用必须属于同一 project

5. **Terminal State Protection**：
   - `Promise.terminal_disposition = FAILED/ABANDONED` 不可回退到 None
   - Terminal disposition 单向：None → {FAILED | ABANDONED}
   - **Mutual Exclusivity**：FULFILLED / FAILED / ABANDONED 是互斥的最终叙事结局
   - **No transitions between final outcomes**：已进入任一终局后不可转换到另一终局
   - PromiseFulfillmentLink 是 immutable relationship，completion evidence 不可撤销
   - 状态转换只能从 OPEN 单向进入三种终局之一：
     ```
     OPEN → FULFILLED (有 PRIMARY/COMPLETE Link，不可再进入 FAILED/ABANDONED)
     OPEN → FAILED (terminal_disposition = FAILED，不可再新增 PRIMARY/COMPLETE Link)
     OPEN → ABANDONED (terminal_disposition = ABANDONED，不可再新增 PRIMARY/COMPLETE Link)
     ```

6. **Reference Integrity**：
   - `PlannedAction.occurred_event_ref` 指向的 Event 必须存在
   - `PromiseFulfillmentLink.event_id` 指向的 Event 必须存在
   - `PromiseFulfillmentLink.promise_id` 指向的 Promise 必须存在

---

### 决策 F：Soft Quality Policies（不在 V2-007 硬编码）

以下评估属于 **quality/planning 层**，不作为 domain invariant：

1. **Promise 兑现节奏**：
   - "Promise 应在 N 章内兑现"
   - "高潮章节应兑现多个 Promise"
   - 由 planning/quality 层评估打分，不阻塞提交

2. **Event 频率评估**：
   - "章节应包含合理数量事件"
   - 属于 pacing 评估，不是 hard constraint

3. **Promise 类型平衡**：
   - "不同类型 Promise 应均衡分布"
   - 属于叙事质量评估

4. **Fulfillment 合理性**：
   - "SUPPORTING Event 是否真正支持 Promise"
   - 由 intelligence/quality 层评估，V2-007 只记录 Link

---

### 决策 G：Canon Ownership 与 Idempotency

#### V2-007 定义语义，Canon Integration 属于 V2-009

**重要边界说明**：
- V2-007 定义 Event/Promise/Link/Timeline 的**领域语义**和 **hard invariants**
- **Persistence 实现**（数据库、CanonCommitService）属于 **V2-009/V2-010**，不在 V2-007 范围
- V2-007 实现应提供 **in-memory domain model** 和 **invariant validation**
- 以下描述的 Canon ownership 是**未来 integration 的语义声明**，不要求 V2-007 实现

#### Event Occurrence Authority（语义声明）

1. **Event Occurrence**：
   - 唯一 truth authority: Canon（未来由 V2-009/V2-010 实现）
   - Event 是 immutable fact，一旦提交不可修改
   - V2-007 定义 Event 语义和 immutability invariant

2. **Promise State**：
   - `terminal_disposition` 唯一 truth authority: Canon（未来实现）
   - `status` 为 DERIVED，从 `terminal_disposition` + Link 推导
   - V2-007 定义推导规则

3. **Fulfillment Link**：
   - Link 是 immutable relationship（建立后不可修改 contribution_role）
   - V2-007 定义 Link 语义和 idempotency invariant

#### Idempotency 保证（语义要求）

1. **Event Commit Idempotency**：
   - 使用稳定 idempotent key（由 workflow 层提供）
   - 相同 key + 相同 payload → 返回原 receipt
   - 相同 key + 不同 payload → 报冲突
   - V2-007 定义 idempotency 语义，V2-009 实现

2. **Promise Fulfillment Idempotency**：
   - `(promise_id, event_id)` 对作为 natural key
   - 重复创建相同 Link → 返回已存在 Link，不创建新记录
   - V2-007 定义 uniqueness invariant

3. **Replay Safety**：
   - Event 重放不产生重复 occurrence（由 idempotent key 保证）
   - Promise fulfillment 重试不双重兑现（由 Link uniqueness 保证）

4. **Deterministic Derived State**：
   - `Promise.status` 可从 `terminal_disposition` + Link 集合确定性推导
   - Timeline 顺序可从 Event.story_time 关系重建（支持 partial order）

---

## 拒绝的备选方案

### Option A：Promise 直接绑定单个 Event

```text
Promise.fulfillment_event_ref → EventId
```

**拒绝理由**：
- 无法表达渐进式兑现（多事件累计）
- 无法表达一事件兑现多承诺
- Promise 必须预知具体事件，缺乏灵活性
- 不符合真实小说叙事模式

---

### Option B：Promise 绑定 Outcome Condition

```text
Promise.outcome_condition: StructuredCondition
Event.outcomes: StructuredOutcome
自动匹配评估 fulfillment
```

**拒绝理由**：
- `outcome_condition` 结构化复杂，容易退化为自由文本
- 自动匹配需要复杂推理引擎，超出 P1 范围
- `fulfillment_degree: 0.0~1.0` 评分属于 soft policy，不应是 hard state
- 过度设计，不符合"保持简单"原则

---

### Option C（被接受）：独立建模 + Link

**接受理由**：
- Event 和 Promise 独立建模，各有清晰语义
- Link 表达 N:N 关系，灵活支持所有兑现模式
- Contribution_role 语义明确（3 个枚举值）
- 支持插叙：Event.story_time 独立于 occurrence_chapter
- 符合 Canon 架构：Event 是 fact，Link 是 relationship
- 实现简单，可测试

---

### 历史归档方案的裁剪

**历史归档建议**（plan/archive/gptdoc NARRATIVE_DOMAIN_SPEC.md §28-35）：

```text
Event 字段: id, event_type, occurred_at, participants, location,
           preconditions, actions, outcomes, causes, effects, evidence, authority

Promise Lifecycle: OPEN | REINFORCED | DELAYED | PARTIAL | PAID | BROKEN | 
                   ABANDONED | SUPERSEDED
```

**本 ADR 裁剪**：
- **Event 字段减少**：去除 `preconditions`, `causes`, `effects`（属于高级因果推理，延期到后续任务）
- **Promise Lifecycle 简化**：去除 `REINFORCED`, `DELAYED`, `PARTIAL`（属于 soft policy，不是 hard state）
- **不实现 Mystery/Clue 系统**（延期到 P3/P4 planning 模块）
- **不实现 Temporal Constraint Solver**（V2-007 只要求"可区分"，不要求自动求解）

**裁剪理由**：
- V2-007 目标：同章多事件与插叙的时间顺序可区分 + Promise 有兑现窗口和生命周期
- 不预先实现 P10/P11 高级推理能力
- 保持 P1 domain model 简单、可验证

---

## 影响与验证

### 对 V2-061 的影响

1. **PlannedAction.occurred_event_ref 语义明确**：
   - 该字段指向 V2-007 定义的 Event.event_id
   - V2-061 不拥有 occurrence authority，只持有引用
   - Occurrence 判断必须查询 V2-007 Event 是否存在

2. **兼容性**：
   - V2-061 无需修改（occurred_event_ref 已是 str | None）
   - V2-007 实现后，该引用可被验证

### 对 V2-005/V2-006 的影响

1. **Entity 引用**：
   - Event.participants: list[EntityId] 使用 V2-005 EntityId
   - Promise.target_entities: list[EntityId] 使用 V2-005 EntityId
   - 必须遵守 project isolation

2. **无 Schema 变更**：
   - V2-005/V2-006 domain model 不需修改

### 对 Canon (V2-009/V2-010) 的影响

**重要说明**：以下描述的是 **未来 Canon integration 的语义要求**，不属于 V2-007 实现范围。

1. **Canon Commit 协议扩展**（V2-009 实现）：
   - 需支持 Event 类型提交
   - 需支持 Promise 类型提交
   - 需支持 PromiseFulfillmentLink 类型提交

2. **Idempotency Key**（V2-009 实现）：
   - Event 使用 workflow 层提供的稳定 key
   - Link 使用 `(promise_id, event_id)` 作为 natural key

3. **V2-007 职责边界**：
   - V2-007 定义 Event/Promise/Link 的领域语义和 hard invariants
   - V2-007 提供 in-memory domain model 和 validation
   - V2-007 不实现 persistence、不依赖 CanonCommitService

### Schema 影响

**Schema 设计边界**（修正）：

以下 schema 文件 **不属于 V2-007 当前强制交付物**，除非正式更新 `plan/machine/implementation-backlog.yaml` 的 `artifacts` 列表：

- `specs/schemas/event.schema.json`
- `specs/schemas/promise.schema.json`
- `specs/schemas/promise-fulfillment-link.schema.json`
- `specs/schemas/timeline.schema.json`

**当前决策**：
- Schema artifacts = **DEFER**（延后到 schema contract formalization 任务）
- V2-007 定义 domain semantics，不强制要求 JSON Schema 输出
- 如需 schema validation，应作为独立任务或 V2-009 persistence layer 的一部分

**如实施 schema**，设计原则：
- 仅包含 BASE 字段（遵循 ADR-002 原则）
- `additionalProperties: false`
- UUID v4 format validation for all IDs

### 代码影响

**V2-007 authoritative artifacts**（根据 `plan/machine/implementation-backlog.yaml`）：
- `src/anovel/domain/events.py`（复数形式）
- `src/anovel/domain/promises.py`（复数形式）
- `tests/contract/test_v2_007.py`

**实现约束**：
- `test_v2_007.py` **必须存在**作为 authoritative acceptance contract
- 可增加辅助测试文件（如 `test_v2_007_event.py`, `test_v2_007_promise.py` 等），但**不得替代** `test_v2_007.py`
- Additional test files must not replace the authoritative artifact
- 如需拆分测试，`test_v2_007.py` 应至少包含核心 acceptance scenarios 或作为测试套件入口

**实现建议**（可在实现时调整）：
- `events.py` 可包含 Event, StoryTime, Timeline 相关定义
- `promises.py` 可包含 Promise, PromiseFulfillmentLink 相关定义
- 如需拆分模块（如 `event.py`, `timeline.py`, `promise.py`, `fulfillment.py`），须保持 `events.py` 和 `promises.py` 作为公开入口模块，或先走 governance 变更流程更新 `implementation-backlog.yaml`

### 数据库影响（V2-009 实现时）

**预期新表**（Schema 设计属于 V2-009）：
- `events`
- `promises`
- `promise_fulfillment_links`
- `timelines`
- `timeline_events` (junction table)

**不在 ADR-003 范围**：
- 具体 column types
- Indexes
- Migration scripts

### 验收影响

**AT-V2-007 必须验证**：
1. 同章多事件时间顺序可区分
2. 插叙场景：story_time ≠ occurrence_chapter
3. Promise 创建、兑现、状态转换
4. PromiseFulfillmentLink 唯一性
5. Event occurrence idempotency
6. Project isolation

### 迁移要求

**P1 无需迁移**：
- 当前无生产数据
- V2-007 是新增能力，不影响已有 V2-005/V2-006/V2-061 数据

---

## 生效与替代

### 生效条件

1. **ADR-003 状态 = ACCEPTED**
2. **登记到 plan/machine/decision-register.yaml**
3. **V2-007 实现前置条件满足**

### 不替代其他 ADR

ADR-003 是独立决策，不替代 ADR-001/ADR-002。

### Machine 登记更新

```yaml
- id: ADR-003
  title: Event occurrence 与 Promise 时序
  status: ACCEPTED
  owner_role: domain-maintainer
  related_tasks:
  - V2-007
  decision_due_task: V2-007
  timing: before_interface_implementation
  decision_record: validation/execution/V2-007/adr-003-decision.yaml
  verification_refs: []
```

**说明**：
- `decision_record` 指向 decision evidence file（`validation/execution/V2-007/adr-003-decision.yaml`）
- Decision evidence 再通过 `artifacts` 字段引用 ADR 正文（`decisions/ADR-003_EVENT_PROMISE_TEMPORAL_SEMANTICS.md`）
- 这是统一的 provenance 结构

### V2-007 Implementation Constraints

V2-007 实现必须：
1. 严格遵循 ADR-003 定义的 Event/Promise/Link/Timeline 语义
2. 实现所有 hard invariants 验证
3. 不硬编码 soft quality policies
4. 提供 in-memory domain model（不实现 persistence）
5. 不依赖 CanonCommitService（Canon integration 属于 V2-009）
6. 保证 idempotency 和 replay safety 的**语义定义**（实际 idempotency 机制由 V2-009 实现）
7. 支持插叙场景测试（story_time vs occurrence_chapter）
8. Promise.status 必须从 terminal_disposition + Link 推导，不单独持久化

---

## 后果

### 积极后果

1. **领域模型清晰**：
   - Event/Promise 语义明确，不与 Goal 混淆
   - 时间模型支持非线性叙事

2. **架构边界明确**：
   - Event occurrence authority = Canon
   - Promise ≠ Character Goal（层次清晰）
   - Hard invariants vs soft policies 分离

3. **实现可行**：
   - 模型简单，P1 可实现
   - 不预先实现 P10 高级能力
   - 测试可验证

4. **未来扩展友好**：
   - Retcon Event 可在后续任务实现
   - Causality graph 可作为 Event 扩展
   - Mystery/Clue 可作为 Promise 特殊类型
   - Temporal constraint solver 可在 planning 层实现

### 消极后果

1. **需要额外 Link 表**：
   - PromiseFulfillmentLink 增加存储复杂度
   - 可接受：换取灵活性和清晰语义

2. **StoryTime 多态复杂性**：
   - PreciseTime | IntervalTime | RelativeTime 需要 union type 处理
   - 可接受：符合真实小说叙事需求

### 风险

1. **如未来需要 Retcon**：
   - ADR-003 明确 Event immutable by default
   - Retcon 通过独立 ADR 定义
   - 不阻塞当前决策

2. **如需要完整 temporal reasoning**：
   - ADR-003 支持基础时间顺序表达
   - 高级约束求解属于 planning 层
   - 不阻塞 V2-007 验收

---

## 验证要求

### 单元测试（V2-007 pure-domain 范围）

```python
def test_event_immutability():
    """Event 是 frozen dataclass，不可修改"""
    event = Event(...)
    with pytest.raises(FrozenInstanceError):
        event.story_time = ...

def test_promise_status_derivation():
    """Promise.status 从 terminal_disposition + Link 纯函数推导"""
    promise = Promise(..., terminal_disposition=None)
    
    # 无 Link 时 → OPEN
    links_empty = []
    assert derive_promise_status(promise, links_empty) == PromiseStatus.OPEN
    
    # 有 SUPPORTING Link → 仍为 OPEN
    links_supporting = [
        PromiseFulfillmentLink(promise_id=promise.promise_id, contribution_role=ContributionRole.SUPPORTING, ...)
    ]
    assert derive_promise_status(promise, links_supporting) == PromiseStatus.OPEN
    
    # 有 PRIMARY Link → FULFILLED
    links_primary = [
        PromiseFulfillmentLink(promise_id=promise.promise_id, contribution_role=ContributionRole.PRIMARY, ...)
    ]
    assert derive_promise_status(promise, links_primary) == PromiseStatus.FULFILLED

def test_terminal_disposition_priority_over_links():
    """Terminal disposition 存在时，status 不依赖 Links"""
    # 注意：这些测试 Promise 对象构造时应无 Links
    # FAILED/ABANDONED + PRIMARY/COMPLETE Link 组合是非法状态，
    # 应由 invariant validation 在创建时阻止（见 test_terminal_exclusivity_invariant）
    
    promise_failed = Promise(..., terminal_disposition="FAILED")
    assert derive_promise_status(promise_failed, []) == PromiseStatus.FAILED
    
    promise_abandoned = Promise(..., terminal_disposition="ABANDONED")
    assert derive_promise_status(promise_abandoned, []) == PromiseStatus.ABANDONED
    
    # 即使有 SUPPORTING Link，terminal disposition 仍优先
    supporting_links = [
        PromiseFulfillmentLink(
            promise_id=promise_failed.promise_id,
            contribution_role=ContributionRole.SUPPORTING,
            ...
        )
    ]
    assert derive_promise_status(promise_failed, supporting_links) == PromiseStatus.FAILED

def test_fulfillment_link_uniqueness_invariant():
    """相同 (promise_id, event_id) 对不可重复（idempotency 语义）"""
    link1 = PromiseFulfillmentLink(
        link_id="link_123",
        promise_id="p1",
        event_id="e1",
        contribution_role=ContributionRole.PRIMARY,
        ...
    )
    
    # V2-007 验证：duplicate pair 违反 uniqueness invariant
    # 真正的 idempotency retry 机制由 V2-009 persistence 实现
    with pytest.raises(ValueError, match="duplicate.*promise_id.*event_id"):
        validate_link_uniqueness([link1, link1])

def test_project_isolation():
    """Event/Promise 不可跨 project 引用"""
    event = Event(
        project_id="proj1",
        participants=[EntityId("entity_from_proj2")],
        ...
    )
    with pytest.raises(ValueError, match="project isolation"):
        validate_project_isolation(event)

def test_story_time_vs_occurrence_chapter():
    """插叙：story_time 早于主线，occurrence_chapter 晚于主线"""
    flashback = Event(
        event_id="e1",
        story_time=PreciseTime(timestamp="2010-01-01", precision="day"),
        occurrence_chapter="ch80",
        ...
    )
    mainline = Event(
        event_id="e2",
        story_time=PreciseTime(timestamp="2020-01-01", precision="day"),
        occurrence_chapter="ch05",
        ...
    )
    
    # Story order (按 story_time)
    story_order = sort_events_by_story_time([flashback, mainline])
    assert story_order == [flashback, mainline]
    
    # Narrative order (按 occurrence_chapter)
    narrative_order = sort_events_by_occurrence_chapter([flashback, mainline])
    assert narrative_order == [mainline, flashback]

def test_terminal_exclusivity_invariant():
    """FULFILLED 与 FAILED/ABANDONED 互斥"""
    promise = Promise(promise_id="p1", terminal_disposition=None, ...)
    primary_link = PromiseFulfillmentLink(
        promise_id="p1",
        event_id="e1",
        contribution_role=ContributionRole.PRIMARY,
        ...
    )
    
    # 已有 PRIMARY link → 不允许设置 terminal_disposition
    with pytest.raises(ValueError, match="cannot set terminal_disposition.*already fulfilled"):
        validate_terminal_exclusivity(promise, [primary_link], new_disposition="FAILED")
    
    # 反之：已 FAILED → 不允许新增 PRIMARY link
    promise_failed = Promise(promise_id="p2", terminal_disposition="FAILED", ...)
    new_primary_link = PromiseFulfillmentLink(
        promise_id="p2",
        contribution_role=ContributionRole.PRIMARY,
        ...
    )
    with pytest.raises(ValueError, match="cannot add PRIMARY.*already terminal"):
        validate_terminal_exclusivity(promise_failed, [], new_link=new_primary_link)
```

### Contract 测试（V2-007 domain semantics）

```python
def test_v2_061_occurred_event_ref_integration():
    """PlannedAction.occurred_event_ref 指向 V2-007 Event（引用语义）"""
    # V2-007 只验证 reference semantics，不验证 persistence
    event = Event(event_id="evt_123", ...)
    planned_action = PlannedAction(
        ...,
        occurred_event_ref="evt_123"
    )
    
    # 验证引用格式
    assert is_valid_event_id(planned_action.occurred_event_ref)
    assert planned_action.occurred_event_ref == event.event_id
    
def test_gradual_promise_fulfillment():
    """渐进式兑现：多 SUPPORTING + 1 PRIMARY"""
    promise = Promise(promise_id="p1", terminal_disposition=None, ...)
    
    # 第一个支持事件
    event1 = Event(event_id="e1", ...)
    link1 = PromiseFulfillmentLink(
        promise_id="p1",
        event_id="e1",
        contribution_role=ContributionRole.SUPPORTING,
        ...
    )
    # Promise 仍为 OPEN
    assert derive_promise_status(promise, [link1]) == PromiseStatus.OPEN
    
    # 第二个支持事件
    event2 = Event(event_id="e2", ...)
    link2 = PromiseFulfillmentLink(
        promise_id="p1",
        event_id="e2",
        contribution_role=ContributionRole.SUPPORTING,
        ...
    )
    
    # 最终主要兑现事件
    event3 = Event(event_id="e3", ...)
    link3 = PromiseFulfillmentLink(
        promise_id="p1",
        event_id="e3",
        contribution_role=ContributionRole.PRIMARY,
        ...
    )
    
    # 现在 Promise 应为 FULFILLED（从所有 Links 推导）
    all_links = [link1, link2, link3]
    assert derive_promise_status(promise, all_links) == PromiseStatus.FULFILLED
```

**说明**：
- V2-007 验证 pure-domain semantics（ID/reference rules, invariants, derivation logic）
- Persistence operations (`commit_to_canon`, `create_link` with retry) 属于 V2-009 scope
- Idempotency **语义**由 V2-007 定义，idempotency **机制**由 V2-009 实现

### AT-V2-007 验收场景

1. **AC-1：同章多事件时间顺序**
   - 给定：一章包含 3 个事件
   - 当：事件有明确 story_time
   - 则：可通过 Timeline 查询 story_time 顺序

2. **AC-2：插叙场景**
   - 给定：回忆章节（第 80 章）
   - 当：描述 10 年前事件
   - 则：Event.story_time = "10 years ago", occurrence_chapter = 80
   - 则：Story order ≠ narrative order

3. **AC-3：Promise 生命周期**
   - 给定：新建 Promise（terminal_disposition=None）
   - 当：关联事件发生并创建 PRIMARY Link
   - 则：Promise.status → FULFILLED（从 Link 推导）
   - 给定：Promise 标记为 FAILED
   - 则：terminal_disposition = FAILED，status 不可回退

4. **AC-4：Promise 与 Goal 区分**
   - 给定：角色有 Goal "revenge"
   - 则：Character.goals 包含该 Goal（V2-061）
   - 给定：叙事有 Promise "复仇会成功"
   - 则：独立创建 Promise 对象（V2-007）
   - 则：两者不混淆

---

## 批准前提条件

1. **语义完整性**：Event/Promise/Link/Timeline 语义明确且无歧义
2. **权威边界清晰**：V2-005/V2-006/V2-061/V2-007/Canon 边界明确
3. **Hard/Soft 分离**：Hard invariants 与 soft policies 明确区分
4. **P1 范围合理**：不预先实现 P10 高级能力
5. **V2-007 可实现**：实现约束明确，验收可测试
6. **无语义冲突**：与 ADR-001/ADR-002 及现有 Contract 无冲突

**当前状态**: ACCEPTED — 2026-10-14

---

## 参考

- plan/03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS.md §1, §3
- V2-061 Implementation Contract (occurred_event_ref authority boundary)
- ADR-002 (BASE/DERIVED/CACHE 分类原则)
- plan/archive/gptdoc/ANovel_V2_Narrative_Domain_Spec_v1.0/NARRATIVE_DOMAIN_SPEC.md (§28-35, 历史设计参考)
- V2-007 Task Definition (plan/machine/implementation-backlog.yaml)
