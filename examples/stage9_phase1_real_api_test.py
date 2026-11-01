"""Stage 9 Phase 1: Real Model Configuration Test

Tests real API configuration and makes first real call.
"""

from anovel.config import get_real_provider_config, mask_api_key
from anovel.gateway.anthropic_provider import AnthropicProvider


def test_real_api_configuration():
    """Test real API configuration loading."""
    print("=" * 80)
    print("Stage 9 Phase 1: Real Model Configuration Test")
    print("=" * 80)
    print()

    # Load configuration
    try:
        config = get_real_provider_config()
        print("✓ Configuration loaded successfully")
        print()
        print("Provider Configuration:")
        print(f"  Base URL: {config['base_url']}")
        print(f"  API Key: {mask_api_key(config['api_key'])}")
        print(f"  Model ID: {config['model_id']}")
        print()
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return 1

    # Create provider
    try:
        provider = AnthropicProvider(
            model_id=config["model_id"],
            api_key=config["api_key"],
            base_url=config["base_url"],
            allow_real_calls=True,  # AUTHORIZED by Owner
        )
        print("✓ Provider initialized")
        print()
    except Exception as e:
        print(f"✗ Provider initialization failed: {e}")
        return 1

    # Make test call
    print("Making first real API call...")
    print("Prompt: '你好，请用一句话介绍你自己。'")
    print()

    try:
        result = provider.generate(
            prompt="你好，请用一句话介绍你自己。",
            max_tokens=100,
            temperature=0.7,
        )

        print("✓ API call successful!")
        print()
        print("Response:")
        print(f"  Model: {result['model']}")
        print(f"  Input Tokens: {result['input_tokens']}")
        print(f"  Output Tokens: {result['output_tokens']}")
        print(f"  Finished: {result['finished']}")
        print()
        print("Generated Text:")
        print("-" * 80)
        print(result["prose"])
        print("-" * 80)
        print()

        # Estimate cost
        cost = provider.estimate_cost(result["input_tokens"], result["output_tokens"])
        print(f"Estimated Cost: ${cost:.6f}")
        print()

        return 0

    except Exception as e:
        print(f"✗ API call failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(test_real_api_configuration())
