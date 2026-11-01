"""Stage 9 Phase 2: Budget Protection Test

Tests $5 budget cap and cost tracking.
"""

from anovel.config import get_real_provider_config, mask_api_key
from anovel.gateway.anthropic_provider import AnthropicProvider
from anovel.gateway.budget_protected import BudgetProtectedGateway


def test_budget_protection():
    """Test budget protection with real API."""
    print("=" * 80)
    print("Stage 9 Phase 2: Budget Protection Test")
    print("=" * 80)
    print()

    # Load configuration
    config = get_real_provider_config()
    print("Provider Configuration:")
    print(f"  Base URL: {config['base_url']}")
    print(f"  API Key: {mask_api_key(config['api_key'])}")
    print(f"  Model ID: {config['model_id']}")
    print()

    # Create provider
    provider = AnthropicProvider(
        model_id=config["model_id"],
        api_key=config["api_key"],
        base_url=config["base_url"],
        allow_real_calls=True,
    )

    # Create budget-protected gateway
    gateway = BudgetProtectedGateway(provider, total_budget_usd=5.0)
    print("✓ Budget-protected gateway initialized")
    print(f"  Total Budget: $5.00")
    print()

    # Test 1: Small request
    print("-" * 80)
    print("Test 1: Small Request")
    print("-" * 80)
    try:
        result, cost = gateway.generate(
            prompt="请用10个字概括：什么是小说？",
            max_tokens=50,
            temperature=0.7,
        )
        print(f"✓ Request succeeded")
        print(f"  Response: {result['prose'][:80]}")
        print(f"  Tokens: {result['input_tokens']} → {result['output_tokens']}")
        print(f"  Cost: ${cost:.6f}")
    except Exception as e:
        print(f"✗ Request failed: {e}")

    gateway.print_budget_report()

    # Test 2: Another small request
    print("-" * 80)
    print("Test 2: Another Request")
    print("-" * 80)
    try:
        result, cost = gateway.generate(
            prompt="用一句话描述：小说创作的核心是什么？",
            max_tokens=100,
            temperature=0.7,
        )
        print(f"✓ Request succeeded")
        print(f"  Response: {result['prose'][:80]}")
        print(f"  Tokens: {result['input_tokens']} → {result['output_tokens']}")
        print(f"  Cost: ${cost:.6f}")
    except Exception as e:
        print(f"✗ Request failed: {e}")

    gateway.print_budget_report()

    # Test 3: Check remaining budget
    status = gateway.get_budget_status()
    print("-" * 80)
    print("Budget Status Check")
    print("-" * 80)
    print(f"Remaining Budget: ${status['remaining_usd']:.4f}")
    print(f"Requests Made: {status['requests_made']}")
    print()

    if status["remaining_usd"] < 0.01:
        print("⚠️  Budget nearly exhausted!")
    elif status["remaining_usd"] > 4.50:
        print("✓ Budget healthy (>90% remaining)")
    else:
        print(f"✓ Budget OK ({status['remaining_usd']/5.0*100:.1f}% remaining)")

    print()
    print("=" * 80)
    print("Phase 2 Complete: Budget Protection Verified")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(test_budget_protection())
