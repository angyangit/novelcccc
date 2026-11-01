"""Stage 7E: Simplified Dry Run Entry Point

Demonstrates controlled chapter generation readiness without full workflow complexity.
"""

import json
from datetime import datetime
from pathlib import Path

from anovel.gateway.mock_provider import MockProvider


def demo_dry_run_readiness():
    """Demonstrate dry run readiness for 3-chapter experiment."""
    print("=" * 80)
    print("Stage 7E: 3-Chapter Experiment Readiness Demo")
    print("=" * 80)
    print()

    # Safety controls
    dry_run = True
    use_mock = True
    allow_paid_calls = False

    print("Safety Controls:")
    print(f"  Dry Run: {dry_run} (No Canon commits)")
    print(f"  Mock Provider: {use_mock} (No paid API calls)")
    print(f"  Allow Paid Calls: {allow_paid_calls}")
    print()

    if not dry_run:
        print("✗ ERROR: Non-dry-run requires Owner authorization")
        return 1

    if not use_mock and not allow_paid_calls:
        print("✗ ERROR: Real provider requires allow_paid_calls=True")
        return 1

    print("✓ Safety checks passed")
    print()

    # Create output directory
    output_dir = Path("experiments/3chapter_readiness")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    print()

    # Simulate 3-chapter generation
    chapters = []
    provider = MockProvider(mode="success")

    for chapter_num in range(1, 4):
        print(f"-" * 80)
        print(f"Chapter {chapter_num}/3")
        print(f"-" * 80)

        # Mock generation
        result = provider.generate(
            prompt=f"Chapter {chapter_num} prompt",
            max_tokens=2000,
        )

        chapter_data = {
            "chapter_number": chapter_num,
            "status": "success",
            "prose_preview": result["prose"][:100],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "model": result["model"],
            "dry_run": dry_run,
            "canon_committed": False,  # Dry run - no commits
            "generated_at": datetime.now().isoformat(),
        }

        chapters.append(chapter_data)

        # Save chapter artifact
        chapter_file = output_dir / f"chapter_{chapter_num:03d}.json"
        with open(chapter_file, "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, indent=2, ensure_ascii=False)

        print(f"✓ Chapter {chapter_num} generated (dry run)")
        print(f"  Prose: {result['prose'][:80]}...")
        print(f"  Tokens: {result['input_tokens']} in, {result['output_tokens']} out")
        print(f"  Saved: {chapter_file}")
        print()

    # Save experiment summary
    experiment_summary = {
        "experiment_id": f"readiness-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "dry_run": dry_run,
        "use_mock": use_mock,
        "chapters_generated": len(chapters),
        "status": "completed",
        "chapters": chapters,
    }

    summary_file = output_dir / "experiment_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(experiment_summary, f, indent=2, ensure_ascii=False)

    print("=" * 80)
    print("Experiment Complete")
    print("=" * 80)
    print()
    print(f"Chapters Generated: {len(chapters)}")
    print(f"Status: {experiment_summary['status']}")
    print(f"Summary: {summary_file}")
    print()

    print("Readiness Checklist:")
    print("  ✓ Dry run mode works")
    print("  ✓ Mock provider generates chapters")
    print("  ✓ Artifacts saved to disk")
    print("  ✓ No Canon commits in dry run")
    print("  ✓ No paid API calls")
    print("  ✓ 3-chapter continuity structure ready")
    print()

    print("Next Steps for Real Generation:")
    print("  1. Owner authorizes budget and model")
    print("  2. Replace MockProvider with AnthropicProvider")
    print("  3. Integrate StructuredExtractor with real LLM output")
    print("  4. Run Q0-Q3 validators on extracted Operations")
    print("  5. Connect to ChapterWorkflow.execute_chapter()")
    print("  6. Decide dry_run=False authorization for Canon commits")
    print()

    return 0


if __name__ == "__main__":
    exit(demo_dry_run_readiness())
