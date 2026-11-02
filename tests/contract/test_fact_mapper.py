"""Unit tests for FactPathMapper.

Tests P0-B requirements:
- Typed fact paths (equity, resources, relationships, cultivation)
- Proper OperationType mapping (SET_FACT, END_FACT, UNDO_FACT)
- Urban and fantasy fixture patterns
- Confidence levels and diagnostics for uncertain mappings
"""

import pytest
from anovel.contracts.fact_mapper import FactPathMapper, MappedFact
from anovel.domain.delta import OperationType


class TestUrbanBusinessPatterns:
    """Test urban business state change mapping."""

    def setup_method(self):
        self.mapper = FactPathMapper()

    def test_equity_change_mapping(self):
        """Test equity percentage changes map to equity.{character}.percentage."""
        result = self.mapper.map_state_change(
            "张明持股从70%降至49%",
            "chapter_01",
            "urban.business.realistic"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "equity" in result.fact_path
        assert "zhang_ming" in result.fact_path
        assert result.confidence in ["certain", "probable"]

    def test_cash_resource_mapping(self):
        """Test cash changes map to resources.company.cash."""
        result = self.mapper.map_state_change(
            "公司账户余额从50万降至30万",
            "chapter_01",
            "urban.business.realistic"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "resources.company.cash" in result.fact_path
        assert result.confidence == "certain"

    def test_funding_received_mapping(self):
        """Test funding acquisition maps to resources.company.funding_received."""
        result = self.mapper.map_state_change(
            "获得500万资金注入",
            "chapter_01",
            "urban.business.realistic"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "resources.company" in result.fact_path
        assert result.confidence == "certain"

    def test_relationship_trust_mapping(self):
        """Test relationship trust changes map to relationships.{a}.{b}.trust_level."""
        result = self.mapper.map_state_change(
            "张明与李华信任度降低",
            "chapter_01",
            "urban.business.realistic"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "relationships" in result.fact_path
        assert "zhang_ming" in result.fact_path or "li_hua" in result.fact_path
        assert result.confidence in ["probable", "certain"]

    def test_relationship_status_change(self):
        """Test relationship status transitions."""
        result = self.mapper.map_state_change(
            "王总从陌生人变为潜在投资人",
            "chapter_01",
            "urban.business.realistic"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "relationships" in result.fact_path
        assert result.confidence in ["probable", "certain"]


class TestFantasyCultivationPatterns:
    """Test fantasy cultivation state change mapping."""

    def setup_method(self):
        self.mapper = FactPathMapper()

    def test_cultivation_advancement(self):
        """Test cultivation realm advancement maps to cultivation.{character}.realm."""
        result = self.mapper.map_state_change(
            "王林从炼气九层突破至筑基期",
            "chapter_01",
            "fantasy.eastern.progression"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "cultivation" in result.fact_path
        assert "wang_lin" in result.fact_path
        assert "realm" in result.fact_path
        assert result.confidence in ["certain", "probable"]

    def test_cultivation_regression(self):
        """Test cultivation regression uses END_FACT."""
        result = self.mapper.map_state_change(
            "柳梦修为跌落至炼气五层",
            "chapter_01",
            "fantasy.eastern.progression"
        )

        assert result.operation_type == OperationType.END_FACT
        assert "cultivation" in result.fact_path
        assert "liu_meng" in result.fact_path
        assert result.confidence in ["certain", "probable"]

    def test_dao_comprehension(self):
        """Test dao comprehension changes map to cultivation.{character}.dao_comprehension."""
        result = self.mapper.map_state_change(
            "道韵从15提升至20",
            "chapter_01",
            "fantasy.eastern.progression"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "cultivation" in result.fact_path
        assert "dao_comprehension" in result.fact_path
        assert result.confidence in ["certain", "probable"]

    def test_spirit_stone_consumption(self):
        """Test spirit stone consumption uses END_FACT."""
        result = self.mapper.map_state_change(
            "王林灵石消耗至200块",
            "chapter_01",
            "fantasy.eastern.progression"
        )

        assert result.operation_type == OperationType.END_FACT
        assert "resources" in result.fact_path
        assert "spirit_stones" in result.fact_path
        assert result.confidence in ["certain", "probable"]

    def test_character_condition(self):
        """Test character condition changes map to condition.{character}."""
        result = self.mapper.map_state_change(
            "柳梦伤势恶化",
            "chapter_01",
            "fantasy.eastern.progression"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "condition" in result.fact_path
        assert "liu_meng" in result.fact_path
        assert result.confidence in ["probable", "certain"]


class TestGenericPatterns:
    """Test genre-agnostic patterns."""

    def setup_method(self):
        self.mapper = FactPathMapper()

    def test_knowledge_acquisition(self):
        """Test knowledge acquisition maps to knowledge.{character}.acquired."""
        result = self.mapper.map_state_change(
            "了解契约条款和隐藏风险",
            "chapter_01",
            "fantasy.eastern.progression"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "knowledge" in result.fact_path
        assert result.confidence in ["probable", "certain"]

    def test_world_state_market(self):
        """Test market state changes map to world.market.state."""
        result = self.mapper.map_state_change(
            "市场窗口期缩短",
            "chapter_01",
            "urban.business.realistic"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert "world.market" in result.fact_path
        assert result.confidence in ["probable", "certain"]


class TestUncertainMappings:
    """Test uncertain mappings return diagnostics."""

    def setup_method(self):
        self.mapper = FactPathMapper()

    def test_unmappable_change_returns_diagnostic(self):
        """Test that unmappable state changes return diagnostic."""
        result = self.mapper.map_state_change(
            "某个完全无法识别的状态变化描述",
            "chapter_01",
            "urban.business.realistic"
        )

        assert result.confidence == "uncertain"
        assert result.diagnostic is not None
        assert "Could not map" in result.diagnostic
        assert "untyped_change" in result.fact_path

    def test_uncertain_mapping_returns_untyped_fallback(self):
        """Test that uncertain mappings return untyped fallback (for mapper level).

        Note: At the compiler level, uncertain mappings now cause compilation
        to fail with CompilationDiagnostic. This test verifies the mapper
        itself still returns a fallback path with uncertain confidence.
        """
        result = self.mapper.map_state_change(
            "一些模糊的变化",
            "chapter_01",
            "urban.business.realistic"
        )

        assert result.operation_type == OperationType.SET_FACT
        assert result.fact_path is not None
        assert result.target_value == "一些模糊的变化"
        assert result.confidence == "uncertain"
        assert "untyped_change" in result.fact_path


class TestRealFixtureIntegration:
    """Test with actual fixture state changes."""

    def setup_method(self):
        self.mapper = FactPathMapper()

    def test_urban_fixture_state_changes(self):
        """Test mapping actual urban fixture state changes."""
        urban_changes = [
            "王总从陌生人变为潜在投资人",
            "公司账户余额从50万降至30万",
            "张明与李华信任度降低",
            "市场窗口期缩短",
            "获得两份具体投资协议",
        ]

        for change in urban_changes:
            result = self.mapper.map_state_change(
                change, "chapter_01", "urban.business.realistic"
            )
            # Should not be uncertain for real fixture data
            assert result.confidence in ["certain", "probable"], f"Unexpected uncertain mapping for: {change}"
            assert "untyped_change" not in result.fact_path, f"Fallback path used for: {change}"

    def test_fantasy_fixture_state_changes(self):
        """Test mapping actual fantasy fixture state changes."""
        fantasy_changes = [
            "获得古修洞府资源",
            "道韵从15提升至20",
            "柳梦修为跌落至炼气五层",
            "王林灵石消耗至200块",
            "了解契约条款和隐藏风险",
            "柳梦伤势恶化",
        ]

        for change in fantasy_changes:
            result = self.mapper.map_state_change(
                change, "chapter_01", "fantasy.eastern.progression"
            )
            # Should not be uncertain for real fixture data
            assert result.confidence in ["certain", "probable"], f"Unexpected uncertain mapping for: {change}"
            assert "untyped_change" not in result.fact_path, f"Fallback path used for: {change}"
