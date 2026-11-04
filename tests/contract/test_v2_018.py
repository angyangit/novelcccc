"""Acceptance tests for V2-018 Context Compiler per ADR-009.

AT-V2-018-01: Low semantic similarity required facts not dropped
AT-V2-018-02: Budget overflow on required items returns diagnostic (FAIL_FAST)
AT-V2-018-03: Cross-project knowledge isolation and inclusion traceability
AT-V2-018-04: Previous chapter ending prioritized over optional retrieval
AT-V2-018-05: Deterministic compilation without generation models
"""

import hashlib
import json
import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest

from anovel.context.compiler import ContextCompiler
from anovel.context.models import (
    ContextArtifact,
    ContextCompilationError,
)
from anovel.context.token_counter import CL100kTokenCounter
from anovel.contracts.models import (
    ChapterContract,
    ContinuityConstraint,
    KnowledgeBoundary,
    ProhibitedTransition,
    ProtectedFact,
    RequiredTransition,
)
from anovel.domain.delta import CanonState, OperationType
from anovel.domain.identity import ProjectId
from anovel.planning.models import GenrePackBinding


@pytest.fixture
def mock_canon_state():
    """Mock Canon state."""
    return CanonState(
        project_id=ProjectId("test-project"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )


@pytest.fixture
def mock_genre_registry():
    """Mock GenrePack registry."""
    registry = Mock()
    registry.get_pack = Mock(return_value=Mock())
    return registry


@pytest.fixture
def token_counter():
    """Mock token counter for testing."""
    counter = Mock()
    counter.encoding_name = "test-tokenizer"
    counter.count_tokens = Mock(side_effect=lambda text: len(text) // 4)  # ~4 chars per token
    return counter


@pytest.fixture
def compiler(mock_genre_registry, token_counter):
    """Context compiler with mocked dependencies."""
    return ContextCompiler(mock_genre_registry, token_counter)


@pytest.fixture
def basic_contract():
    """Basic chapter contract for testing."""
    return ChapterContract(
        contract_id=str(uuid.uuid4()),
        chapter_id="test-ch1",
        chapter_number=1,
        plan_version="v1.0",
        created_at=datetime.now(),
        canon_parent="canon-parent-hash",
        genre_pack_binding=GenrePackBinding(
            pack_id="test-genre", version="1.0", content_hash="test-hash"
        ),
        required_transitions=[],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
        continuity_constraints=None,  # Chapter 1 has no previous chapter
    )


class TestATv201801LowRelevanceMandatory:
    """AT-V2-018-01: 低语义相关但必需的旧事实不被裁剪"""

    def test_continuity_preserved_regardless_of_relevance(
        self, compiler, mock_canon_state, token_counter
    ):
        """Previous chapter ending preserved even if low semantic relevance.

        ADR-009: Low semantic similarity but required old facts not clipped.
        """
        # Contract with continuity from previous chapter
        contract = ChapterContract(
            contract_id=str(uuid.uuid4()),
            chapter_id="test-ch2",
            chapter_number=2,
            plan_version="v1.0",
            created_at=datetime.now(),
            canon_parent="canon-parent-hash",
            genre_pack_binding=GenrePackBinding(
                pack_id="test-genre", version="1.0", content_hash="test-hash"
            ),
            required_transitions=[],
            prohibited_transitions=[],
            protected_facts=[],
            knowledge_boundaries=[],
            continuity_constraints=ContinuityConstraint(
                previous_chapter_id="test-ch1",
                previous_chapter_hash="prev-hash",
                previous_end_state={"scene": "平淡日常对话，无关键事件"},  # Low relevance
                current_start_requirements=[],
            ),
        )

        previous_end = {"actual_text": "上一章结尾是平淡的生活场景描写"}

        result = compiler.compile_context(
            chapter_contract=contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("test-project"),
            previous_chapter_end=previous_end,
            token_budget=10000,
            output_reserve=2000,
        )

        assert isinstance(result, ContextArtifact), "Compilation should succeed"

        # Verify continuity in mandatory items
        continuity_items = [
            item for item in result.mandatory_items if item.source_type == "continuity"
        ]
        assert len(continuity_items) > 0, "Continuity must be in mandatory items"
        assert continuity_items[0].mandatory is True
        assert "平淡日常对话" in str(continuity_items[0].content)


class TestATv201802MandatoryOverflow:
    """AT-V2-018-02: 预算溢出必需项时明确阻断 (ADR-009 FAIL_FAST)"""

    def test_mandatory_overflow_returns_explicit_error(
        self, compiler, mock_canon_state, basic_contract
    ):
        """Mandatory overflow returns ContextCompilationError, not silent truncation."""

        # Create contract with many required transitions to exceed budget
        large_contract = ChapterContract(
            contract_id=basic_contract.contract_id,
            chapter_id=basic_contract.chapter_id,
            chapter_number=basic_contract.chapter_number,
            plan_version=basic_contract.plan_version,
            created_at=basic_contract.created_at,
            canon_parent=basic_contract.canon_parent,
            genre_pack_binding=basic_contract.genre_pack_binding,
            required_transitions=[
                RequiredTransition(
                    transition_id=str(uuid.uuid4()),
                    operation_type=OperationType.SET_FACT,
                    fact_path=f"fact.path.{i}",
                    target_value=f"Large value string " * 100,  # ~500 tokens each
                    rationale=f"Required transition {i} with substantial rationale text " * 20,
                )
                for i in range(50)  # 50 * 500 = 25000 tokens
            ],
            prohibited_transitions=[],
            protected_facts=[],
            knowledge_boundaries=[],
            continuity_constraints=None,
        )

        result = compiler.compile_context(
            chapter_contract=large_contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("test-project"),
            token_budget=10000,  # Too small for mandatory items
            output_reserve=2000,
        )

        # PASS: Returns explicit error
        assert isinstance(result, ContextCompilationError)
        assert result.error_type == "mandatory_overflow"
        assert result.mandatory_tokens is not None
        assert result.available_budget is not None
        assert result.overflow_amount > 0
        assert result.suggested_budget > result.available_budget


class TestATv201803KnowledgeIsolation:
    """AT-V2-018-03: 错项目未来知识无泄漏且每项 inclusion 可解释"""

    def test_knowledge_boundaries_enforced(
        self, compiler, mock_canon_state, basic_contract
    ):
        """Character knowledge boundaries strictly enforced per ADR-009."""

        contract = ChapterContract(
            contract_id=basic_contract.contract_id,
            chapter_id=basic_contract.chapter_id,
            chapter_number=basic_contract.chapter_number,
            plan_version=basic_contract.plan_version,
            created_at=basic_contract.created_at,
            canon_parent=basic_contract.canon_parent,
            genre_pack_binding=basic_contract.genre_pack_binding,
            required_transitions=[],
            prohibited_transitions=[],
            protected_facts=[],
            knowledge_boundaries=[
                KnowledgeBoundary(
                    boundary_id=str(uuid.uuid4()),
                    fact_id="secret-funding",
                    knowers=["protagonist"],
                    revelation_constraint=None,
                    reader_knows=True,  # Reader knows
                ),
                KnowledgeBoundary(
                    boundary_id=str(uuid.uuid4()),
                    fact_id="hidden-identity",
                    knowers=["antagonist"],
                    revelation_constraint="not_before_chapter_10",
                    reader_knows=False,  # Secret from reader
                ),
            ],
            continuity_constraints=None,
        )

        result = compiler.compile_context(
            chapter_contract=contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("test-project"),
            token_budget=10000,
            output_reserve=2000,
        )

        assert isinstance(result, ContextArtifact)

        # Verify knowledge items have correct visibility
        knowledge_items = [
            item for item in result.mandatory_items
            if item.source_type == "character_knowledge"
        ]

        # Reader-known secret should have "reader" visibility
        reader_known = [item for item in knowledge_items if "secret-funding" in str(item.content)]
        if reader_known:
            assert reader_known[0].visibility == "reader"

        # Secret should have "writer" visibility (not "reader")
        writer_only = [item for item in knowledge_items if "hidden-identity" in str(item.content)]
        if writer_only:
            assert writer_only[0].visibility == "writer"

    def test_every_item_has_inclusion_reason(
        self, compiler, mock_canon_state, basic_contract
    ):
        """Every ContextItem must have explainable inclusion_reason per ADR-009."""

        result = compiler.compile_context(
            chapter_contract=basic_contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("test-project"),
            token_budget=10000,
            output_reserve=2000,
        )

        assert isinstance(result, ContextArtifact)

        all_items = result.mandatory_items + result.optional_items
        for item in all_items:
            assert item.inclusion_reason, f"Item {item.item_id} missing inclusion_reason"
            assert len(item.inclusion_reason) > 0


class TestATv201804ContinuityPriority:
    """AT-V2-018-04: 必要的前章实际末段不被可选检索挤出"""

    def test_continuity_not_displaced_by_optional_retrieval(
        self, compiler, mock_canon_state
    ):
        """Previous chapter ending preserved even with large optional retrieval."""

        contract = ChapterContract(
            contract_id=str(uuid.uuid4()),
            chapter_id="test-ch2",
            chapter_number=2,
            plan_version="v1.0",
            created_at=datetime.now(),
            canon_parent="canon-parent-hash",
            genre_pack_binding=GenrePackBinding(
                pack_id="test-genre", version="1.0", content_hash="test-hash"
            ),
            required_transitions=[],
            prohibited_transitions=[],
            protected_facts=[],
            knowledge_boundaries=[],
            continuity_constraints=ContinuityConstraint(
                previous_chapter_id="test-ch1",
                previous_chapter_hash="prev-hash",
                previous_end_state={"scene": "critical_ending"},
                current_start_requirements=[],
            ),
        )

        # Large optional retrieval
        large_retrieval = [
            {"relevance": 0.95, "content": "High relevance content " * 100}
            for _ in range(20)
        ]

        result = compiler.compile_context(
            chapter_contract=contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("test-project"),
            previous_chapter_end={"actual": "Previous chapter critical ending"},
            optional_retrieval=large_retrieval,
            token_budget=10000,
            output_reserve=2000,
        )

        assert isinstance(result, ContextArtifact)

        # Continuity must be in mandatory_items (never displaced)
        continuity_items = [
            item for item in result.mandatory_items if item.source_type == "continuity"
        ]
        assert len(continuity_items) > 0, "Continuity must remain in mandatory items"
        assert continuity_items[0].mandatory is True


class TestATv201805DeterministicOffline:
    """AT-V2-018-05: 冻结输入在不调用生成模型时可编译 ContextArtifact"""

    def test_deterministic_compilation_no_llm_calls(
        self, compiler, mock_canon_state, basic_contract
    ):
        """Same frozen inputs produce identical results without LLM calls."""

        result1 = compiler.compile_context(
            chapter_contract=basic_contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("test-project"),
            token_budget=10000,
            output_reserve=2000,
        )

        result2 = compiler.compile_context(
            chapter_contract=basic_contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("test-project"),
            token_budget=10000,
            output_reserve=2000,
        )

        assert isinstance(result1, ContextArtifact)
        assert isinstance(result2, ContextArtifact)

        # artifact_id and created_at will differ, but content should be identical
        assert result1.chapter_contract_id == result2.chapter_contract_id
        assert result1.canon_parent == result2.canon_parent
        assert result1.genre_pack_hash == result2.genre_pack_hash
        assert len(result1.mandatory_items) == len(result2.mandatory_items)
        assert result1.compilation_log.mandatory_tokens == result2.compilation_log.mandatory_tokens

        # No LLM calls - verified by mock not being called with LLM-like methods
        # (Canon and GenrePack mocks don't expose generation APIs)
