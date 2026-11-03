# V2-018 Development Preparation: Context Compiler Design

**Status:** APPROVED FOR IMPLEMENTATION (Conditional on PR #17 + G-P4)  
**Date:** 2026-11-03  
**ADR-009:** ACCEPTED  
**Owner Authorization:** Granted 2026-11-03

---

## 1. Reusable Interfaces from Existing Code

### A. Canon Snapshot (V2-012) ✅
**Location:** `src/anovel/canon/projection.py`

```python
class CanonProjectionService:
    def project_to_commit(self, project_id: ProjectId, branch: str, 
                         commit_id: CommitId) -> CanonState
    
@dataclass(frozen=True)
class SnapshotData:
    snapshot_id: str
    project_id: str
    commit_id: str  # Canon parent hash
    canon_state: CanonState  # Reconstructed state
```

**Usage in V2-018:** Obtain frozen Canon state snapshot from `chapter_contract.canon_parent`

---

### B. ChapterContract (V2-017) ✅
**Location:** `src/anovel/contracts/models.py`

```python
@dataclass(frozen=True)
class ChapterContract:
    contract_id: str
    canon_parent: str  # Frozen Canon commit hash
    genre_pack_binding: GenrePackBinding
    required_transitions: list[RequiredTransition]
    prohibited_transitions: list[ProhibitedTransition]
    protected_facts: list[ProtectedFact]
    knowledge_boundaries: list[KnowledgeBoundary]
    continuity_constraints: ContinuityConstraint | None
```

**Usage in V2-018:** Primary input defining mandatory constraints and knowledge boundaries

---

### C. GenrePack (V2-013/014) ✅
**Location:** `src/anovel/genre/`

```python
class GenrePackRegistry:
    def get_pack(self, pack_id: str, version: str) -> GenrePackMetadata

class GenreHardPolicyEngine:
    def judge_fact(self, fact: NarrativeFact) -> PolicyJudgment
```

**Usage in V2-018:** Load GenrePack hard policies from `genre_pack_binding.content_hash`

---

### D. Character Knowledge (V2-061) ✅
**Location:** `src/anovel/domain/knowledge.py`

```python
@dataclass(frozen=True)
class CharacterKnowledge:
    entity_id: EntityId
    knowledge: list[tuple[PropositionId, KnowledgeLevel]]
    acquisition_source: AcquisitionSource

class KnowledgeLevel(Enum):
    KNOWN = "KNOWN"
    BELIEVED = "BELIEVED"
    SUSPECTED = "SUSPECTED"
```

**Usage in V2-018:** Extract character known facts for context assembly, enforce knowledge boundaries

---

## 2. New Components for V2-018

### A. Context Models
**New File:** `src/anovel/context/models.py`

```python
"""Context Compiler models for V2-018.

Defines ContextArtifact, ContextItem, and compilation diagnostics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Any

@dataclass(frozen=True)
class ContextItem:
    """Single item in compiled context with provenance and metadata."""
    
    item_id: str  # UUID
    content: str | dict[str, Any]  # Actual context content
    source_type: Literal["canon", "contract", "genre_pack", 
                         "character_knowledge", "retrieval"]
    source_hash: str  # SHA-256 of source content
    scope: str  # project_id
    visibility: Literal["writer", "character", "reader", "reviewer"]
    mandatory: bool  # Cannot be trimmed for budget
    token_count: int
    inclusion_reason: str  # Explainability
    
@dataclass(frozen=True)
class CompilationLog:
    """Records context compilation decisions for auditability."""
    
    total_budget: int
    mandatory_tokens: int
    optional_tokens: int
    output_reserve: int  # Reserved for Writer output + system overhead
    excluded_optional_items: list[tuple[str, str]]  # (item_id, reason)
    token_counting_method: str  # Model-specific (e.g., "cl100k_base", "claude-tokenizer")
    
@dataclass(frozen=True)
class ContextArtifact:
    """Compiled context ready for Writer consumption."""
    
    artifact_id: str
    chapter_contract_id: str
    canon_parent: str  # Frozen Canon commit hash
    genre_pack_hash: str
    created_at: datetime
    
    mandatory_items: list[ContextItem]
    optional_items: list[ContextItem]
    
    compilation_log: CompilationLog

@dataclass(frozen=True)
class ContextCompilationError:
    """Error when context cannot be compiled within constraints."""
    
    error_type: Literal["mandatory_overflow", "scope_violation", 
                       "missing_input"]
    message: str
    mandatory_tokens: int | None = None
    available_budget: int | None = None  # total_budget - output_reserve
    overflow_amount: int | None = None
    suggested_budget: int | None = None
    affected_items: list[str] = field(default_factory=list)
```

---

### B. Context Compiler
**New File:** `src/anovel/context/compiler.py`

```python
"""Context Compiler for V2-018.

Assembles ContextArtifact from ChapterContract, Canon snapshot, GenrePack,
character knowledge, and optional retrieval content.

Key principles:
- Mandatory items never trimmed (FAIL_FAST on overflow)
- Strict knowledge isolation (character/reader/reviewer boundaries)
- Deterministic compilation (no LLM calls, offline reproducible)
- Full provenance tracking for auditability
"""

import uuid
from datetime import datetime
from typing import Any

from ..canon.projection import CanonProjectionService, SnapshotData
from ..contracts.models import ChapterContract
from ..domain.identity import ProjectId
from ..domain.knowledge import CharacterKnowledge
from ..genre.registry import GenrePackRegistry
from .models import (
    ContextArtifact,
    ContextCompilationError,
    ContextItem,
    CompilationLog,
)

# Result type for compilation
CompilationResult = ContextArtifact | ContextCompilationError


class ContextCompiler:
    """Compiles context from frozen inputs for Writer."""
    
    def __init__(
        self,
        canon_projection: CanonProjectionService,
        genre_registry: GenrePackRegistry,
        token_counter: TokenCounter,  # TBD: tokenizer abstraction
    ):
        """Initialize with required services."""
        self.canon_projection = canon_projection
        self.genre_registry = genre_registry
        self.token_counter = token_counter
    
    def compile_context(
        self,
        chapter_contract: ChapterContract,
        project_id: ProjectId,
        branch_name: str,
        previous_chapter_end: dict[str, Any] | None = None,
        optional_retrieval: list[dict[str, Any]] | None = None,
        token_budget: int = 32000,
    ) -> CompilationResult:
        """
        Compile ContextArtifact from frozen inputs.
        
        Args:
            chapter_contract: Compiled contract (from V2-017)
            project_id: Project scope
            branch_name: Branch name for Canon projection
            previous_chapter_end: Actual end state from chapter N-1
            optional_retrieval: Retrieved summaries (can be trimmed)
            token_budget: Maximum total tokens
            
        Returns:
            ContextArtifact if successful
            ContextCompilationError if mandatory overflow or violations
        """
        mandatory_items: list[ContextItem] = []
        
        # 1. Load Canon snapshot
        canon_snapshot = self._load_canon_snapshot(
            project_id, branch_name, chapter_contract.canon_parent
        )
        
        # 2. Assemble mandatory items
        mandatory_items.extend(
            self._assemble_continuity(chapter_contract, previous_chapter_end)
        )
        mandatory_items.extend(
            self._assemble_contract_constraints(chapter_contract)
        )
        mandatory_items.extend(
            self._assemble_character_knowledge(
                chapter_contract, canon_snapshot, project_id
            )
        )
        mandatory_items.extend(
            self._assemble_genre_policies(chapter_contract)
        )
        
        # 3. Check mandatory overflow
        mandatory_tokens = sum(item.token_count for item in mandatory_items)
        if mandatory_tokens > token_budget:
            return ContextCompilationError(
                error_type="mandatory_overflow",
                message=f"Mandatory context ({mandatory_tokens} tokens) exceeds budget ({token_budget} tokens)",
                mandatory_tokens=mandatory_tokens,
                budget=token_budget,
                overflow_amount=mandatory_tokens - token_budget,
                suggested_budget=mandatory_tokens + 8000,  # +25% headroom
                affected_items=[item.item_id for item in mandatory_items],
            )
        
        # 4. Select optional items within remaining budget
        remaining_budget = token_budget - mandatory_tokens
        optional_items, excluded = self._select_optional_items(
            optional_retrieval or [], remaining_budget
        )
        
        # 5. Build artifact
        artifact = ContextArtifact(
            artifact_id=str(uuid.uuid4()),
            chapter_contract_id=chapter_contract.contract_id,
            canon_parent=chapter_contract.canon_parent,
            genre_pack_hash=chapter_contract.genre_pack_binding.content_hash,
            created_at=datetime.now(),
            mandatory_items=mandatory_items,
            optional_items=optional_items,
            compilation_log=CompilationLog(
                total_budget=token_budget,
                mandatory_tokens=mandatory_tokens,
                optional_tokens=sum(item.token_count for item in optional_items),
                excluded_optional_items=excluded,
                token_counting_method="cl100k_base",
            ),
        )
        
        return artifact
    
    def _assemble_continuity(
        self, contract: ChapterContract, previous_end: dict | None
    ) -> list[ContextItem]:
        """Assemble continuity constraint items (mandatory)."""
        # Implementation: extract previous_end_state from contract.continuity_constraints
        pass
    
    def _assemble_contract_constraints(
        self, contract: ChapterContract
    ) -> list[ContextItem]:
        """Assemble contract constraints (mandatory)."""
        # Implementation: convert required/prohibited transitions to ContextItems
        pass
    
    def _assemble_character_knowledge(
        self, contract: ChapterContract, canon_snapshot: SnapshotData,
        project_id: ProjectId
    ) -> list[ContextItem]:
        """Assemble character knowledge with boundaries (mandatory)."""
        # Implementation: query CharacterKnowledge from canon_snapshot,
        # apply knowledge_boundaries filtering
        pass
    
    def _assemble_genre_policies(
        self, contract: ChapterContract
    ) -> list[ContextItem]:
        """Assemble GenrePack hard policies (mandatory)."""
        # Implementation: load GenrePack, extract hard constraints
        pass
    
    def _select_optional_items(
        self, retrieval: list[dict], budget: int, contract: ChapterContract
    ) -> tuple[list[ContextItem], list[tuple[str, str]]]:
        """
        Select optional items within budget using adaptive priority.
        
        Priority factors (per ADR-009 Owner requirement):
        - 因果依赖: Contract required_transitions 直接相关背景
        - 章节需要: Contract 引用但非强制的支持性信息
        - 时间相关性: 前章/近期事件 > 远期历史
        - 信息重要性: 角色核心动机 > 次要细节
        
        Returns: (selected_items, excluded_items_with_reasons)
        """
        # Implementation: adaptive selection based on contract content
        pass
    
    def _load_canon_snapshot(
        self, project_id: ProjectId, branch: str, commit_id: str
    ) -> SnapshotData:
        """Load Canon snapshot for given commit."""
        return self.canon_projection.project_to_commit(
            project_id, branch, commit_id
        )
```

---

### C. Token Counter Abstraction
**New File:** `src/anovel/context/token_counter.py`

```python
"""Token counting abstraction for context budget management."""

from abc import ABC, abstractmethod

class TokenCounter(ABC):
    """Abstract token counter for different tokenizers."""
    
    @property
    @abstractmethod
    def encoding_name(self) -> str:
        """Return encoding name for logging."""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        pass

class CL100kTokenCounter(TokenCounter):
    """OpenAI cl100k_base tokenizer (GPT-4)."""
    
    def __init__(self):
        import tiktoken
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    @property
    def encoding_name(self) -> str:
        return "cl100k_base"
    
    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
```

---

## 3. AT-V2-018 Acceptance Test Design

**New File:** `tests/contract/test_v2_018.py`

```python
"""Acceptance tests for V2-018 Context Compiler.

Test coverage:
1. Mandatory overflow fails explicitly (not silent truncation)
2. Low relevance but mandatory items included
3. Reviewer-only facts excluded from Writer context
4. Future knowledge leak prevented
5. Offline compilation deterministic
"""

import pytest
from datetime import datetime

from src.anovel.context.compiler import ContextCompiler, CompilationResult
from src.anovel.context.models import ContextCompilationError, ContextArtifact
from src.anovel.contracts.models import ChapterContract, ContinuityConstraint
from tests.contract.fixtures import create_test_contract, create_mock_canon_snapshot


class TestMandatoryOverflow:
    """AT-V2-018-1: 预算溢出必需项时明确阻断"""
    
    def test_mandatory_overflow_fails_explicitly(self):
        """Mandatory items exceed budget → ContextCompilationError with overflow details"""
        compiler = create_compiler()
        contract = create_large_contract(mandatory_tokens=35000)
        
        result = compiler.compile_context(
            contract, project_id="test", branch_name="main", token_budget=32000
        )
        
        assert isinstance(result, ContextCompilationError)
        assert result.error_type == "mandatory_overflow"
        assert result.mandatory_tokens == 35000
        assert result.overflow_amount == 3000
        assert result.suggested_budget >= 35000


class TestLowRelevanceMandatory:
    """AT-V2-018-2: 低语义相关但必需的旧事实不被裁剪"""
    
    def test_low_relevance_continuity_included(self):
        """Previous chapter ending with low semantic relevance must be preserved"""
        compiler = create_compiler()
        contract = create_contract_with_continuity(
            previous_end={"scene": "平淡对话，无关键事件"}  # Low relevance
        )
        
        result = compiler.compile_context(contract, project_id="test", 
                                          branch_name="main", token_budget=32000)
        
        assert isinstance(result, ContextArtifact)
        continuity_items = [
            item for item in result.mandatory_items 
            if item.source_type == "canon" and "continuity" in item.inclusion_reason
        ]
        assert len(continuity_items) > 0
        assert any("平淡对话" in str(item.content) for item in continuity_items)


class TestKnowledgeIsolation:
    """AT-V2-018-3: 错项目未来知识无泄漏且每项 inclusion 可解释"""
    
    def test_reviewer_facts_excluded(self):
        """Reviewer-only materials never enter Writer context"""
        compiler = create_compiler()
        contract = create_contract_with_reviewer_notes()
        
        result = compiler.compile_context(contract, project_id="test",
                                          branch_name="main", token_budget=32000)
        
        assert isinstance(result, ContextArtifact)
        all_items = result.mandatory_items + result.optional_items
        assert not any(item.visibility == "reviewer" for item in all_items)
    
    def test_future_chapter_facts_excluded(self):
        """Future chapter facts (chapter_number > current) excluded"""
        compiler = create_compiler()
        contract = create_chapter_3_contract()  # Current chapter = 3
        canon_with_future = create_canon_with_chapter_5_facts()
        
        result = compiler.compile_context(
            contract, project_id="test", branch_name="main",
            token_budget=32000
        )
        
        assert isinstance(result, ContextArtifact)
        # Verify no chapter 4+ facts in context
        for item in result.mandatory_items:
            if item.source_type == "canon":
                assert not contains_future_chapter_facts(item.content, current=3)


class TestOfflineCompilation:
    """AT-V2-018-4: 冻结输入在不调用生成模型时可编译 ContextArtifact"""
    
    def test_deterministic_offline_compilation(self):
        """Same frozen inputs produce identical ContextArtifact without LLM calls"""
        compiler = create_compiler()
        contract = create_test_contract()
        
        # Compile twice with same inputs
        result1 = compiler.compile_context(
            contract, project_id="test", branch_name="main", token_budget=32000
        )
        result2 = compiler.compile_context(
            contract, project_id="test", branch_name="main", token_budget=32000
        )
        
        assert isinstance(result1, ContextArtifact)
        assert isinstance(result2, ContextArtifact)
        
        # artifact_id and created_at differ, but content identical
        assert result1.chapter_contract_id == result2.chapter_contract_id
        assert result1.canon_parent == result2.canon_parent
        assert len(result1.mandatory_items) == len(result2.mandatory_items)
        assert result1.compilation_log.mandatory_tokens == \
               result2.compilation_log.mandatory_tokens


class TestContinuityPriority:
    """AT-V2-018-5: 必要的前章实际末段不被可选检索挤出"""
    
    def test_continuity_not_displaced_by_retrieval(self):
        """Previous chapter ending preserved even with high-relevance retrieval"""
        compiler = create_compiler()
        contract = create_contract_with_continuity(previous_end={"key": "value"})
        
        # Add large optional retrieval
        large_retrieval = [
            {"content": "高相关检索" * 1000, "relevance": 0.95} for _ in range(10)
        ]
        
        result = compiler.compile_context(
            contract, project_id="test", branch_name="main",
            optional_retrieval=large_retrieval, token_budget=32000
        )
        
        assert isinstance(result, ContextArtifact)
        # Continuity in mandatory_items, not displaced
        assert any(
            "continuity" in item.inclusion_reason 
            for item in result.mandatory_items
        )
```

---

## 4. Code Gap Analysis

### Need to Implement (V2-018 IMPLEMENT phase)

**New modules (greenfield):**
1. `src/anovel/context/__init__.py` — Package init
2. `src/anovel/context/models.py` — 160 lines (dataclasses)
3. `src/anovel/context/compiler.py` — 350 lines (core logic)
4. `src/anovel/context/token_counter.py` — 30 lines (abstraction)
5. `tests/contract/test_v2_018.py` — 250 lines (5 test classes)

**Total new code:** ~790 lines

**Reuse from existing code:**
- Canon projection: `CanonProjectionService` (V2-012) ✅
- Contract models: `ChapterContract` (V2-017) ✅
- Character knowledge: `CharacterKnowledge` (V2-061) ✅
- Genre registry: `GenrePackRegistry` (V2-013) ✅

**External dependency:**
- `tiktoken` library for token counting (add to requirements)

---

## 5. Missing Capabilities After V2-018

**To reach first chapter generation, still need:**

1. **V2-019 Model Gateway** — Send ContextArtifact to LLM, receive prose
2. **V2-020 Single Chapter Workflow** — Orchestrate compile → context → generate → extract
3. **V2-021 NarrativeDelta Extractor** — Parse generated prose into structured deltas
4. **V2-022-025 Quality Validators** — Q0-Q3 validation before commit
5. **V2-026 CommitPermit** — Authorize Canon commit based on quality

**Critical path to first chapter:**
V2-018 (Context) → V2-019 (Gateway) → V2-020 (Workflow) → V2-021 (Extractor) → V2-022-026 (Validation)

**Estimated remaining tasks:** 5 tasks, ~2000 lines new code + integration

---

## 6. Implementation Blockers

**Cannot start V2-018 until:**
1. ✅ PR #17 merged (fb5627a → remote)
2. ✅ G-P4 gate VERIFIED
3. ⏳ ADR-009 ACCEPTED (Owner decision on policies)

**No other blockers.** Design complete, reusable interfaces identified, test plan ready.
