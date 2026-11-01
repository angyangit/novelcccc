"""Stage 7E: Controlled 3-Chapter Experiment Entry Point

Minimal entry for real novel generation with safety controls.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from anovel.contracts.compiler import ContractCompiler
from anovel.context.compiler import ContextCompiler
from anovel.domain.delta import CanonState
from anovel.domain.identity import ProjectId
from anovel.gateway.gateway import ModelGateway
from anovel.gateway.mock_provider import MockProvider
from anovel.planning.models import SeriesVision
from anovel.quality.q0 import Q0Validator
from anovel.workflow.offline_extractor import OfflineExtractor
from anovel.workflow.workflow import ChapterWorkflow


class ThreeChapterExperiment:
    """Controlled 3-chapter novel generation experiment.

    Safety features:
    - Default: Dry run mode (no Canon commits)
    - Default: Mock provider (no paid calls)
    - Saves all artifacts for inspection
    - Stops on ERROR/UNKNOWN/quality failure
    """

    def __init__(
        self,
        series_vision: SeriesVision,
        output_dir: Path,
        dry_run: bool = True,
        use_mock_provider: bool = True,
        allow_paid_calls: bool = False,
    ):
        """Initialize experiment.

        Args:
            series_vision: Series vision for the novel
            output_dir: Directory to save artifacts
            dry_run: If True, no Canon commits (default: True)
            use_mock_provider: If True, use MockProvider (default: True)
            allow_paid_calls: If True and not mock, allow real API calls (default: False)
        """
        self.series_vision = series_vision
        self.output_dir = output_dir
        self.dry_run = dry_run
        self.use_mock_provider = use_mock_provider
        self.allow_paid_calls = allow_paid_calls

        # Safety checks
        if not dry_run:
            raise RuntimeError(
                "Non-dry-run mode requires explicit Owner authorization. "
                "Dry run protects production Canon from unauthorized modification."
            )

        if not use_mock_provider and not allow_paid_calls:
            raise RuntimeError(
                "Real provider requires allow_paid_calls=True. "
                "This prevents accidental paid API usage."
            )

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.contract_compiler = ContractCompiler()
        self.context_compiler = ContextCompiler()

        # Provider and gateway
        if use_mock_provider:
            provider = MockProvider(mode="success")
        else:
            raise NotImplementedError(
                "Real provider integration requires Stage 7C completion + authorization"
            )

        self.gateway = ModelGateway(provider=provider, total_budget_usd=None)

        # Extractor and validators
        self.extractor = OfflineExtractor()
        self.q0_validator = Q0Validator()

        # Workflow
        self.workflow = ChapterWorkflow(
            contract_compiler=self.contract_compiler,
            context_compiler=self.context_compiler,
            model_gateway=self.gateway,
            extractor=self.extractor,
            q0_validator=self.q0_validator,
            mock_mode=dry_run,
        )

        # Experiment state
        self.chapters_completed: list[dict[str, Any]] = []
        self.current_canon_state = CanonState(
            project_id=ProjectId(series_vision.series_id),
            facts=(),
            tombstones=frozenset(),
            commit_history=(),
        )

    def run_experiment(self, num_chapters: int = 3) -> dict[str, Any]:
        """Run controlled multi-chapter experiment.

        Args:
            num_chapters: Number of chapters to generate (default: 3)

        Returns:
            Experiment results with status and artifacts
        """
        print(f"=" * 80)
        print(f"Three-Chapter Experiment: {self.series_vision.title}")
        print(f"=" * 80)
        print()
        print(f"Mode: {'DRY RUN (no Canon commits)' if self.dry_run else 'LIVE'}")
        print(f"Provider: {'Mock (no paid calls)' if self.use_mock_provider else 'Real'}")
        print(f"Output: {self.output_dir}")
        print()

        results = {
            "experiment_id": f"exp-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "series_id": self.series_vision.series_id,
            "dry_run": self.dry_run,
            "use_mock_provider": self.use_mock_provider,
            "chapters": [],
            "status": "running",
            "error": None,
        }

        try:
            for chapter_num in range(1, num_chapters + 1):
                print(f"-" * 80)
                print(f"Chapter {chapter_num}/{num_chapters}")
                print(f"-" * 80)

                chapter_result = self._generate_chapter(chapter_num)
                results["chapters"].append(chapter_result)

                # Save chapter artifact
                self._save_chapter_artifact(chapter_num, chapter_result)

                # Check for errors
                if chapter_result["workflow_status"] == "failed":
                    print(f"✗ Chapter {chapter_num} FAILED: {chapter_result['error']}")
                    results["status"] = "failed"
                    results["error"] = f"Chapter {chapter_num} failed"
                    break

                if chapter_result["workflow_status"] == "unknown":
                    print(f"? Chapter {chapter_num} UNKNOWN")
                    results["status"] = "unknown"
                    results["error"] = f"Chapter {chapter_num} unknown status"
                    break

                print(f"✓ Chapter {chapter_num} completed")
                print()

            if results["status"] == "running":
                results["status"] = "completed"

        except Exception as e:
            results["status"] = "error"
            results["error"] = str(e)
            print(f"✗ Experiment ERROR: {e}")

        # Save final results
        self._save_experiment_results(results)

        print(f"=" * 80)
        print(f"Experiment Status: {results['status'].upper()}")
        print(f"=" * 80)
        print()

        return results

    def _generate_chapter(self, chapter_num: int) -> dict[str, Any]:
        """Generate single chapter."""
        canon_parent = f"canon-{chapter_num - 1}"

        # Run workflow
        workflow_result = self.workflow.execute_chapter(
            series_vision=self.series_vision,
            chapter_number=chapter_num,
            canon_parent=canon_parent,
        )

        # Extract key information
        chapter_result = {
            "chapter_number": chapter_num,
            "workflow_status": workflow_result.status,
            "prose_hash": workflow_result.prose_hash,
            "delta_id": str(workflow_result.delta_id) if workflow_result.delta_id else None,
            "commit_receipt": workflow_result.commit_receipt,
            "quality_passed": workflow_result.quality_passed,
            "quality_checks": workflow_result.quality_checks,
            "blocking_issues": workflow_result.blocking_issues,
            "error": workflow_result.error,
            "completed_at": datetime.now().isoformat(),
        }

        return chapter_result

    def _save_chapter_artifact(self, chapter_num: int, chapter_result: dict[str, Any]):
        """Save chapter artifact to disk."""
        artifact_path = self.output_dir / f"chapter_{chapter_num:03d}.json"
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(chapter_result, f, indent=2, ensure_ascii=False)

    def _save_experiment_results(self, results: dict[str, Any]):
        """Save final experiment results."""
        results_path = self.output_dir / "experiment_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    """Run controlled 3-chapter experiment."""
    from anovel.planning.models import GenrePackBinding, WorldConstraints

    # Create test series vision
    series_vision = SeriesVision(
        series_id="test-3chapter-urban",
        title="硅谷创业实验",
        synopsis="三章都市创业小说测试",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban",
            version="1.0",
            content_hash="test-urban",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # Create experiment
    experiment = ThreeChapterExperiment(
        series_vision=series_vision,
        output_dir=Path("experiments/3chapter_test"),
        dry_run=True,  # SAFETY: No Canon commits
        use_mock_provider=True,  # SAFETY: No paid calls
        allow_paid_calls=False,  # SAFETY: Block real API
    )

    # Run experiment
    results = experiment.run_experiment(num_chapters=3)

    # Print summary
    print()
    print("Experiment Summary:")
    print(f"  Status: {results['status']}")
    print(f"  Chapters Completed: {len(results['chapters'])}")
    if results["error"]:
        print(f"  Error: {results['error']}")

    return 0 if results["status"] == "completed" else 1


if __name__ == "__main__":
    exit(main())
