"""Historical Provenance Regression Tests

Tests 6 cases per REPO-AI-CONTEXT-HYGIENE-003 governance requirement.

Contract: Validate historical closure artifact provenance semantics using
production governance validator (EvidenceReader from governance_checks).
"""

import sys
import tempfile
import json
import hashlib
import subprocess
from pathlib import Path
import shutil
import pytest
import yaml

# Add plan/scripts to path for imports
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "plan" / "scripts"))

from governance_checks import EvidenceReader


class TestHistoricalProvenanceRegression:
    """Historical provenance validation using production EvidenceReader."""

    def setup_method(self):
        """Create temporary plan structure for each test.

        Use real plan directory to enable git operations for historical provenance.
        Tests create evidence in plan/test-hp-evidence/ which is cleaned up after.
        """
        # Use real plan directory so git operations work
        self.plan = REPO_ROOT / "plan"

        # Create test evidence directory inside plan/
        self.test_evidence_dir = self.plan / "test-hp-evidence"
        if self.test_evidence_dir.exists():
            shutil.rmtree(self.test_evidence_dir)
        self.test_evidence_dir.mkdir()

        # Load schema for EvidenceReader
        self.schema = json.loads((self.plan / "schemas/evidence-record.schema.json").read_text())

        # Error collector
        self.errors = []

    def teardown_method(self):
        """Clean up test evidence directory."""
        if self.test_evidence_dir.exists():
            shutil.rmtree(self.test_evidence_dir)

    def create_evidence_record(self, evidence_id, evidence_type, revision,
                                artifacts=None, subject_id=None):
        """Create a valid evidence record YAML file."""
        record = {
            "record_type": "plan_execution_evidence",
            "schema_version": "1.0",
            "evidence_id": evidence_id,
            "evidence_type": evidence_type,
            "subject_id": subject_id or "TEST",
            "revision": revision,
            "status": "PASS",
            "producer": "test",
            "executed_at": "2026-01-01T00:00:00Z",
            "environment_fingerprint": "test",
            "command": "pytest test.py",
            "exit_code": 0,
            "check_ids": ["CHECK-TEST-001"],
            "artifacts": artifacts or [],
            "input_evidence_refs": []
        }
        return record

    def test_HP_01_correct_subject_and_artifact_revisions(self):
        """HP-01: subject_revision A, artifact_revision B (A != B), correct SHA at B → PASS.

        Must have: A != B, artifact exists at B, recorded SHA == actual bytes at B.
        Production EvidenceReader returns ZERO provenance errors - validation succeeds.
        """
        # Use two different real revisions
        subject_revision_A = "28776a1aae31b4e49f48b84ea7f4ed044f9420ec"  # V2-061 domain complete
        artifact_revision_B = "c88377657818799ecf93918f4b98fe622a4a6037"  # Earlier revision

        assert subject_revision_A != artifact_revision_B, "HP-01 requires A != B"

        # Register historical provenance with artifact at revision B
        closure_id = "HP-01"
        historical_provenance = {
            closure_id: {
                "subject_revision": subject_revision_A,
                "artifact_revision": artifact_revision_B
            }
        }

        reader = EvidenceReader(
            self.plan, self.schema, self.errors,
            compat={}, historical_provenance=historical_provenance
        )

        # Use an artifact that exists at revision B in the real repo
        artifact_path = "machine/ci-gates.yaml"

        # Get actual content from git at revision B
        try:
            result = subprocess.run(
                ["git", "show", f"{artifact_revision_B}:plan/{artifact_path}"],
                capture_output=True, check=True, cwd=REPO_ROOT
            )
            actual_content_at_B = result.stdout
            actual_sha256_at_B = hashlib.sha256(actual_content_at_B).hexdigest()

            # Create test evidence in plan/test-hp-evidence/
            evidence_path = f"test-hp-evidence/{closure_id}/evidence.yaml"
            evidence_dir = self.test_evidence_dir / closure_id
            evidence_dir.mkdir(parents=True, exist_ok=True)

            record = self.create_evidence_record(
                evidence_id=f"{closure_id}-evidence",
                evidence_type="TEST_RESULT",
                revision=subject_revision_A,
                artifacts=[{"ref": artifact_path, "sha256": actual_sha256_at_B}],
                subject_id=closure_id
            )
            (evidence_dir / "evidence.yaml").write_text(yaml.dump(record))

            # Run production validator
            reader.read(evidence_path, {"TEST_RESULT"}, closure_id, subject_revision_A)

            # HP-01 PASS: ZERO provenance errors - validation succeeded
            assert len(self.errors) == 0, \
                f"HP-01 failed: expected zero provenance errors, got {len(self.errors)}: {self.errors}"

        except subprocess.CalledProcessError as e:
            pytest.fail(f"HP-01 setup failed: git command error: {e}")

    def test_HP_02_artifact_revision_equals_subject_but_historical_bytes_differ(self):
        """HP-02: true artifact at B, subject at A (A != B), but incorrectly claim artifact_revision = A → FAIL.

        Production EvidenceReader must reject: wrong revision registration causes validation mismatch.
        """
        # True artifact revision
        true_artifact_revision_B = "c88377657818799ecf93918f4b98fe622a4a6037"
        # Subject revision (different)
        subject_revision_A = "28776a1aae31b4e49f48b84ea7f4ed044f9420ec"

        assert subject_revision_A != true_artifact_revision_B, "HP-02 requires A != B"

        # INCORRECT registration: claim artifact is at A (subject revision) when it's really at B
        closure_id = "HP-02"
        historical_provenance = {
            closure_id: {
                "subject_revision": subject_revision_A,
                "artifact_revision": subject_revision_A  # WRONG - should be B
            }
        }

        reader = EvidenceReader(
            self.plan, self.schema, self.errors,
            compat={}, historical_provenance=historical_provenance
        )

        artifact_path = "machine/ci-gates.yaml"

        try:
            # Get content from TRUE revision B
            result_B = subprocess.run(
                ["git", "show", f"{true_artifact_revision_B}:plan/{artifact_path}"],
                capture_output=True, check=True, cwd=REPO_ROOT
            )
            content_at_B = result_B.stdout
            sha_at_B = hashlib.sha256(content_at_B).hexdigest()

            # Create test evidence
            evidence_path = f"test-hp-evidence/{closure_id}/evidence.yaml"
            evidence_dir = self.test_evidence_dir / closure_id
            evidence_dir.mkdir(parents=True, exist_ok=True)

            record = self.create_evidence_record(
                evidence_id=f"{closure_id}-evidence",
                evidence_type="TEST_RESULT",
                revision=subject_revision_A,
                artifacts=[{"ref": artifact_path, "sha256": sha_at_B}],
                subject_id=closure_id
            )
            (evidence_dir / "evidence.yaml").write_text(yaml.dump(record))

            # Run production validator
            reader.read(evidence_path, {"TEST_RESULT"}, closure_id, subject_revision_A)

            # HP-02 must FAIL: wrong revision registration rejection
            # Validator tries to verify at claimed A, but bytes are from B
            artifact_errors = [e for e in self.errors if "EVIDENCE_ARTIFACT" in e and
                             (artifact_path in e or "historical" in e.lower() or "revision" in e.lower())]
            assert len(artifact_errors) > 0, \
                f"HP-02 failed: expected wrong-revision rejection, got {len(self.errors)} errors: {self.errors}"

        except subprocess.CalledProcessError as e:
            pytest.fail(f"HP-02 setup failed: {e}")

    def test_HP_03_wrong_artifact_revision(self):
        """HP-03: Wrong artifact_revision → git read failure, nonexistent revision rejection."""
        subject_revision = "28776a1aae31b4e49f48b84ea7f4ed044f9420ec"
        claimed_revision = "0000000000000000000000000000000000000000"

        historical_provenance = {
            "HP-03": {
                "subject_revision": subject_revision,
                "artifact_revision": claimed_revision
            }
        }

        reader = EvidenceReader(
            self.plan, self.schema, self.errors,
            compat={}, historical_provenance=historical_provenance
        )

        artifact_path = "machine/ci-gates.yaml"

        evidence_path = "test-hp-evidence/HP-03/evidence.yaml"
        evidence_dir = self.test_evidence_dir / "HP-03"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        record = self.create_evidence_record(
            evidence_id="HP-03-evidence",
            evidence_type="TEST_RESULT",
            revision=subject_revision,
            artifacts=[{"ref": artifact_path, "sha256": hashlib.sha256(b"content").hexdigest()}],
            subject_id="HP-03"
        )
        (evidence_dir / "evidence.yaml").write_text(yaml.dump(record))

        # Run production validator
        reader.read(evidence_path, {"TEST_RESULT"}, "HP-03", subject_revision)

        # HP-03: Must reject nonexistent revision (git cannot read at 0000...)
        artifact_errors = [e for e in self.errors if "EVIDENCE_ARTIFACT" in e and
                         (artifact_path in e or "cannot read" in e.lower() or "git" in e.lower())]
        assert len(artifact_errors) > 0, \
            f"HP-03 failed: expected nonexistent-revision rejection, got: {self.errors}"

    def test_HP_04_wrong_historical_SHA(self):
        """HP-04: Real historical scenario - valid revision B, artifact exists at B, but recorded SHA is wrong → hash mismatch.

        Must construct: subject A, artifact at B (A != B), git can read B, but evidence claims wrong SHA.
        Production validator must detect exact hash mismatch at historical revision B.
        """
        subject_revision_A = "28776a1aae31b4e49f48b84ea7f4ed044f9420ec"
        artifact_revision_B = "c88377657818799ecf93918f4b98fe622a4a6037"

        assert subject_revision_A != artifact_revision_B, "HP-04 requires A != B"

        closure_id = "HP-04"
        historical_provenance = {
            closure_id: {
                "subject_revision": subject_revision_A,
                "artifact_revision": artifact_revision_B
            }
        }

        reader = EvidenceReader(
            self.plan, self.schema, self.errors,
            compat={}, historical_provenance=historical_provenance
        )

        # Use artifact that exists at revision B
        artifact_path = "machine/ci-gates.yaml"

        try:
            # Get actual content from git at revision B
            result = subprocess.run(
                ["git", "show", f"{artifact_revision_B}:plan/{artifact_path}"],
                capture_output=True, check=True, cwd=REPO_ROOT
            )
            actual_content_at_B = result.stdout
            actual_sha256_at_B = hashlib.sha256(actual_content_at_B).hexdigest()

            # Claim WRONG SHA (different from actual)
            wrong_sha256 = "0" * 64
            assert wrong_sha256 != actual_sha256_at_B, "Must use different SHA for HP-04"

            evidence_path = f"test-hp-evidence/{closure_id}/evidence.yaml"
            evidence_dir = self.test_evidence_dir / closure_id
            evidence_dir.mkdir(parents=True, exist_ok=True)

            record = self.create_evidence_record(
                evidence_id=f"{closure_id}-evidence",
                evidence_type="TEST_RESULT",
                revision=subject_revision_A,
                artifacts=[{"ref": artifact_path, "sha256": wrong_sha256}],
                subject_id=closure_id
            )
            (evidence_dir / "evidence.yaml").write_text(yaml.dump(record))

            # Run production validator with historical provenance
            reader.read(evidence_path, {"TEST_RESULT"}, closure_id, subject_revision_A)

            # HP-04: Must detect hash mismatch at historical revision B
            # Artifact exists at B (git can read), but recorded SHA is wrong
            artifact_errors = [e for e in self.errors if "EVIDENCE_ARTIFACT" in e]
            assert len(artifact_errors) > 0, \
                f"HP-04 failed: expected hash mismatch detection, got {len(self.errors)} errors: {self.errors}"

            # Verify it's hash-related error, not missing/cannot-read
            hash_related = any("mismatch" in e.lower() for e in artifact_errors)
            assert hash_related, \
                f"HP-04: expected hash mismatch semantics, got: {artifact_errors}"

        except subprocess.CalledProcessError as e:
            pytest.fail(f"HP-04 setup failed: git command error: {e}")

    def test_HP_05_artifact_missing_at_claimed_revision(self):
        """HP-05: Valid revision + missing artifact path → cannot read / missing failure."""
        subject_revision = "28776a1aae31b4e49f48b84ea7f4ed044f9420ec"
        artifact_revision = "c88377657818799ecf93918f4b98fe622a4a6037"

        historical_provenance = {
            "HP-05": {
                "subject_revision": subject_revision,
                "artifact_revision": artifact_revision
            }
        }

        reader = EvidenceReader(
            self.plan, self.schema, self.errors,
            compat={}, historical_provenance=historical_provenance
        )

        # Reference nonexistent artifact (doesn't exist at revision)
        artifact_path = "validation/execution/HP-05/nonexistent.txt"

        evidence_path = "test-hp-evidence/HP-05/evidence.yaml"
        evidence_dir = self.test_evidence_dir / "HP-05"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        record = self.create_evidence_record(
            evidence_id="HP-05-evidence",
            evidence_type="TEST_RESULT",
            revision=subject_revision,
            artifacts=[{"ref": artifact_path, "sha256": "a" * 64}],
            subject_id="HP-05"
        )
        (evidence_dir / "evidence.yaml").write_text(yaml.dump(record))

        # Run production validator
        reader.read(evidence_path, {"TEST_RESULT"}, "HP-05", subject_revision)

        # HP-05: Must reject missing artifact
        artifact_errors = [e for e in self.errors if "EVIDENCE_ARTIFACT" in e and
                         (artifact_path in e or "cannot read" in e.lower() or "missing" in e.lower())]
        assert len(artifact_errors) > 0, \
            f"HP-05 failed: expected missing-artifact rejection, got: {self.errors}"

    def test_HP_06_unregistered_closure_attempts_compatibility(self):
        """HP-06: Production compatibility check via EvidenceReader.

        Registered grandfather (V2-005/V2-006) → allowed per real rule.
        Unregistered closure → rejected.
        No test-only authority.
        """
        # Test non-grandfathered task
        reader_999 = EvidenceReader(
            self.plan, self.schema, [],
            compat={"V2-005": {}, "V2-006": {}},
            historical_provenance={}
        )

        evidence_path_999 = "test-hp-evidence/V2-999/missing-evidence.yaml"
        errors_999 = []
        reader_999.errors = errors_999

        # Create minimal test evidence structure
        evidence_dir_999 = self.test_evidence_dir / "V2-999"
        evidence_dir_999.mkdir(parents=True, exist_ok=True)

        # Try to read missing evidence for non-grandfathered task
        reader_999.read(evidence_path_999, {"TEST_RESULT"}, "V2-999", "a" * 40)

        # Should have errors
        assert len(errors_999) > 0, "Expected error for non-grandfathered task V2-999"

        # Test grandfathered task V2-005
        reader_005 = EvidenceReader(
            self.plan, self.schema, [],
            compat={"V2-005": {}, "V2-006": {}},
            historical_provenance={}
        )

        evidence_path_005 = "test-hp-evidence/V2-005/missing-evidence.yaml"
        errors_005 = []
        reader_005.errors = errors_005

        # Create test evidence directory for V2-005
        evidence_dir_005 = self.test_evidence_dir / "V2-005"
        evidence_dir_005.mkdir(parents=True, exist_ok=True)

        result = reader_005.read(evidence_path_005, {"TEST_RESULT"}, "V2-005", "b" * 40)

        # Grandfathered task: production code suppresses errors
        assert result is None, "Grandfathered task should return None"
        # Production compatibility mechanism validates this

    def test_HP_07_scoped_provenance_pins_listed_record_only(self):
        """HP-07: evidence_refs scope pins only listed records; siblings use current bytes."""
        g_p3_dir = "validation/closure/G-P3-68c8d00"
        provenance = {
            "G-P3-68c8d00": {
                "subject_revision": "68c8d00ae5a74ee31ddb8d18ab23ab6921c185d1",
                "artifact_revision": "140b2dc253cfaa9538351be96ae8e007c8cb96c2",
                "evidence_refs": [f"{g_p3_dir}/phase-decision.yaml"],
            }
        }

        pinned_errors = []
        EvidenceReader(
            self.plan, self.schema, pinned_errors, compat={}, historical_provenance=provenance
        ).read(f"{g_p3_dir}/phase-decision.yaml", {"PHASE_DECISION"}, "G-P3", None)
        assert not [e for e in pinned_errors if "EVIDENCE_ARTIFACT" in e], pinned_errors

        unpinned_errors = []
        EvidenceReader(
            self.plan, self.schema, unpinned_errors, compat={}, historical_provenance={}
        ).read(f"{g_p3_dir}/phase-decision.yaml", {"PHASE_DECISION"}, "G-P3", None)
        assert [e for e in unpinned_errors if "EVIDENCE_ARTIFACT" in e], \
            "phase-decision must fail without the pin (live phase-gates.yaml changed)"

        sibling_errors = []
        EvidenceReader(
            self.plan, self.schema, sibling_errors, compat={}, historical_provenance=provenance
        ).read(f"{g_p3_dir}/V2-015-code-evidence.yaml", {"CODE"}, "V2-015", None)
        assert not [e for e in sibling_errors if "EVIDENCE_ARTIFACT" in e], \
            f"sibling must still verify against current bytes: {sibling_errors}"

        tampered = self.test_evidence_dir / "G-P3-68c8d00"
        tampered.mkdir(parents=True)
        record = yaml.safe_load((self.plan / g_p3_dir / "phase-decision.yaml").read_text())
        record["artifacts"][0]["sha256"] = "0" * 64
        (tampered / "phase-decision.yaml").write_text(yaml.dump(record))
        tampered_ref = "test-hp-evidence/G-P3-68c8d00/phase-decision.yaml"
        scoped = {"X": dict(provenance["G-P3-68c8d00"], evidence_refs=[tampered_ref])}
        tampered_errors = []
        EvidenceReader(
            self.plan, self.schema, tampered_errors, compat={}, historical_provenance=scoped
        ).read(tampered_ref, {"PHASE_DECISION"}, "G-P3", None)
        assert any("mismatch" in e for e in tampered_errors), tampered_errors
