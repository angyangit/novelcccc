"""Stage 7D: LLM Extraction Pipeline Demo with Fake Provider

Demonstrates structured semantic extraction without paid API calls.
"""

from anovel.gateway.fake_llm_provider import FakeLLMProvider
from anovel.gateway.gateway import ModelGateway


def demo_extraction_pipeline():
    """Demonstrate LLM extraction pipeline with fake responses."""
    print("=" * 80)
    print("Stage 7D: LLM Extraction Pipeline Demo")
    print("=" * 80)
    print()
    print("Using FakeLLMProvider - NO PAID API CALLS")
    print()

    scenarios = [
        ("Urban Funding", "urban_funding"),
        ("Fantasy Breakthrough", "fantasy_breakthrough"),
        ("Contradictory Evidence", "contradictory"),
        ("Negation/Plans", "negation"),
        ("Empty (No Changes)", "empty"),
    ]

    for name, scenario in scenarios:
        print("-" * 80)
        print(f"Scenario: {name}")
        print("-" * 80)

        # Create fake provider and gateway
        provider = FakeLLMProvider(extraction_scenario=scenario)
        gateway = ModelGateway(provider=provider, total_budget_usd=None)

        # Simulate extraction prompt
        prompt = f"Extract state changes from prose: [Scenario: {scenario}]"

        # Check budget (should pass with fake provider)
        estimated_cost = provider.estimate_cost(input_tokens=500, output_tokens=250)
        budget_status = gateway.check_budget(estimated_cost)
        print(f"Budget Check: {budget_status} (Cost: ${estimated_cost:.6f})")

        # Generate extraction
        try:
            result = provider.generate(prompt, max_tokens=1000)
            print(f"Status: SUCCESS")
            print(f"Input Tokens: {result['input_tokens']}")
            print(f"Output Tokens: {result['output_tokens']}")
            print(f"Model: {result['model']}")
            print()
            print("Extracted JSON (first 500 chars):")
            print(result["prose"][:500])
            print()

            # Parse and analyze
            import json

            try:
                extraction = json.loads(result["prose"])
                print(f"State Changes: {len(extraction.get('state_changes', []))}")
                print(f"Beliefs: {len(extraction.get('beliefs', []))}")
                print(f"Rumors: {len(extraction.get('rumors', []))}")
                print(f"Plans: {len(extraction.get('plans', []))}")
                print(f"Negations: {len(extraction.get('negations', []))}")

                # Show state changes
                for i, change in enumerate(extraction.get("state_changes", []), 1):
                    print(
                        f"  Change {i}: {change['fact_path']} = {change['value']} "
                        f"(confidence: {change['confidence']})"
                    )

            except json.JSONDecodeError as e:
                print(f"JSON Parse Error: {e}")

        except Exception as e:
            print(f"Status: ERROR - {e}")

        print()

    print("=" * 80)
    print("Demo Complete")
    print("=" * 80)
    print()
    print("Coverage:")
    print("  ✅ Structured extraction JSON format")
    print("  ✅ State changes with evidence locations")
    print("  ✅ Beliefs vs. facts distinction")
    print("  ✅ Rumors/unverified claims")
    print("  ✅ Plans (未发生) vs. actual changes")
    print("  ✅ Negations")
    print("  ✅ Contradictory evidence handling")
    print()
    print("Next Steps:")
    print(
        "  1. Create real StructuredExtractor that parses JSON and builds Operations"
    )
    print("  2. Validate evidence positions match actual prose")
    print("  3. Run through Q0-Q3 validators")
    print("  4. Test with real Anthropic Provider (when authorized)")
    print()


if __name__ == "__main__":
    demo_extraction_pipeline()
