"""Tests for P0-E: ADR-008 invalidation scope rules.

Tests all 5 invalidation scenarios:
1. Canon parent advance invalidates contracts bound to old parent
2. GenrePack upgrade invalidates contracts using old hash
3. Prior chapter revision invalidates dependent chapters
4. Plan supersession invalidates contracts referencing old version
5. Fixture content change invalidates all contracts from that fixture
"""

import pytest
from datetime import datetime

from anovel.planning.replanning import (
    InvalidationRecord,
    generate_invalidation_scope,
    create_replan_proposal,
)


class TestADR008InvalidationRules:
    """Test ADR-008 invalidation scope rules (AT-V2-017-08)."""

    def test_rule_1_canon_advance_invalidation(self):
        """Test that Canon parent advance invalidates bound contracts."""
        contracts = [
            {
                "chapter_id": "chapter_01",
                "canon_parent": "canon_hash_v1",
                "chapter_number": 1,
            },
            {
                "chapter_id": "chapter_02",
                "canon_parent": "canon_hash_v1",
                "chapter_number": 2,
            },
            {
                "chapter_id": "chapter_03",
                "canon_parent": "canon_hash_v2",  # Different parent
                "chapter_number": 3,
            },
        ]

        scope = generate_invalidation_scope(
            change_type="canon_advance",
            changed_input="canon_hash_v1",  # Old parent hash
            all_contracts=contracts,
        )

        # Should invalidate chapters 1 and 2 (bound to old parent)
        assert "chapter_01" in scope.affected_chapters
        assert "chapter_02" in scope.affected_chapters
        assert "chapter_03" not in scope.affected_chapters
        assert len(scope.affected_chapters) == 2

    def test_rule_2_pack_upgrade_invalidation(self):
        """Test that GenrePack upgrade invalidates contracts using old hash."""
        contracts = [
            {
                "chapter_id": "chapter_01",
                "genre_pack_binding": {"pack_id": "urban.business", "content_hash": "pack_v1_hash"},
                "chapter_number": 1,
            },
            {
                "chapter_id": "chapter_02",
                "genre_pack_binding": {"pack_id": "urban.business", "content_hash": "pack_v1_hash"},
                "chapter_number": 2,
            },
            {
                "chapter_id": "chapter_03",
                "genre_pack_binding": {"pack_id": "urban.business", "content_hash": "pack_v2_hash"},
                "chapter_number": 3,
            },
        ]

        scope = generate_invalidation_scope(
            change_type="pack_upgrade",
            changed_input="pack_v1_hash",  # Old pack hash
            all_contracts=contracts,
        )

        # Should invalidate chapters 1 and 2 (using old pack)
        assert "chapter_01" in scope.affected_chapters
        assert "chapter_02" in scope.affected_chapters
        assert "chapter_03" not in scope.affected_chapters
        assert len(scope.affected_chapters) == 2

    def test_rule_3_chapter_revision_invalidation(self):
        """Test that prior chapter revision invalidates dependent chapters."""
        contracts = [
            {"chapter_id": "chapter_01", "chapter_number": 1},
            {"chapter_id": "chapter_02", "chapter_number": 2},
            {"chapter_id": "chapter_03", "chapter_number": 3},
            {"chapter_id": "chapter_04", "chapter_number": 4},
        ]

        # Chapter 2 revised
        scope = generate_invalidation_scope(
            change_type="chapter_revision",
            changed_input="chapter_02",  # Revised chapter
            all_contracts=contracts,
        )

        # Should invalidate chapters 3 and 4 (subsequent to chapter 2)
        assert "chapter_01" not in scope.affected_chapters
        assert "chapter_02" not in scope.affected_chapters  # Revised chapter itself not invalidated
        assert "chapter_03" in scope.affected_chapters
        assert "chapter_04" in scope.affected_chapters
        assert len(scope.affected_chapters) == 2

    def test_rule_4_plan_supersession_invalidation(self):
        """Test that plan supersession invalidates old version contracts."""
        contracts = [
            {"chapter_id": "chapter_01", "plan_version": "v1", "chapter_number": 1},
            {"chapter_id": "chapter_02", "plan_version": "v1", "chapter_number": 2},
            {"chapter_id": "chapter_03", "plan_version": "v2", "chapter_number": 3},
            {"chapter_id": "chapter_04", "plan_version": "v2", "chapter_number": 4},
        ]

        # Plan v1 superseded by v2
        scope = generate_invalidation_scope(
            change_type="plan_supersession",
            changed_input="v1",  # Old version
            all_contracts=contracts,
        )

        # Should invalidate chapters 1 and 2 (referencing v1)
        assert "chapter_01" in scope.affected_chapters
        assert "chapter_02" in scope.affected_chapters
        assert "chapter_03" not in scope.affected_chapters
        assert "chapter_04" not in scope.affected_chapters
        assert len(scope.affected_chapters) == 2

    def test_rule_5_fixture_change_invalidation(self):
        """Test that fixture content change invalidates all related contracts."""
        contracts = [
            {"chapter_id": "chapter_01", "fixture_ref": "urban_v1", "chapter_number": 1},
            {"chapter_id": "chapter_02", "fixture_ref": "urban_v1", "chapter_number": 2},
            {"chapter_id": "chapter_03", "fixture_ref": "fantasy_v1", "chapter_number": 3},
        ]

        # Urban fixture changed
        scope = generate_invalidation_scope(
            change_type="fixture_change",
            changed_input="urban_v1",  # Changed fixture
            all_contracts=contracts,
        )

        # Should invalidate all contracts from urban_v1 fixture
        assert "chapter_01" in scope.affected_chapters
        assert "chapter_02" in scope.affected_chapters
        assert "chapter_03" not in scope.affected_chapters
        assert len(scope.affected_chapters) == 2


class TestReplanProposal:
    """Test replan proposal generation."""

    def test_replan_proposal_created_for_invalidation(self):
        """Test that invalidation generates replan proposal (not auto-rewrite)."""
        invalidation = InvalidationRecord(
            contract_id="contract_001",
            invalidation_reason="canon_parent_changed",
            invalidated_at=datetime.now(),
            affected_inputs={"old_parent": "old_canon_hash", "new_parent": "new_canon_hash"},
        )

        scope = generate_invalidation_scope(
            change_type="canon_advance",
            changed_input="old_canon_hash",
            all_contracts=[
                {"chapter_id": "chapter_01", "canon_parent": "old_canon_hash", "chapter_number": 1},
                {"chapter_id": "chapter_02", "canon_parent": "old_canon_hash", "chapter_number": 2},
            ],
        )

        proposal = create_replan_proposal(
            invalidation=invalidation,
            scope=scope,
            current_version="v1",
        )

        # Should create proposal, not auto-execute
        assert proposal.proposal_id is not None
        assert proposal.new_plan_version == "v2"  # Incremented
        assert len(proposal.affected_chapters) == 2
        assert proposal.approval_status == "pending"
        assert "Recompile" in proposal.proposed_changes

    def test_replan_version_increment(self):
        """Test that replan proposal increments version correctly."""
        invalidation = InvalidationRecord(
            contract_id="contract_001",
            invalidation_reason="pack_upgraded",
            invalidated_at=datetime.now(),
            affected_inputs={"old_hash": "old_pack_hash", "new_hash": "new_pack_hash"},
        )

        scope = generate_invalidation_scope(
            change_type="pack_upgrade",
            changed_input="old_pack_hash",
            all_contracts=[
                {
                    "chapter_id": "chapter_01",
                    "genre_pack_binding": {"content_hash": "old_pack_hash"},
                    "chapter_number": 1,
                },
            ],
        )

        # Test version increment
        proposal_v2 = create_replan_proposal(invalidation, scope, "v1")
        assert proposal_v2.new_plan_version == "v2"

        proposal_v3 = create_replan_proposal(invalidation, scope, "v2")
        assert proposal_v3.new_plan_version == "v3"

        proposal_v10 = create_replan_proposal(invalidation, scope, "v9")
        assert proposal_v10.new_plan_version == "v10"

    def test_proposal_requires_approval(self):
        """Test that proposals start in pending state (require approval)."""
        invalidation = InvalidationRecord(
            contract_id="contract_001",
            invalidation_reason="prior_chapter_revised",
            invalidated_at=datetime.now(),
            affected_inputs={"revised_chapter": "chapter_01"},
        )

        scope = generate_invalidation_scope(
            change_type="chapter_revision",
            changed_input="chapter_01",
            all_contracts=[
                {"chapter_id": "chapter_02", "chapter_number": 2},
                {"chapter_id": "chapter_03", "chapter_number": 3},
            ],
        )

        proposal = create_replan_proposal(invalidation, scope, "v1")

        # Should require approval
        assert proposal.approval_status == "pending"
        assert proposal.approved_by is None
        assert proposal.approved_at is None


class TestInvalidationEdgeCases:
    """Test edge cases in invalidation logic."""

    def test_empty_contracts_list(self):
        """Test invalidation with no contracts."""
        scope = generate_invalidation_scope(
            change_type="canon_advance",
            changed_input="old_hash",
            all_contracts=[],
        )

        assert scope.affected_chapters == []
        assert len(scope.affected_chapters) == 0

    def test_no_matching_contracts(self):
        """Test invalidation when no contracts match criteria."""
        contracts = [
            {"chapter_id": "chapter_01", "canon_parent": "new_hash", "chapter_number": 1},
        ]

        scope = generate_invalidation_scope(
            change_type="canon_advance",
            changed_input="old_hash",  # Different hash
            all_contracts=contracts,
        )

        assert scope.affected_chapters == []

    def test_chapter_revision_of_last_chapter(self):
        """Test that revising the last chapter invalidates nothing."""
        contracts = [
            {"chapter_id": "chapter_01", "chapter_number": 1},
            {"chapter_id": "chapter_02", "chapter_number": 2},
            {"chapter_id": "chapter_03", "chapter_number": 3},
        ]

        # Revise chapter 3 (last chapter)
        scope = generate_invalidation_scope(
            change_type="chapter_revision",
            changed_input="chapter_03",
            all_contracts=contracts,
        )

        # No subsequent chapters to invalidate
        assert scope.affected_chapters == []

    def test_multiple_invalidation_types_cascade(self):
        """Test that multiple changes can create cascading invalidations."""
        contracts = [
            {
                "chapter_id": "chapter_01",
                "canon_parent": "canon_v1",
                "genre_pack_binding": {"content_hash": "pack_v1"},
                "plan_version": "v1",
                "chapter_number": 1,
            },
        ]

        # Canon advance
        scope_canon = generate_invalidation_scope("canon_advance", "canon_v1", contracts)
        assert "chapter_01" in scope_canon.affected_chapters

        # Pack upgrade
        scope_pack = generate_invalidation_scope("pack_upgrade", "pack_v1", contracts)
        assert "chapter_01" in scope_pack.affected_chapters

        # Plan supersession
        scope_plan = generate_invalidation_scope("plan_supersession", "v1", contracts)
        assert "chapter_01" in scope_plan.affected_chapters

        # All three changes invalidate the same contract
        # (In real system, would consolidate into single replan proposal)
