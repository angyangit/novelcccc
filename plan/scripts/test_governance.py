#!/usr/bin/env python3
"""Positive closure fixtures and isolated governance regressions, not runtime tests."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import validate_plan as validator
import yaml
from execution_checks import CONTROL_INPUTS, execution_checks
from governance_checks import evidence_checks

REVISION = "a" * 40


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="anovel-governance-test-")
        self.addCleanup(self.tmp.cleanup)
        self.plan = Path(self.tmp.name) / "plan"

        # Copy plan/ but exclude historical closure evidence to avoid validation conflicts
        def ignore_patterns(directory, contents):
            ignored = []
            if "validation" in Path(directory).parts:
                # Exclude closure/ directory - historical phase/milestone evidence only
                # Keep execution/ - needed for absence record tests
                if "closure" in contents:
                    ignored.append("closure")
            if "__pycache__" in contents:
                ignored.append("__pycache__")
            if ".DS_Store" in contents:
                ignored.append(".DS_Store")
            return ignored

        shutil.copytree(
            validator.PLAN,
            self.plan,
            ignore=ignore_patterns,
        )

        # Copy referenced docs/ files into plan/docs/ to make fixture self-contained
        # The validator resolves references relative to the plan directory
        docs_src = validator.PLAN.parent / "docs"
        docs_dst = self.plan / "docs"
        docs_dst.mkdir(exist_ok=True)

        # Copy contract files referenced by tasks
        for contract in [
            "V2-001_IMPLEMENTATION_CONTRACT.md",
            "V2-002_IMPLEMENTATION_CONTRACT.md",
            "V2-003_IMPLEMENTATION_CONTRACT.md",
            "V2-004_IMPLEMENTATION_CONTRACT.md",
            "V2-006_IMPLEMENTATION_CONTRACT.md",
        ]:
            src = docs_src / contract
            if src.exists():
                shutil.copy2(src, docs_dst / contract)

        # Copy archive directory if referenced
        archive_src = docs_src / "archive"
        if archive_src.exists():
            shutil.copytree(archive_src, docs_dst / "archive", dirs_exist_ok=True)

        self.data = deepcopy(validator.load())
        self.records = self.plan / "validation/fixture"
        self.records.mkdir(parents=True, exist_ok=True)
        raw = self.records / "raw.txt"
        raw.write_text(
            "SYNTHETIC ISOLATED TEST INPUT. NOT REAL ENGINEERING OR CI EVIDENCE.\n"
        )
        self.artifact = {
            "ref": "validation/fixture/raw.txt",
            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        }

        # Normalize all P1 tasks to OPEN for clean positive baseline
        # Production state (2026-10-19): V2-005/006 have absence records,
        # V2-061/007/008 are fully CLOSED with complete evidence.
        # Fixture creates clean baseline by removing all P1 closure state to avoid
        # dependency validation violations (V2-007 depends on V2-005, V2-008 depends on V2-006/007/061).
        # Individual tests add CLOSED status with synthetic evidence as needed.
        P1_TASKS = ("V2-005", "V2-006", "V2-061", "V2-007", "V2-008")
        tasks = self.data["implementation-backlog"]["tasks"]
        for task in tasks:
            if task["task_id"] in P1_TASKS:
                task["status"] = "OPEN"
                task["readiness"] = "PLANNED"
                task["evidence"] = {"code": [], "tests": [], "ci": [], "acceptance": []}
                task["execution_packet_ref"] = None

        # Remove all P1 execution evidence from the temporary fixture copy
        for task_id in P1_TASKS:
            absence_dir = self.plan / "validation/execution" / task_id
            if absence_dir.exists():
                shutil.rmtree(absence_dir)

        # Set all P1 test suites to PLANNED (tasks are now OPEN)
        for suite in self.data["test-catalog"]["suites"]:
            if suite["task_id"] in P1_TASKS:
                suite["status"] = "PLANNED"
                suite["execution_evidence"] = []

        # Clear P1 ADR decision records that point to removed execution packets
        for decision in self.data["decision-register"]["decisions"]:
            if decision["id"] in ("ADR-002", "ADR-003", "ADR-004"):
                # ADR-001 is in V2-001 (P0, not removed)
                # ADR-002 is in V2-061, ADR-003 in V2-007, ADR-004 in V2-008 (all removed in fixture)
                decision["status"] = "REQUIRED"
                decision["decision_record"] = None

        # Remove historical closure_refs from findings (they point to excluded validation/closure/)
        # Change CLOSED findings to OPEN since they no longer have closure evidence
        for finding in self.data["remediation-register"]["findings"]:
            if finding.get("status") == "CLOSED":
                finding["status"] = "OPEN_TRACKED"
            finding["closure_refs"] = []

        self.make_p0()

        # Write modified data back to disk for CLI tests
        for name in validator.NAMES:
            (self.plan / "machine" / f"{name}.yaml").write_text(
                yaml.safe_dump(self.data[name], allow_unicode=True, sort_keys=False)
            )

        # Remove references to excluded validation/closure/ from README
        readme_path = self.plan / "README.md"
        if readme_path.exists():
            readme_content = readme_path.read_text()
            # Remove the markdown link to validation/closure/
            readme_content = readme_content.replace(
                "[G-P0 出口审核](validation/closure/G-P0-38b0c57/)", "G-P0 出口审核"
            )
            readme_path.write_text(readme_content)

        self.assertEqual(
            self.errors(), [], "Positive evidence fixture must be valid before mutation"
        )

    def record(self, kind, subject, **extra):
        ref = f"validation/fixture/{kind}-{subject}.json"
        obj = {
            "record_type": "plan_execution_evidence",
            "schema_version": "1.0",
            "evidence_id": kind + "-" + subject,
            "evidence_type": kind,
            "subject_id": subject,
            "revision": REVISION,
            "status": "PASS",
            "producer": "isolated unit-test fixture",
            "executed_at": "2026-09-21T00:00:00Z",
            "environment_fingerprint": "synthetic-test-only",
            "artifacts": [deepcopy(self.artifact)],
            "input_evidence_refs": [],
        }
        if kind in {"TEST_RESULT", "CI_RUN"}:
            obj.update(
                command="synthetic fixture; no real execution claimed",
                exit_code=0,
                check_ids=["fixture"],
            )
        if kind == "CI_RUN":
            obj.update(
                pipeline_id="fixture-pipeline",
                job_id="fixture-job",
                pipeline_url="https://ci.example.invalid/fixture",
            )
        if kind in {
            "ACCEPTANCE_RECORD",
            "ADR_DECISION",
            "PHASE_DECISION",
            "MILESTONE_DECISION",
            "FINDING_CLOSURE",
        }:
            obj.update(
                decision={
                    "PHASE_DECISION": "VERIFIED",
                    "MILESTONE_DECISION": "VERIFIED",
                    "FINDING_CLOSURE": "CLOSED",
                }.get(kind, "ACCEPTED"),
                rationale="Synthetic positive control; not a real task closure",
            )
        obj.update(extra)
        (self.plan / ref).write_text(json.dumps(obj) + "\n")
        return ref

    def make_p0(self):
        for t in self.data["implementation-backlog"]["tasks"][:4]:
            tid = t["task_id"]
            suite = next(
                s for s in self.data["test-catalog"]["suites"] if s["task_id"] == tid
            )
            ids = [s["id"] for s in suite["scenarios"]]
            refs = {
                kind: self.record(
                    typ, tid, **({"check_ids": ids} if kind == "tests" else {})
                )
                for kind, typ in [
                    ("code", "CODE"),
                    ("tests", "TEST_RESULT"),
                    ("ci", "CI_RUN"),
                ]
            }
            dispositions = [
                {
                    "finding_id": fid,
                    "responsibility": "FULL",
                    "disposition": "RESOLVED",
                    "evidence_refs": [refs["tests"]],
                    "reason": "Only this task obligation is covered by the synthetic fixture",
                }
                for fid in t["related_findings"]
            ]
            external = [
                {
                    "practice_id": x,
                    "adoption_mode": "independent fixture",
                    "source_version_note": "fixture only",
                    "verification_refs": [refs["tests"]],
                    "conclusion": "no runtime claim",
                    "limitations": "isolated test",
                }
                for x in t.get("external_practices", [])
            ]
            refs["acceptance"] = self.record(
                "ACCEPTANCE_RECORD",
                tid,
                input_evidence_refs=list(refs.values()),
                check_ids=ids,
                finding_dispositions=dispositions,
                external_practice_results=external,
            )
            t.update(
                status="CLOSED",
                evidence={
                    kind: [{"ref": ref, "revision": REVISION, "status": "PASS"}]
                    for kind, ref in refs.items()
                },
            )
            suite.update(status="VERIFIED", execution_evidence=[refs["tests"]])
            for a in self.data["decision-register"]["decisions"]:
                if a["id"] in t["required_decisions"]:
                    a.update(
                        status="ACCEPTED",
                        decision_record=self.record("ADR_DECISION", a["id"]),
                    )
            self.make_packet(t)
        gates = [
            g for g in self.data["ci-gates"]["gates"] if g["activation_phase"] == "P0"
        ]
        ci = self.record("CI_RUN", "P0", check_ids=[g["id"] for g in gates])
        for g in gates:
            g.update(status="VERIFIED", evidence_refs=[ci])
        accepts = [
            t["evidence"]["acceptance"][0]["ref"]
            for t in self.data["implementation-backlog"]["tasks"][:4]
        ]
        phase = self.record(
            "PHASE_DECISION",
            "P0",
            input_evidence_refs=accepts + [ci],
            ci_evidence_refs=[ci],
        )
        self.data["phase-gates"]["phases"][0].update(
            status="VERIFIED", evidence_refs=[phase]
        )
        self.data["milestones"]["milestones"][0].update(
            status="VERIFIED",
            evidence_refs=[
                self.record(
                    "MILESTONE_DECISION", "M0", input_evidence_refs=accepts + [phase]
                )
            ],
        )

    def errors(self):
        return (
            validator.validate_objects(self.data)
            + evidence_checks(self.data, self.plan)
            + execution_checks(self.data, self.plan)
        )

    def make_packet(self, task, action="IMPLEMENT"):
        """Synthetic inputs in the disposable test tree; never real task evidence."""
        inputs = []
        for index, ref in enumerate(
            dict.fromkeys(task["normative_specs"] + list(CONTROL_INPUTS))
        ):
            original = self.plan / ref
            # Required normative/control inputs must never disappear silently
            if not original.exists():
                raise FileNotFoundError(
                    f"Required input missing from test fixture: {ref}\n"
                    f"Fixture setup must copy all required normative/control inputs."
                )
            snapshot = self.records / f"{task['task_id']}-input-{index}.txt"
            snapshot.write_bytes(original.read_bytes())
            inputs.append(
                {
                    "source_ref": ref,
                    "ref": str(snapshot.relative_to(self.plan)),
                    "sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                }
            )
        packet = {
            "record_type": "task_execution_packet",
            "schema_version": "1.0",
            "task_id": task["task_id"],
            "plan_version": self.data["implementation-backlog"]["version"],
            "repository_revision": REVISION,
            "worktree_dirty": False,
            "plan_manifest_sha256": validator.sha(self.plan / "FILE_MANIFEST.json"),
            "environment": {
                "fingerprint": "synthetic-only",
                "runtime_versions": {"test": "synthetic"},
                "database_image": None,
                "ci_context": None,
            },
            "implementer": "synthetic implementer",
            "verifier": "synthetic verifier",
            "owner_role": task["owner_role"],
            "scope": "isolated positive test fixture",
            "action": action,
            "inputs": inputs,
            "expected_outputs": task["artifacts"][:],
            "allowed_paths": task["artifacts"][:],
            "required_decisions": task["required_decisions"][:],
            "claims": [],
            "estimate": {
                "range": None,
                "unit": None,
                "assumptions": [],
                "confidence": "NOT_ESTIMATED",
            },
            "budget": {
                "paid_calls_allowed": False,
                "model_cost_cap": None,
                "infrastructure_cap": None,
                "maximum_attempts": 1,
                "maximum_runtime": 60,
            },
            "stop_conditions": ["synthetic-only; no real actions"],
            "review_notes": [],
            "handoff": {
                "current_step": "isolated fixture",
                "completed_steps": [],
                "pending_items": [],
                "next_action": action,
                "last_check": {
                    "status": "NOT_RUN",
                    "artifacts": [],
                    "missing_artifact_reason": None,
                },
            },
        }
        ref = f"validation/fixture/PACKET-{task['task_id']}.json"
        (self.plan / ref).write_text(json.dumps(packet, ensure_ascii=False) + "\n")
        task["execution_packet_ref"] = ref
        return packet

    def reject(self, prefix):
        errors = self.errors()
        self.assertTrue(any(e.startswith(prefix) for e in errors), (prefix, errors))

    def mutate_record(self, kind, subject, mutate):
        path = self.records / f"{kind}-{subject}.json"
        record = json.loads(path.read_text())
        mutate(record)
        path.write_text(json.dumps(record) + "\n")

    def test_valid_p0_completion_chain(self):
        self.assertEqual(self.errors(), [])

    def test_valid_partial_finding_disposition(self):
        self.mutate_record(
            "ACCEPTANCE_RECORD",
            "V2-002",
            lambda r: r["finding_dispositions"][0].update(
                responsibility="PARTIAL",
                disposition="PARTIALLY_RESOLVED",
                remaining_work="later scope",
                next_task="V2-005",
                owner_role="domain-maintainer",
                due_gate="G-P1",
            ),
        )
        self.assertEqual(self.errors(), [])

    def test_valid_future_task_start(self):
        task = self.data["implementation-backlog"]["tasks"][4]
        task.update(status="IN_PROGRESS", readiness="READY_AFTER_GATES")
        self.make_packet(task, "PREPARE")
        self.assertEqual(self.errors(), [])

    def test_valid_multiple_suites_for_one_task(self):
        task = self.data["implementation-backlog"]["tasks"][0]
        extra = deepcopy(self.data["test-catalog"]["suites"][0])
        extra["id"] = "AT-V2-001-EXTRA"
        extra["scenarios"] = [
            {
                "id": "AT-V2-001-EXTRA-01",
                "required_assertion": "additional isolated assertion",
            }
        ]
        self.data["test-catalog"]["suites"].append(extra)
        task["tests"].append(extra["id"])
        task["acceptance_criteria"].append(extra["scenarios"][0]["required_assertion"])
        for kind in ("TEST_RESULT", "ACCEPTANCE_RECORD"):
            self.mutate_record(
                kind, "V2-001", lambda r: r["check_ids"].append("AT-V2-001-EXTRA-01")
            )
        self.assertEqual(self.errors(), [])

    def test_all_ci_removed(self):
        self.data["ci-gates"]["gates"] = []
        self.reject("CI_BASELINE")

    def test_ci_postponed(self):
        self.data["ci-gates"]["gates"][0]["activation_phase"] = "P14"
        self.reject("CI_BASELINE")

    def test_ci_checks_removed(self):
        self.data["ci-gates"]["gates"][0]["checks"] = []
        self.reject("CI_BASELINE")

    def test_ci_duplicate(self):
        self.data["ci-gates"]["gates"].append(
            deepcopy(self.data["ci-gates"]["gates"][0])
        )
        self.reject("CI_BASELINE")

    def test_missing_suite_file(self):
        self.data["test-catalog"]["suites"][0]["execution_evidence"] = [
            "validation/absent.json"
        ]
        self.reject("EVIDENCE_RECORD")

    def test_missing_phase_file(self):
        self.data["phase-gates"]["phases"][0]["evidence_refs"] = [
            "validation/absent.json"
        ]
        self.reject("EVIDENCE_RECORD")

    def test_readme_not_test_record(self):
        self.data["test-catalog"]["suites"][0]["execution_evidence"] = ["README.md"]
        self.reject("EVIDENCE_RECORD")

    def test_directory_not_record(self):
        self.data["test-catalog"]["suites"][0]["execution_evidence"] = ["validation"]
        self.reject("EVIDENCE_RECORD")

    def test_adr_template_not_decision(self):
        self.data["decision-register"]["decisions"][0]["decision_record"] = (
            "templates/ADR.md"
        )
        self.reject("EVIDENCE_RECORD")

    def test_template_artifact_cannot_support_decision(self):
        template = self.plan / "templates/ADR.md"
        self.mutate_record(
            "ADR_DECISION",
            "ADR-001",
            lambda r: r.update(
                artifacts=[
                    {
                        "ref": "templates/ADR.md",
                        "sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
                    }
                ]
            ),
        )
        self.reject("EVIDENCE_ARTIFACT")

    def test_normalized_template_aliases_are_rejected(self):
        template = self.plan / "templates/ADR.md"
        link = self.records / "template-link.md"
        link.symlink_to(template)
        for ref in (
            "./templates/ADR.md",
            "validation/../templates/ADR.md",
            "validation/fixture/template-link.md",
        ):
            with self.subTest(ref=ref):
                self.mutate_record(
                    "ADR_DECISION",
                    "ADR-001",
                    lambda r: r.update(
                        artifacts=[
                            {
                                "ref": ref,
                                "sha256": hashlib.sha256(
                                    template.read_bytes()
                                ).hexdigest(),
                            }
                        ]
                    ),
                )
                self.reject("EVIDENCE_ARTIFACT")

    def test_valid_artifact_in_nested_templates_named_directory(self):
        artifact = self.records / "templates/result.txt"
        artifact.parent.mkdir()
        artifact.write_text("Synthetic execution result; not a plan template")
        self.mutate_record(
            "ADR_DECISION",
            "ADR-001",
            lambda r: r.update(
                artifacts=[
                    {
                        "ref": str(artifact.relative_to(self.plan)),
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    }
                ]
            ),
        )
        self.assertEqual(self.errors(), [])

    def test_milestone_shrink(self):
        self.data["milestones"]["milestones"][6]["required_tasks"] = ["V2-001"]
        self.reject("MILESTONE_BASELINE")

    def test_milestone_requires_phase(self):
        self.data["phase-gates"]["phases"][0]["status"] = "NOT_VERIFIED"
        self.reject("MILESTONE_PHASE")

    def test_milestone_revision_matches_phase_decision(self):
        self.mutate_record(
            "MILESTONE_DECISION", "M0", lambda r: r.update(revision="b" * 40)
        )
        self.reject("EVIDENCE_REVISION")

    def test_valid_historical_task_revision_in_current_phase(self):
        task = self.data["implementation-backlog"]["tasks"][0]
        for pointers in task["evidence"].values():
            for pointer in pointers:
                pointer["revision"] = "b" * 40
                path = self.plan / pointer["ref"]
                record = json.loads(path.read_text())
                record["revision"] = "b" * 40
                path.write_text(json.dumps(record) + "\n")
        self.assertEqual(self.errors(), [])

    def test_adr_backlink_removed(self):
        self.data["implementation-backlog"]["tasks"][0]["required_decisions"] = []
        self.reject("ADR_BACKLINK")

    def test_finding_backlink_removed(self):
        self.data["implementation-backlog"]["tasks"][1]["related_findings"] = []
        self.reject("FINDING_BACKLINK")

    def test_planned_readiness_cannot_start(self):
        self.data["implementation-backlog"]["tasks"][6]["status"] = "IN_PROGRESS"
        self.reject("TASK_READINESS")

    def test_p0_blocked(self):
        self.data["phase-gates"]["entry_gate"]["status"] = "BLOCKED"
        self.reject("ENTRY_GATE")

    def test_missing_finding_disposition(self):
        self.mutate_record(
            "ACCEPTANCE_RECORD", "V2-002", lambda r: r.update(finding_dispositions=[])
        )
        self.reject("FINDING_DISPOSITION")

    def test_partial_finding_requires_next_owner(self):
        self.mutate_record(
            "ACCEPTANCE_RECORD",
            "V2-002",
            lambda r: r["finding_dispositions"][0].update(disposition="TRANSFERRED"),
        )
        self.reject("EVIDENCE_RECORD")

    def test_wrong_evidence_type(self):
        self.data["test-catalog"]["suites"][0]["execution_evidence"] = [
            "validation/fixture/CODE-V2-001.json"
        ]
        self.reject("EVIDENCE_TYPE")

    def test_wrong_subject(self):
        self.mutate_record(
            "TEST_RESULT", "V2-001", lambda r: r.update(subject_id="V2-002")
        )
        self.reject("EVIDENCE_SUBJECT")

    def test_wrong_revision(self):
        self.mutate_record(
            "TEST_RESULT", "V2-001", lambda r: r.update(revision="b" * 40)
        )
        self.reject("EVIDENCE_REVISION")

    def test_bad_artifact_hash(self):
        self.mutate_record(
            "TEST_RESULT", "V2-001", lambda r: r["artifacts"][0].update(sha256="0" * 64)
        )
        self.reject("EVIDENCE_ARTIFACT")

    def test_suite_coverage_not_just_nonempty(self):
        self.mutate_record(
            "TEST_RESULT",
            "V2-001",
            lambda r: r.update(check_ids=["not-a-real-scenario"]),
        )
        self.reject("EVIDENCE_COVERAGE")

    def test_failed_run_rejected(self):
        self.mutate_record("CI_RUN", "V2-001", lambda r: r.update(exit_code=1))
        self.reject("EVIDENCE_RECORD")

    def test_runtime_failure_states_are_not_closure_witnesses(self):
        path = self.records / "CI_RUN-V2-001.json"
        original = json.loads(path.read_text())
        for status in ("FAIL", "ERROR", "UNKNOWN", "BLOCKED"):
            with self.subTest(status=status):
                record = deepcopy(original)
                record["status"] = status
                path.write_text(json.dumps(record) + "\n")
                self.reject("EVIDENCE_RECORD")

    def test_cli_external_reports_do_not_change_plan(self):
        def inventory():
            return {
                str(p.relative_to(self.plan)): hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
                for p in self.plan.rglob("*")
                if p.is_file()
            }

        # Generate views and manifest first
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.plan / "scripts/validate_plan.py"),
                "--write-views",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        before = inventory()
        reports = Path(self.tmp.name) / "dist/validation/job-1"
        for mode, name in [
            ("--check", "plan-validation.json"),
            ("--self-test", "validator-self-test.json"),
        ]:
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(self.plan / "scripts/validate_plan.py"),
                    mode,
                    "--output-dir",
                    str(reports),
                ],
                capture_output=True,
                text=True,
            )
            # Clean positive fixture must validate successfully
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((reports / name).read_text())
            self.assertEqual(
                report["status"],
                "PASS",
                f"Clean fixture must pass: {report.get('errors', [])}",
            )
        self.assertEqual(before, inventory())

    def test_phase_requires_applicable_ci(self):
        self.mutate_record("CI_RUN", "P0", lambda r: r.update(check_ids=["STATIC"]))
        self.reject("EVIDENCE_COVERAGE")

    def test_phase_input_binding(self):
        self.mutate_record(
            "PHASE_DECISION",
            "P0",
            lambda r: r.update(
                input_evidence_refs=["validation/fixture/CI_RUN-P0.json"]
            ),
        )
        self.reject("PHASE_INPUTS")

    def test_evidence_cycle(self):
        self.mutate_record(
            "TEST_RESULT",
            "V2-001",
            lambda r: r.update(
                input_evidence_refs=["validation/fixture/TEST_RESULT-V2-001.json"]
            ),
        )
        self.reject("EVIDENCE_CYCLE")

    def test_source_registry_does_not_claim_fresh_verification(self):
        self.data["foundational-reference-register"]["references"][0][
            "verification_status"
        ] = "VERIFIED"
        self.reject("FOUNDATION_EVIDENCE")

    def test_valid_exported_cli_and_single_negative(self):
        for name in validator.NAMES:
            (self.plan / "machine" / f"{name}.yaml").write_text(
                yaml.safe_dump(self.data[name], allow_unicode=True, sort_keys=False)
            )
        # Explicit generation is allowed for intended changes; it must not weaken semantic checks.
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.plan / "scripts/validate_plan.py"),
                "--write-views",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.plan / "scripts/validate_plan.py"),
                "--check",
            ],
            capture_output=True,
            text=True,
        )
        # After write-views, clean positive fixture must validate successfully
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(
            report["status"],
            "PASS",
            f"Clean fixture must pass after write-views: {report.get('errors', [])}",
        )

        # Now introduce a deliberate negative mutation
        gates = self.data["ci-gates"]
        gates["gates"] = []
        (self.plan / "machine/ci-gates.yaml").write_text(yaml.safe_dump(gates))
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.plan / "scripts/validate_plan.py"),
                "--check",
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(
            any(
                e.startswith("CI_BASELINE") for e in json.loads(result.stdout)["errors"]
            )
        )

    def test_phase_decision_revision_identifies_verified_candidate(self):
        """Phase decision revision identifies the candidate that was verified by CI,
        even when the decision record is written in a later commit."""
        # The phase decision revision points to the verified candidate
        phase_record_path = next(
            (self.plan / "validation/fixture").glob("*PHASE_DECISION*P0*.json")
        )
        phase_record = json.loads(phase_record_path.read_text())

        # Verify the phase decision revision matches the CI_RUN revision
        ci_ref = phase_record["ci_evidence_refs"][0]
        ci_path = self.plan / ci_ref
        ci_record = json.loads(ci_path.read_text())

        # Both should identify the same candidate revision that was verified
        self.assertEqual(
            phase_record["revision"],
            ci_record["revision"],
            "PHASE_DECISION.revision must match CI_RUN.revision (the verified candidate)",
        )

        # Milestone decision should also use the same verified candidate revision
        milestone_record_path = next(
            (self.plan / "validation/fixture").glob("*MILESTONE_DECISION*M0*.json")
        )
        milestone_record = json.loads(milestone_record_path.read_text())

        self.assertEqual(
            milestone_record["revision"],
            phase_record["revision"],
            "MILESTONE_DECISION.revision must match PHASE_DECISION.revision",
        )

        # All point to the same verified candidate
        self.assertEqual(phase_record["revision"], REVISION)
        self.assertEqual(ci_record["revision"], REVISION)
        self.assertEqual(milestone_record["revision"], REVISION)

    def test_absence_record_not_allowed_for_active_tasks(self):
        """Execution packet absence records must only be used for CLOSED historical tasks,
        not as a bypass for OPEN/IN_PROGRESS/IMPLEMENTED tasks."""
        # Create an absence record for an OPEN task (should fail)
        tasks = self.data["implementation-backlog"]["tasks"]
        # Pick an OPEN task that is NOT V2-005/V2-006 (those are grandfathered)
        open_task = next(
            t
            for t in tasks
            if t["status"] == "OPEN" and t["task_id"] not in ("V2-005", "V2-006")
        )
        tid = open_task["task_id"]

        absence_record = self.records / f"absence-{tid}.yaml"
        absence_record.write_text(f"""record_type: execution_packet_absence_record
schema_version: '1.0'
task_id: {tid}
closure_revision: {"a" * 40}
closure_tag: fake-tag
registration_context: test
reason: Testing absence record bypass prevention
evidence_refs:
- type: implementation
  ref: src/fake.py
""")

        # Point the OPEN task at the absence record
        open_task["execution_packet_ref"] = f"validation/fixture/absence-{tid}.yaml"

        # This should produce EXEC_ABSENCE_NOT_GRANDFATHERED error
        errors = execution_checks(self.data, self.plan)
        self.assertTrue(
            any(f"EXEC_ABSENCE_NOT_GRANDFATHERED {tid}" in e for e in errors),
            f"Absence record should be rejected for non-grandfathered task {tid}",
        )

    def test_absence_record_only_for_grandfathered_tasks(self):
        """Only V2-005 and V2-006 may use absence records (explicit grandfathering)."""
        tasks = self.data["implementation-backlog"]["tasks"]

        # Find a future CLOSED task (or create one)
        v2_007 = next((t for t in tasks if t["task_id"] == "V2-007"), None)
        if v2_007:
            # Temporarily mark as CLOSED for this test
            original_status = v2_007["status"]
            v2_007["status"] = "CLOSED"

            absence_record = self.records / "absence-V2-007.yaml"
            absence_record.write_text("""record_type: execution_packet_absence_record
schema_version: '1.0'
task_id: V2-007
closure_revision: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
closure_tag: fake-v2-007-complete
registration_context: test
reason: Testing future task bypass prevention
evidence_refs:
- type: implementation
  ref: src/fake.py
""")

            v2_007["execution_packet_ref"] = "validation/fixture/absence-V2-007.yaml"

            errors = execution_checks(self.data, self.plan)
            self.assertTrue(
                any("EXEC_ABSENCE_NOT_GRANDFATHERED V2-007" in e for e in errors),
                "V2-007 should not be allowed to use absence record (not grandfathered)",
            )

            # Restore
            v2_007["status"] = original_status

    def test_absence_record_wrong_closure_sha_rejected(self):
        """Absence record with wrong closure SHA must be rejected."""
        tasks = self.data["implementation-backlog"]["tasks"]
        v2_005 = next(t for t in tasks if t["task_id"] == "V2-005")

        # Set task to CLOSED status (required for absence record validation)
        v2_005["status"] = "CLOSED"

        # Create absence record with wrong SHA
        absence_record = self.records / "absence-V2-005-wrong.yaml"
        absence_record.write_text("""record_type: execution_packet_absence_record
schema_version: '1.0'
task_id: V2-005
closure_revision: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
closure_tag: v2.005-complete
registration_context: test
reason: Testing wrong SHA rejection
evidence_refs:
- type: implementation
  ref: src/fake.py
""")

        original_ref = v2_005.get("execution_packet_ref")
        v2_005["execution_packet_ref"] = "validation/fixture/absence-V2-005-wrong.yaml"

        errors = execution_checks(self.data, self.plan)
        self.assertTrue(
            any(
                "EXEC_ABSENCE_IDENTITY V2-005" in e and "closure_revision" in e
                for e in errors
            ),
            "Wrong closure_revision should be rejected",
        )

        # Restore
        if original_ref:
            v2_005["execution_packet_ref"] = original_ref

    def test_absence_record_wrong_tag_rejected(self):
        """Absence record with wrong closure tag must be rejected."""
        tasks = self.data["implementation-backlog"]["tasks"]
        v2_006 = next(t for t in tasks if t["task_id"] == "V2-006")

        # Set task to CLOSED status (required for absence record validation)
        v2_006["status"] = "CLOSED"

        # Create absence record with wrong tag
        absence_record = self.records / "absence-V2-006-wrong.yaml"
        absence_record.write_text("""record_type: execution_packet_absence_record
schema_version: '1.0'
task_id: V2-006
closure_revision: bba1061ef27669ece55530bfdd846767b2fe21af
closure_tag: wrong-tag
registration_context: test
reason: Testing wrong tag rejection
evidence_refs:
- type: implementation
  ref: src/fake.py
""")

        original_ref = v2_006.get("execution_packet_ref")
        v2_006["execution_packet_ref"] = "validation/fixture/absence-V2-006-wrong.yaml"

        errors = execution_checks(self.data, self.plan)
        self.assertTrue(
            any(
                "EXEC_ABSENCE_IDENTITY V2-006" in e and "closure_tag" in e
                for e in errors
            ),
            "Wrong closure_tag should be rejected",
        )

        # Restore
        if original_ref:
            v2_006["execution_packet_ref"] = original_ref

    def test_grandfathered_absence_records_valid(self):
        """V2-005 and V2-006 with correct absence records should produce EXEC_PACKET_ABSENT only."""
        # This test verifies that properly configured grandfathered absence records
        # are accepted structurally and produce the expected EXEC_PACKET_ABSENT finding

        # Set up V2-005 and V2-006 as CLOSED with valid absence records
        self._setup_absence_record_tasks()

        errors = execution_checks(self.data, self.plan)

        # Should have EXEC_PACKET_ABSENT findings
        v2_005_absent = [e for e in errors if "EXEC_PACKET_ABSENT V2-005" in e]
        v2_006_absent = [e for e in errors if "EXEC_PACKET_ABSENT V2-006" in e]

        self.assertEqual(
            len(v2_005_absent),
            1,
            "V2-005 should have exactly one EXEC_PACKET_ABSENT finding",
        )
        self.assertEqual(
            len(v2_006_absent),
            1,
            "V2-006 should have exactly one EXEC_PACKET_ABSENT finding",
        )

        # Should NOT have bypass/identity errors for grandfathered tasks
        v2_005_bypass = [
            e
            for e in errors
            if "V2-005" in e
            and ("BYPASS" in e or "NOT_GRANDFATHERED" in e or "IDENTITY" in e)
        ]
        v2_006_bypass = [
            e
            for e in errors
            if "V2-006" in e
            and ("BYPASS" in e or "NOT_GRANDFATHERED" in e or "IDENTITY" in e)
        ]

        self.assertEqual(
            len(v2_005_bypass),
            0,
            "V2-005 should not have bypass/identity errors with valid absence record",
        )
        self.assertEqual(
            len(v2_006_bypass),
            0,
            "V2-006 should not have bypass/identity errors with valid absence record",
        )

    def _setup_absence_record_tasks(self):
        """Set up V2-005/V2-006 as CLOSED with valid absence records for testing."""
        tasks = self.data["implementation-backlog"]["tasks"]
        for task_id in ("V2-005", "V2-006"):
            task = next(t for t in tasks if t["task_id"] == task_id)
            task["status"] = "CLOSED"

            # Create minimal synthetic evidence
            code_ref = self.record("CODE", task_id)
            tests_ref = self.record("TEST_RESULT", task_id)
            ci_ref = self.record("CI_RUN", task_id)
            acceptance_ref = self.record(
                "ACCEPTANCE_RECORD",
                task_id,
                input_evidence_refs=[code_ref, tests_ref, ci_ref],
                check_ids=[],
                finding_dispositions=[],
                external_practice_results=[],
            )

            task["evidence"] = {
                "code": [{"ref": code_ref, "revision": REVISION, "status": "PASS"}],
                "tests": [{"ref": tests_ref, "revision": REVISION, "status": "PASS"}],
                "ci": [{"ref": ci_ref, "revision": REVISION, "status": "PASS"}],
                "acceptance": [
                    {"ref": acceptance_ref, "revision": REVISION, "status": "PASS"}
                ],
            }

            # Create valid absence record
            absence_path = (
                self.plan
                / f"validation/execution/{task_id}/execution-packet-absent.yaml"
            )
            absence_record = {
                "record_type": "execution_packet_absence_record",
                "schema_version": "1.0",
                "task_id": task_id,
                "closure_revision": "bd303e64dab6475bd12b69d273afa6c64eaa38ad"
                if task_id == "V2-005"
                else "bba1061ef27669ece55530bfdd846767b2fe21af",
                "closure_tag": f"v2.{'005' if task_id == 'V2-005' else '006'}-complete",
                "registration_context": "test fixture",
                "reason": f"{task_id} closed before execution packet framework.",
                "evidence_refs": [
                    {"type": "implementation", "ref": code_ref, "note": "Test fixture"}
                ],
            }
            absence_path.parent.mkdir(parents=True, exist_ok=True)
            absence_path.write_text(
                yaml.safe_dump(absence_record, allow_unicode=True, sort_keys=False)
            )
            task["execution_packet_ref"] = str(absence_path.relative_to(self.plan))

    def test_grandfathered_but_active_status_rejected(self):
        """Grandfathered task (V2-005) with valid absence record but active status must be rejected."""
        # Set up V2-005 with valid absence record first
        self._setup_absence_record_tasks()

        tasks = self.data["implementation-backlog"]["tasks"]
        v2_005 = next(t for t in tasks if t["task_id"] == "V2-005")

        # V2-005 is grandfathered and has correct closure_revision/tag in absence record
        # But if status is not CLOSED, it should still be rejected
        original_status = v2_005["status"]
        v2_005["status"] = "OPEN"

        errors = execution_checks(self.data, self.plan)
        self.assertTrue(
            any("EXEC_ABSENCE_BYPASS V2-005" in e for e in errors),
            "Grandfathered task with OPEN status should be rejected with EXEC_ABSENCE_BYPASS",
        )

        # Try IN_PROGRESS as well
        v2_005["status"] = "IN_PROGRESS"
        errors = execution_checks(self.data, self.plan)
        self.assertTrue(
            any("EXEC_ABSENCE_BYPASS V2-005" in e for e in errors),
            "Grandfathered task with IN_PROGRESS status should be rejected with EXEC_ABSENCE_BYPASS",
        )

        # Restore
        v2_005["status"] = original_status


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({"case": test.id(), "status": "PASS"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append({"case": test.id(), "status": "FAIL"})

    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append({"case": test.id(), "status": "ERROR"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=validator.PLAN / "validation"
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GovernanceTests)
    result: RecordedResult = unittest.TextTestRunner(
        verbosity=2, resultclass=RecordedResult
    ).run(suite)  # type: ignore[assignment]
    report = {
        "scope": "Planning governance regressions in disposable copies; synthetic records are not runtime evidence",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_sha256": validator.sha(validator.PLAN / "FILE_MANIFEST.json"),
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "test_count": result.testsRun,
        "cases": result.cases,
    }
    (args.output_dir / "governance-regression.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    sys.exit(0 if result.wasSuccessful() else 1)
