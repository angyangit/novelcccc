"""Tests for V2-019 Model Gateway per ADR-010.

AT-V2-019-01: Budget admission gate blocks calls when insufficient funds
AT-V2-019-02: UNKNOWN result does not trigger auto-retry
AT-V2-019-03: Separate logical request, attempt, and provider IDs tracked
AT-V2-019-04: Cache hit returns zero cost with same semantic input
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from anovel.gateway import (
    BudgetManager,
    ModelGateway,
    ResultStatus,
    CostStatus,
)


class TestATv201901BudgetAdmission:
    """AT-V2-019-01: 预算不足时阻断调用"""

    def test_insufficient_budget_blocks_call(self):
        """Budget manager blocks call when insufficient funds."""
        budget = BudgetManager(total_limit_usd=1.0)

        # Reserve most of budget
        assert budget.reserve(0.9)

        # Try to reserve more than available
        assert not budget.reserve(0.5)

        # Verify state
        state = budget.get_state()
        assert state.inflight_reserved_usd == 0.9
        assert abs(state.available_usd() - 0.1) < 0.001  # Floating point tolerance


class TestATv201902UnknownNoRetry:
    """AT-V2-019-02: UNKNOWN 结果不触发自动重试"""

    @patch("anovel.gateway.anthropic_provider.Anthropic")
    def test_unknown_status_stops_retry(self, mock_anthropic_class):
        """UNKNOWN result should not trigger automatic retry."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Simulate timeout error (UNKNOWN status)
        mock_client.messages.create.side_effect = Exception("Request timeout")

        gateway = ModelGateway(
            anthropic_key="test-key", budget_limit_usd=100.0, max_retries=3
        )

        response = gateway.generate(
            model_id="claude-sonnet-4", prompt="Test prompt", max_tokens=100
        )

        # Should have exactly 1 attempt (no retries for UNKNOWN)
        assert len(response.attempts) == 1
        assert response.result_status == ResultStatus.UNKNOWN
        assert response.cost_status == CostStatus.UNKNOWN_LIABILITY


class TestATv201903RequestAttemptSeparation:
    """AT-V2-019-03: 逻辑请求、尝试、Provider ID 分离记录"""

    @patch("anovel.gateway.anthropic_provider.Anthropic")
    def test_request_attempt_provider_ids_separate(self, mock_anthropic_class):
        """Verify separate tracking of request ID, attempt ID, and provider ID."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock successful response
        mock_response = Mock()
        mock_response.id = "provider-request-123"
        mock_response.usage = Mock(input_tokens=10, output_tokens=20)
        mock_response.content = [Mock(type="text", text="Response text")]
        mock_client.messages.create.return_value = mock_response

        gateway = ModelGateway(anthropic_key="test-key", budget_limit_usd=100.0)

        response = gateway.generate(
            model_id="claude-sonnet-4", prompt="Test", max_tokens=50
        )

        assert response.result_status == ResultStatus.SUCCESS
        assert len(response.attempts) == 1

        attempt = response.attempts[0]
        # Verify separate IDs
        assert (
            attempt.request_id == response.request_id
        )  # Links back to logical request
        assert attempt.attempt_id != attempt.request_id  # Attempt has own ID
        assert (
            attempt.provider_request_id == "provider-request-123"
        )  # Provider ID tracked
        assert attempt.attempt_number == 1


class TestATv201904CacheHit:
    """AT-V2-019-04: 相同语义输入的缓存命中返回零成本"""

    @patch("anovel.gateway.anthropic_provider.Anthropic")
    def test_cache_hit_zero_cost(self, mock_anthropic_class):
        """Cache hit should return same result with zero additional cost."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock successful response
        mock_response = Mock()
        mock_response.id = "provider-request-123"
        mock_response.usage = Mock(input_tokens=10, output_tokens=20)
        mock_response.content = [Mock(type="text", text="Cached response")]
        mock_client.messages.create.return_value = mock_response

        gateway = ModelGateway(anthropic_key="test-key", budget_limit_usd=100.0)

        # First call - should hit provider
        response1 = gateway.generate(
            model_id="claude-sonnet-4", prompt="Test prompt", max_tokens=50
        )

        assert response1.result_status == ResultStatus.SUCCESS
        assert not response1.cache_hit
        assert response1.total_cost_usd > 0
        first_cost = response1.total_cost_usd

        # Second call with same semantic input - should hit cache
        response2 = gateway.generate(
            model_id="claude-sonnet-4", prompt="Test prompt", max_tokens=50
        )

        assert response2.result_status == ResultStatus.SUCCESS
        assert response2.cache_hit
        assert response2.total_cost_usd == 0.0
        assert response2.response_text == "Cached response"

        # Provider should only be called once
        assert mock_client.messages.create.call_count == 1


class TestBudgetManager:
    """Additional budget manager tests."""

    def test_confirm_cost_releases_reservation(self):
        """Confirming cost should release inflight reservation."""
        budget = BudgetManager(total_limit_usd=10.0)

        # Reserve budget
        assert budget.reserve(3.0)
        state = budget.get_state()
        assert state.inflight_reserved_usd == 3.0
        assert state.confirmed_spent_usd == 0.0

        # Confirm actual cost
        budget.confirm_cost(reserved_amount_usd=3.0, actual_cost_usd=2.5)
        state = budget.get_state()
        assert state.inflight_reserved_usd == 0.0
        assert state.confirmed_spent_usd == 2.5
        assert state.available_usd() == 7.5

    def test_mark_unknown_moves_to_liability(self):
        """Marking unknown should move from inflight to unknown liability."""
        budget = BudgetManager(total_limit_usd=10.0)

        assert budget.reserve(2.0)
        budget.mark_unknown(2.0)

        state = budget.get_state()
        assert state.inflight_reserved_usd == 0.0
        assert state.unknown_liability_usd == 2.0
        assert state.confirmed_spent_usd == 0.0
        # Unknown liability reduces available budget
        assert state.available_usd() == 8.0
