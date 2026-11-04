#!/usr/bin/env python3
"""Generate first chapter for both fixtures - V2-020 demonstration.

Generates actual Chinese novel chapters for:
1. Urban business startup
2. Eastern fantasy cultivation
"""

import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from anovel.context.compiler import ContextCompiler
from anovel.context.token_counter import TokenCounter
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import CanonState, OperationType
from anovel.domain.identity import ProjectId
from anovel.gateway import ModelGateway
from anovel.planning.models import GenrePackBinding
from anovel.workflow import ChapterWorkflow


class SimpleTokenCounter(TokenCounter):
    """Simple token counter for demo."""

    @property
    def encoding_name(self) -> str:
        return "simple-demo-tokenizer"

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


def create_urban_business_contract():
    """Create chapter 1 contract for urban business fixture."""
    return ChapterContract(
        contract_id=str(uuid.uuid4()),
        chapter_id="urban-ch1",
        chapter_number=1,
        plan_version="v1.0",
        created_at=datetime.now(),
        canon_parent="urban-canon-init",
        genre_pack_binding=GenrePackBinding(
            pack_id="urban-business-startup",
            version="1.0",
            content_hash="urban-hash-v1",
        ),
        required_transitions=[
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.name",
                target_value="林逸",
                rationale="确立主角姓名",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.age",
                target_value=28,
                rationale="确立主角年龄",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.background",
                target_value="大厂工程师，工作五年后决定创业",
                rationale="确立主角背景",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.startup_idea",
                target_value="基于AI的智能任务管理平台，解决团队协作痛点",
                rationale="确立核心创业方向",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.initial_challenge",
                target_value="刚辞职，存款只够支撑半年，需要尽快找到天使投资",
                rationale="建立初始冲突张力",
            ),
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
        continuity_constraints=None,
    )


def create_fantasy_cultivation_contract():
    """Create chapter 1 contract for eastern fantasy fixture."""
    return ChapterContract(
        contract_id=str(uuid.uuid4()),
        chapter_id="fantasy-ch1",
        chapter_number=1,
        plan_version="v1.0",
        created_at=datetime.now(),
        canon_parent="fantasy-canon-init",
        genre_pack_binding=GenrePackBinding(
            pack_id="eastern-fantasy-cultivation",
            version="1.0",
            content_hash="fantasy-hash-v1",
        ),
        required_transitions=[
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.name",
                target_value="叶凡",
                rationale="确立主角姓名",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.age",
                target_value=16,
                rationale="确立主角年龄",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.cultivation_realm",
                target_value="炼气期一层",
                rationale="确立主角起始修为",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.background",
                target_value="青云宗外门弟子，天赋平平，被同门欺压",
                rationale="确立主角背景与处境",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.golden_finger",
                target_value="意外获得上古仙人的传承玉简，记载逆天功法《混元天经》",
                rationale="确立主角核心优势",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.immediate_danger",
                target_value="三日后外门大比，输了将被逐出宗门",
                rationale="建立紧迫感和初始冲突",
            ),
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
        continuity_constraints=None,
    )


def main():
    """Generate first chapter for both fixtures."""
    print("=" * 80)
    print("V2-020 Chapter Workflow - First Chapter Generation")
    print("=" * 80)

    # Setup services
    mock_genre = Mock()
    mock_genre.get_pack = Mock(return_value=Mock())

    token_counter = SimpleTokenCounter()
    context_compiler = ContextCompiler(mock_genre, token_counter)

    # Check for real API key in environment
    import os

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    use_real_model = anthropic_key is not None

    if use_real_model:
        print("\n✓ ANTHROPIC_API_KEY found - will generate with real Claude model\n")
        model_gateway = ModelGateway(anthropic_key=anthropic_key, budget_limit_usd=5.0)  # type: ignore[call-arg]
    else:
        print("\n⚠ No ANTHROPIC_API_KEY - using mock provider (no real content)\n")
        # Create mock gateway for testing
        mock_gateway = Mock()
        mock_response = Mock()
        mock_response.result_status = Mock(value="success")
        mock_response.response_text = (
            "# 第一章 起点\n\n（这是Mock模式，未生成真实内容）"
        )
        mock_response.total_cost_usd = 0.0
        mock_gateway.generate = Mock(return_value=mock_response)
        model_gateway = mock_gateway

    # Create workflow
    output_dir = Path("output/drafts")
    workflow = ChapterWorkflow(context_compiler, model_gateway, output_dir)

    # Mock Canon state
    mock_canon_state = CanonState(
        project_id=ProjectId("demo-project"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Generate urban business chapter 1
    print("\n[1/2] Urban Business Startup - Chapter 1")
    print("-" * 80)

    urban_contract = create_urban_business_contract()
    try:
        urban_draft = workflow.generate_chapter_draft(
            chapter_contract=urban_contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("urban-business-001"),
            model_id="claude-sonnet-4",
            max_tokens=4000 if use_real_model else 100,
        )

        print(f"\n✅ Generation SUCCESS")
        print(f"Title: {urban_draft.title}")
        print(f"Word Count: {urban_draft.word_count}")
        print(f"Cost: ${urban_draft.generation_cost_usd:.4f}")
        print(f"Saved: output/drafts/chapter_001_urban-ch1.md")

    except Exception as e:
        print(f"\n❌ Generation FAILED: {e}")

    # Generate fantasy cultivation chapter 1
    print("\n[2/2] Eastern Fantasy Cultivation - Chapter 1")
    print("-" * 80)

    fantasy_contract = create_fantasy_cultivation_contract()
    try:
        fantasy_draft = workflow.generate_chapter_draft(
            chapter_contract=fantasy_contract,
            canon_state=mock_canon_state,
            project_id=ProjectId("fantasy-cultivation-001"),
            model_id="claude-sonnet-4",
            max_tokens=4000 if use_real_model else 100,
        )

        print(f"\n✅ Generation SUCCESS")
        print(f"Title: {fantasy_draft.title}")
        print(f"Word Count: {fantasy_draft.word_count}")
        print(f"Cost: ${fantasy_draft.generation_cost_usd:.4f}")
        print(f"Saved: output/drafts/chapter_001_fantasy-ch1.md")

    except Exception as e:
        print(f"\n❌ Generation FAILED: {e}")

    print("\n" + "=" * 80)
    print("First Chapter Generation Complete")
    print("=" * 80)

    if use_real_model:
        print("\n请查看 output/drafts/ 目录中的生成章节，进行人工阅读质量评价。")
    else:
        print("\n提示：设置 ANTHROPIC_API_KEY 环境变量后可生成真实小说内容。")


if __name__ == "__main__":
    main()
