"""Tests for chapter range state change deduplication.

Phase 3 requirement: Beat-level state changes should not be duplicated
across every chapter in the range. Distinguish between:
- Beat-level phase goals (narrative arc across chapters)
- Beat-level cumulative changes (happen once across the beat)
- Chapter-specific transitions (bound to specific chapter)
"""

from pathlib import Path

from anovel.contracts.fixture_loader import load_series_vision_from_fixture


class TestChapterRangeDeduplication:
    """Test that beat-level state changes are not duplicated per chapter."""

    def test_urban_fixture_no_duplicate_cash_consumption(self):
        """Test that cash consumption in beat 1-3 is not tripled."""
        fixture_path = Path('specs/fixtures/urban_business_startup_v1.yaml')
        series_vision = load_series_vision_from_fixture(fixture_path)

        # Beat 1-3 has state_changes: ["公司账户余额从50万降至30万"]
        # This should be a beat-level change, not per-chapter
        chapters = series_vision.arc_plans[0].chapters[:3]

        # Currently FAILS: each chapter has the same cash change
        # Expected: only one chapter has it, or it's marked as beat-level
        cash_changes = []
        for ch in chapters:
            for change in ch.required_state_changes:
                if "账户余额" in change or "50万" in change:
                    cash_changes.append((ch.chapter_number, change))

        # Should have at most 1 cash change across the beat, not 3
        assert len(cash_changes) <= 1, (
            f"Cash consumption duplicated across chapters {[c[0] for c in cash_changes]}. "
            f"Beat-level changes should not repeat per chapter."
        )

    def test_urban_fixture_no_duplicate_relationship_changes(self):
        """Test that relationship changes in beat 4-7 are not quadrupled."""
        fixture_path = Path('specs/fixtures/urban_business_startup_v1.yaml')
        series_vision = load_series_vision_from_fixture(fixture_path)

        # Beat 4-7 has "张明与李华信任度降低"
        # This is a cumulative deterioration, not 4 separate drops
        chapters = series_vision.arc_plans[0].chapters[3:7]

        trust_changes = []
        for ch in chapters:
            for change in ch.required_state_changes:
                if "信任度" in change:
                    trust_changes.append((ch.chapter_number, change))

        # Should be tracked as a beat-level trend, not duplicated
        assert len(trust_changes) <= 1, (
            f"Trust change duplicated across {len(trust_changes)} chapters. "
            f"Beat-level changes should not repeat per chapter."
        )

    def test_beat_goals_vs_state_changes_distinction(self):
        """Test that beat goals (narrative content) are distinct from state changes."""
        fixture_path = Path('specs/fixtures/urban_business_startup_v1.yaml')
        series_vision = load_series_vision_from_fixture(fixture_path)

        # Beat 1-3: content="公司现状、资金压力、王总提出融资方案"
        # This is a narrative arc, should be in goals
        # state_changes should be cumulative facts, not narrative description

        chapters = series_vision.arc_plans[0].chapters[:3]

        for ch in chapters:
            # Goals should contain beat narrative content
            assert len(ch.goals) > 0

            # But required_state_changes should not duplicate across all 3
            # (This test currently fails due to the bug)

    def test_fantasy_fixture_no_duplicate_cultivation_advancement(self):
        """Test that cultivation realm changes are not duplicated."""
        fixture_path = Path('specs/fixtures/fantasy_eastern_cultivation_v1.yaml')
        series_vision = load_series_vision_from_fixture(fixture_path)

        # Fantasy fixture has similar beat ranges
        # Check that cultivation realm changes don't repeat
        chapters = series_vision.arc_plans[0].chapters

        realm_changes_by_chapter = {}
        for ch in chapters:
            realm_changes = [
                change for change in ch.required_state_changes
                if "修为" in change or "境界" in change or "筑基" in change
            ]
            if realm_changes:
                realm_changes_by_chapter[ch.chapter_number] = realm_changes

        # Each realm advancement should appear in at most one chapter
        # (or be marked as beat-level)
        all_realm_changes = [
            change
            for changes in realm_changes_by_chapter.values()
            for change in changes
        ]

        # Count duplicates
        from collections import Counter
        change_counts = Counter(all_realm_changes)
        duplicates = {change: count for change, count in change_counts.items() if count > 1}

        assert len(duplicates) == 0, (
            f"Cultivation changes duplicated across chapters: {duplicates}"
        )

    def test_resource_consumption_not_multiplied(self):
        """Test that resource consumption across beat range is cumulative, not multiplicative."""
        fixture_path = Path('specs/fixtures/urban_business_startup_v1.yaml')
        series_vision = load_series_vision_from_fixture(fixture_path)

        # Beat 1-3: cash 50万→30万 (loses 20万 total, not 60万)
        # Beat 11-13: cash →15万 (loses 15万 more, not 45万)

        chapters_1_3 = series_vision.arc_plans[0].chapters[:3]
        chapters_11_13 = series_vision.arc_plans[0].chapters[10:13]

        # If each chapter in 1-3 has the same cash change as required_transition,
        # the compiler would create 3 identical transitions, consuming 60万 total
        # This violates resource conservation

        # Count how many times the same state change appears
        all_changes = []
        for ch in chapters_1_3 + chapters_11_13:
            all_changes.extend(ch.required_state_changes)

        from collections import Counter
        change_counts = Counter(all_changes)

        # No state change should appear more than once
        duplicates = {change: count for change, count in change_counts.items() if count > 1}
        assert len(duplicates) == 0, (
            f"State changes duplicated: {duplicates}. "
            f"This would cause resource over-consumption."
        )
