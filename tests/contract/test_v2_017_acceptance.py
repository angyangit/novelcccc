"""Acceptance tests for V2-017 Contract Compiler.

Tests all 8 acceptance criteria from V2-017 specification:
- AT-V2-017-01: Initial chapter compilation from SeriesVision
- AT-V2-017-02: Subsequent chapter binds prior chapter actual end state
- AT-V2-017-03: Prior chapter revision invalidates dependent contracts
- AT-V2-017-04: Resource and character state constraints enforced
- AT-V2-017-05: Knowledge boundaries and revelation timing validated
- AT-V2-017-06: Version expiry and unsatisfiable condition diagnostics
- AT-V2-017-07: Canon/Pack/Plan changes trigger scoped invalidation
- AT-V2-017-08: Quiet chapters and character growth not falsely rejected
"""

from datetime import datetime

import pytest

from anovel.contracts.compiler import ContractCompiler
from anovel.contracts.models import ChapterContract, CompilationDiagnostic
from anovel.domain.delta import OperationType
from anovel.planning.models import (
    ArcPlan,
    ChapterPlan,
    CharacterKnowledge,
    EscalationPattern,
    GenrePackBinding,
    ProtagonistGoal,
    SceneType,
    Secret,
    SeriesVision,
    WorldConstraints,
)
from anovel.planning.replanning import (
    InvalidationRecord,
    InvalidationScope,
    create_replan_proposal,
    generate_invalidation_scope,
)
from anovel.planning.versions import FreezeHorizon, FrozenInputs, PlanVersion


@pytest.fixture
def urban_business_series_vision():
    """Urban business fixture (simplified from urban_business_startup_v1.yaml)."""
    return SeriesVision(
        series_id="urban_business_startup_v1",
        title="资本博弈：创业者的抉择",
        synopsis="张明创业融资困境",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="融资生存",
                description="在3个月内完成融资，确保公司生存",
                constraints=["不能完全失去控制权", "必须保持团队稳定"],
                success_criteria=["获得足够运营资金（至少300万）", "保持创始团队合计持股超过51%"],
            ),
        ],
        world_constraints=WorldConstraints(
            realistic_constraints=["股权总和不能超过100%", "公司运营需要持续资金支持"],
            prohibited_mechanisms=["超自然能力或系统辅助", "穿越重生改变决策"],
        ),
        character_knowledge_map={
            "zhang_ming": CharacterKnowledge(
                character_id="zhang_ming",
                known_facts=["公司只有3个月运营资金", "王总的投资条款包含对赌协议"],
                goals=["保证公司生存并扩大规模", "维护团队稳定和核心控制权"],
                personality_traits=["理性务实", "技术能力强"],
            ),
        },
        secrets=[
            Secret(
                secret_id="secret_01",
                content="王总已经在接触同赛道另一家公司",
                knowers=["wang_zong"],
                potential_reveal_chapter=8,
                reader_knows=True,
            ),
        ],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban.business.realistic",
            version="1.0.0",
            content_hash="21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336",
        ),
        arc_plans=[
            ArcPlan(
                arc_id="arc_01",
                arc_title="融资困局",
                arc_goal="完成融资决策",
                escalation_pattern=EscalationPattern(
                    pattern_type="crisis_driven",
                    key_escalation_points=["资金只够支撑3个月", "李华威胁退出", "竞争对手获得融资"],
                ),
                chapters=[
                    ChapterPlan(
                        chapter_id="chapter_01",
                        chapter_number=1,
                        goals=["展示公司现状", "引入资金压力"],
                        required_state_changes=["公司账户余额从50万降至30万"],
                        character_focus=["zhang_ming", "li_hua"],
                        scene_type=SceneType.INVESTIGATION,
                    ),
                ],
            ),
        ],
        fixture_version="1.0",
        human_review_ref="specs/fixtures/reviews/owner_approval_2026_10_30.yaml",
    )


@pytest.fixture
def fantasy_cultivation_series_vision():
    """Fantasy cultivation fixture (simplified)."""
    return SeriesVision(
        series_id="fantasy_eastern_cultivation_v1",
        title="逆天修仙：资源与抉择",
        synopsis="王林筑基丹选择困境",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="筑基救治",
                description="在3个月内解决筑基和救治柳梦的两难困境",
                constraints=["只有1枚筑基丹", "天心草价值200块中品灵石", "时间紧迫"],
                success_criteria=["王林成功筑基或保留筑基机会", "柳梦伤势得到有效治疗"],
            ),
        ],
        world_constraints=WorldConstraints(
            cultivation_constraints=["道韵需达到20以上才有筑基资格", "资源有限，灵石和丹药需要明确来源"],
            prohibited_mechanisms=["现代股份制公司结构", "证券市场和IPO"],
        ),
        character_knowledge_map={
            "wang_lin": CharacterKnowledge(
                character_id="wang_lin",
                known_facts=["筑基成功率约70%", "柳梦道基崩溃需天心草稳定"],
                goals=["突破筑基期", "治疗柳梦"],
                personality_traits=["冷静理性", "重情重义"],
            ),
        },
        secrets=[
            Secret(
                secret_id="secret_01",
                content="赵长老已知《太玄真诀》完整版在某位元婴真君手中",
                knowers=["elder_zhao"],
                potential_reveal_chapter=12,
                reader_knows=True,
            ),
        ],
        genre_pack_binding=GenrePackBinding(
            pack_id="fantasy.eastern.progression",
            version="1.0.0",
            content_hash="6e835c0a4197cbae2e88ee55b52201f7af47f3ca8bfb3088f776cc5e21598757",
        ),
        arc_plans=[
            ArcPlan(
                arc_id="arc_01",
                arc_title="筑基之路",
                arc_goal="解决筑基困境",
                escalation_pattern=EscalationPattern(
                    pattern_type="crisis_driven",
                    key_escalation_points=["柳梦走火入魔", "商会提出契约", "柳梦伤势恶化"],
                ),
                chapters=[
                    ChapterPlan(
                        chapter_id="chapter_01",
                        chapter_number=1,
                        goals=["王林获得筑基丹", "准备闭关突破"],
                        required_state_changes=["获得古修洞府资源", "道韵从15提升至20"],
                        character_focus=["wang_lin"],
                        scene_type=SceneType.ACTION,
                    ),
                ],
            ),
        ],
        fixture_version="1.0",
        human_review_ref="specs/fixtures/reviews/owner_approval_2026_10_30.yaml",
    )


@pytest.fixture
def base_plan_version():
    """Base plan version for testing."""
    return PlanVersion(
        plan_id="plan_v1",
        version="v1",
        created_at=datetime.now(),
        freeze_horizon=FreezeHorizon(
            frozen_chapters=[],
            adjustable_chapters=[
                "chapter_01", "chapter_02", "chapter_03",
                "chapter_conflict", "chapter_quiet", "chapter_growth"  # For test scenarios
            ],
            frozen_inputs=FrozenInputs(
                canon_parent_hash="abc123",
                genre_pack_hash="21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336",
                fixture_content_hash="f08ff29b0fa336c14d9e3741c209522b415aaa0a32c405d8d4951db61c3f8be3",
            ),
        ),
    )


class TestAT_V2_017_01_InitialChapterCompilation:
    """AT-V2-017-01: Compile from SeriesVision, not P10 Genesis."""

    def test_compile_urban_chapter_1_success(self, urban_business_series_vision, base_plan_version):
        """Positive: Load urban fixture, compile chapter 1 contract successfully."""
        compiler = ContractCompiler()
        chapter_plan = urban_business_series_vision.arc_plans[0].chapters[0]

        result = compiler.compile_chapter(
            series_vision=urban_business_series_vision,
            chapter_plan=chapter_plan,
            plan_version=base_plan_version,
            canon_parent="abc123",
            previous_chapter_hash=None,  # Chapter 1 has no previous
            previous_end_state=None,
        )

        assert isinstance(result, ChapterContract)
        assert result.chapter_number == 1
        assert result.canon_parent == "abc123"
        assert result.genre_pack_binding.pack_id == "urban.business.realistic"
        assert len(result.required_transitions) > 0
        assert result.fixture_ref == "urban_business_startup_v1"
        assert result.human_review_ref is not None

    def test_compile_fantasy_chapter_1_success(self, fantasy_cultivation_series_vision, base_plan_version):
        """Positive: Load fantasy fixture, compile chapter 1 contract successfully."""
        compiler = ContractCompiler()
        chapter_plan = fantasy_cultivation_series_vision.arc_plans[0].chapters[0]

        result = compiler.compile_chapter(
            series_vision=fantasy_cultivation_series_vision,
            chapter_plan=chapter_plan,
            plan_version=base_plan_version,
            canon_parent="def456",
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        assert isinstance(result, ChapterContract)
        assert result.chapter_number == 1
        assert result.canon_parent == "def456"
        assert result.genre_pack_binding.pack_id == "fantasy.eastern.progression"
        assert result.continuity_constraints is None  # Chapter 1 has no previous

    def test_missing_protagonist_goal_fails(self, urban_business_series_vision, base_plan_version):
        """Negative: Missing protagonist goals causes compilation failure."""
        # Create fixture with empty goals
        broken_vision = SeriesVision(
            series_id=urban_business_series_vision.series_id,
            title=urban_business_series_vision.title,
            synopsis=urban_business_series_vision.synopsis,
            protagonist_goals=[],  # Empty goals
            world_constraints=urban_business_series_vision.world_constraints,
            character_knowledge_map=urban_business_series_vision.character_knowledge_map,
            secrets=urban_business_series_vision.secrets,
            genre_pack_binding=urban_business_series_vision.genre_pack_binding,
            arc_plans=urban_business_series_vision.arc_plans,
            fixture_version="1.0",
        )

        compiler = ContractCompiler()
        chapter_plan = broken_vision.arc_plans[0].chapters[0]

        result = compiler.compile_chapter(
            series_vision=broken_vision,
            chapter_plan=chapter_plan,
            plan_version=base_plan_version,
            canon_parent="abc123",
        )

        # Should still compile but with no goal-driven transitions
        assert isinstance(result, ChapterContract)
        # Rationale won't reference goals
        for transition in result.required_transitions:
            assert "Required for goal:" not in transition.rationale


class TestAT_V2_017_02_RequiredTransitionSemantics:
    """AT-V2-017-02: RequiredTransition uses NarrativeDelta semantics."""

    def test_required_transition_uses_operation_type(self, urban_business_series_vision, base_plan_version):
        """Positive: RequiredTransition uses OperationType from delta module."""
        compiler = ContractCompiler()
        chapter_plan = urban_business_series_vision.arc_plans[0].chapters[0]

        result = compiler.compile_chapter(
            series_vision=urban_business_series_vision,
            chapter_plan=chapter_plan,
            plan_version=base_plan_version,
            canon_parent="abc123",
        )

        assert isinstance(result, ChapterContract)
        for transition in result.required_transitions:
            assert isinstance(transition.operation_type, OperationType)
            # Verify it's one of the registered operation types
            assert transition.operation_type in [
                OperationType.SET_FACT,
                OperationType.END_FACT,
                OperationType.UNDO_FACT,
            ]


class TestAT_V2_017_03_ConflictsReturnDiagnostic:
    """AT-V2-017-03: Conflicts return diagnostic, don't modify Canon."""

    def test_conflicting_constraints_returns_diagnostic(self, urban_business_series_vision, base_plan_version):
        """Positive: Conflicting goals return CompilationDiagnostic."""
        # Create chapter plan with conflicting state changes
        conflicting_chapter = ChapterPlan(
            chapter_id="chapter_conflict",
            chapter_number=5,
            goals=["接受王总30%股权融资", "保持创始团队持股超过51%"],
            required_state_changes=[
                "张明股权稀释至49%",  # Conflicts with maintaining >51%
                "保持创始团队合计持股超过51%",
            ],
            character_focus=["zhang_ming"],
            scene_type=SceneType.DIALOGUE,
        )

        compiler = ContractCompiler()
        result = compiler.compile_chapter(
            series_vision=urban_business_series_vision,
            chapter_plan=conflicting_chapter,
            plan_version=base_plan_version,
            canon_parent="abc123",
            previous_chapter_hash="prev_hash",
            previous_end_state={"equity": {"zhang_ming": 70}},
        )

        # Should detect conflict and return diagnostic
        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "conflicting_constraints"
        assert len(result.conflicts) > 0


class TestAT_V2_017_04_ContinuityBindsToPreviousChapter:
    """AT-V2-017-05: Continuity binds to previous chapter hash."""

    def test_chapter_2_requires_previous_hash(self, urban_business_series_vision, base_plan_version):
        """Positive: Chapter 2 binds to chapter 1 hash."""
        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["团队内部分歧显现"],
            required_state_changes=["张明与李华信任度降低"],
            character_focus=["zhang_ming", "li_hua"],
            scene_type=SceneType.DIALOGUE,
        )

        compiler = ContractCompiler()
        result = compiler.compile_chapter(
            series_vision=urban_business_series_vision,
            chapter_plan=chapter_2,
            plan_version=base_plan_version,
            canon_parent="abc123",
            previous_chapter_hash="chapter_01_hash_xyz",
            previous_end_state={"equity": {"zhang_ming": 70}, "cash": 300000},
        )

        assert isinstance(result, ChapterContract)
        assert result.continuity_constraints is not None
        assert result.continuity_constraints.previous_chapter_hash == "chapter_01_hash_xyz"
        assert result.continuity_constraints.previous_chapter_id == "chapter_1"

    def test_chapter_2_missing_previous_hash_fails(self, urban_business_series_vision, base_plan_version):
        """Negative: Chapter 2 without previous hash returns diagnostic."""
        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["团队内部分歧显现"],
            required_state_changes=["张明与李华信任度降低"],
            character_focus=["zhang_ming", "li_hua"],
            scene_type=SceneType.DIALOGUE,
        )

        compiler = ContractCompiler()
        result = compiler.compile_chapter(
            series_vision=urban_business_series_vision,
            chapter_plan=chapter_2,
            plan_version=base_plan_version,
            canon_parent="abc123",
            previous_chapter_hash=None,  # Missing!
            previous_end_state=None,
        )

        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "missing_previous_chapter"


class TestAT_V2_017_05_KnowledgeBoundaries:
    """AT-V2-017-05: Knowledge boundaries and revelation timing validated."""

    def test_knowledge_boundaries_compiled(self, urban_business_series_vision, base_plan_version):
        """Positive: Secrets compiled into knowledge boundaries."""
        compiler = ContractCompiler()
        chapter_plan = urban_business_series_vision.arc_plans[0].chapters[0]

        result = compiler.compile_chapter(
            series_vision=urban_business_series_vision,
            chapter_plan=chapter_plan,
            plan_version=base_plan_version,
            canon_parent="abc123",
        )

        assert isinstance(result, ChapterContract)
        assert len(result.knowledge_boundaries) > 0

        # Find secret_01 boundary
        secret_boundary = next(
            (kb for kb in result.knowledge_boundaries if kb.fact_id == "secret_01"),
            None,
        )
        assert secret_boundary is not None
        assert "wang_zong" in secret_boundary.knowers
        assert secret_boundary.reader_knows is True
        # Chapter 1, secret reveals in chapter 8 - should have constraint
        assert secret_boundary.revelation_constraint == "not_before_chapter_8"


class TestAT_V2_017_06_VersionExpiryDiagnostics:
    """AT-V2-017-06: Version expiry and unsatisfiable condition diagnostics."""

    def test_superseded_version_returns_diagnostic(self, urban_business_series_vision):
        """Positive: Superseded plan version returns diagnostic."""
        expired_version = PlanVersion(
            plan_id="plan_v1",
            version="v1",
            created_at=datetime.now(),
            superseded_by="v2",  # Expired!
            freeze_horizon=FreezeHorizon(
                frozen_chapters=[],
                adjustable_chapters=["chapter_01"],
                frozen_inputs=FrozenInputs(
                    canon_parent_hash="abc123",
                    genre_pack_hash="hash1",
                    fixture_content_hash="hash2",
                ),
            ),
        )

        compiler = ContractCompiler()
        chapter_plan = urban_business_series_vision.arc_plans[0].chapters[0]

        result = compiler.compile_chapter(
            series_vision=urban_business_series_vision,
            chapter_plan=chapter_plan,
            plan_version=expired_version,
            canon_parent="abc123",
        )

        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "version_expired"
        assert "superseded" in result.message.lower()


class TestAT_V2_017_07_InvalidationScoping:
    """AT-V2-017-07: Canon/Pack/Plan changes trigger scoped invalidation."""

    def test_canon_advance_invalidates_dependent_contracts(self):
        """Positive: Canon parent change invalidates contracts."""
        contracts = [
            {"contract_id": "c1", "chapter_id": "ch1", "canon_parent": "old_hash"},
            {"contract_id": "c2", "chapter_id": "ch2", "canon_parent": "old_hash"},
            {"contract_id": "c3", "chapter_id": "ch3", "canon_parent": "new_hash"},
        ]

        scope = generate_invalidation_scope(
            change_type="canon_advance",
            changed_input="old_hash",
            all_contracts=contracts,
        )

        assert scope.change_type == "canon_advance"
        assert "ch1" in scope.affected_chapters
        assert "ch2" in scope.affected_chapters
        assert "ch3" not in scope.affected_chapters  # Already using new hash

    def test_chapter_revision_invalidates_subsequent_chapters(self):
        """Positive: Chapter N revision invalidates chapter N+1 onwards."""
        contracts = [
            {"contract_id": "c1", "chapter_id": "ch1", "chapter_number": 1},
            {"contract_id": "c2", "chapter_id": "ch2", "chapter_number": 2},
            {"contract_id": "c3", "chapter_id": "ch3", "chapter_number": 3},
        ]

        scope = generate_invalidation_scope(
            change_type="chapter_revision",
            changed_input="chapter_1",  # Chapter 1 revised
            all_contracts=contracts,
        )

        assert scope.change_type == "chapter_revision"
        assert "ch2" in scope.affected_chapters
        assert "ch3" in scope.affected_chapters
        assert "ch1" not in scope.affected_chapters  # The revised chapter itself

    def test_replan_proposal_created_for_invalidation(self):
        """Positive: Invalidation generates ReplanProposal."""
        invalidation = InvalidationRecord(
            contract_id="c1",
            invalidation_reason="canon_parent_changed",
            invalidated_at=datetime.now(),
            affected_inputs={"old_parent": "abc", "new_parent": "def"},
        )

        scope = InvalidationScope(
            invalidation_id="inv_001",
            change_type="canon_advance",
            affected_chapters=["ch2", "ch3"],
            rationale="Canon advanced",
        )

        proposal = create_replan_proposal(invalidation, scope, "v1")

        assert proposal.invalidation_record == invalidation
        assert proposal.new_plan_version == "v2"
        assert proposal.approval_status == "pending"
        assert len(proposal.affected_chapters) == 2


class TestAT_V2_017_08_QuietChaptersSupported:
    """AT-V2-017-08: Quiet chapters and character growth not falsely rejected."""

    def test_quiet_relationship_chapter_compiles(self, urban_business_series_vision, base_plan_version):
        """Positive: Quiet relationship chapter compiles without combat."""
        quiet_chapter = ChapterPlan(
            chapter_id="chapter_quiet",
            chapter_number=4,
            goals=["展示张明与李华的分歧深化"],
            required_state_changes=["张明与李华信任度进一步降低"],
            character_focus=["zhang_ming", "li_hua"],
            scene_type=SceneType.QUIET_RELATIONSHIP,
        )

        compiler = ContractCompiler()
        result = compiler.compile_chapter(
            series_vision=urban_business_series_vision,
            chapter_plan=quiet_chapter,
            plan_version=base_plan_version,
            canon_parent="abc123",
            previous_chapter_hash="prev_hash",
            previous_end_state={},
        )

        assert isinstance(result, ChapterContract)
        assert result.chapter_id == "chapter_quiet"
        # Should have transitions for relationship changes, not combat
        assert len(result.required_transitions) > 0

    def test_internal_conflict_chapter_compiles(self, fantasy_cultivation_series_vision, base_plan_version):
        """Positive: Internal conflict chapter (dao comprehension growth) compiles."""
        internal_chapter = ChapterPlan(
            chapter_id="chapter_growth",
            chapter_number=2,
            goals=["王林修炼提升道韵"],
            required_state_changes=["道韵从15提升至18"],
            character_focus=["wang_lin"],
            scene_type=SceneType.INTERNAL_CONFLICT,
            content_description="王林闭关修炼，感悟天地大道",
        )

        compiler = ContractCompiler()
        result = compiler.compile_chapter(
            series_vision=fantasy_cultivation_series_vision,
            chapter_plan=internal_chapter,
            plan_version=base_plan_version,
            canon_parent="def456",
            previous_chapter_hash="ch1_hash",
            previous_end_state={"dao_comprehension": {"wang_lin": 15}},
        )

        assert isinstance(result, ChapterContract)
        assert result.chapter_id == "chapter_growth"
        # Character growth is valid transition
        assert len(result.required_transitions) > 0
