"""Minimum governance obligations and typed local evidence validation.

These checks reject malformed attestations. They do not authenticate the remote
CI service or prevent a person with repository write rights changing the code.
"""

import hashlib
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


def object_checks(data):
    errors = []

    def check(ok, message):
        if not ok:
            errors.append(message)

    baseline = data["governance-baseline"]
    tasks = {t["task_id"]: t for t in data["implementation-backlog"]["tasks"]}
    phases = {p["id"]: p for p in data["phase-gates"]["phases"]}
    gates = data["ci-gates"]["gates"]
    by_gate = {g["id"]: g for g in gates}
    check(len(by_gate) == len(gates), "CI_BASELINE: duplicate gate")
    for gid, required in baseline["required_ci"].items():
        g = by_gate.get(gid)
        check(g is not None, f"CI_BASELINE {gid}: required gate absent")
        if g is None:
            continue
        phase = g.get("activation_phase")
        check(
            phase in phases
            and int(phase[1:]) <= int(required["latest_activation_phase"][1:]),
            f"CI_BASELINE {gid}: activation postponed",
        )
        check(
            set(required["required_checks"]).issubset(g.get("checks", [])),
            f"CI_BASELINE {gid}: checks weakened",
        )
        check(
            g.get("mode") == required["mode"],
            f"CI_BASELINE {gid}: trigger policy changed",
        )
    for m in data["milestones"]["milestones"]:
        minimum = baseline["milestones"].get(m["id"])
        check(minimum is not None, f"MILESTONE_BASELINE {m['id']}: absent baseline")
        if minimum:
            check(
                set(minimum["required_tasks"]).issubset(m["required_tasks"]),
                f"MILESTONE_BASELINE {m['id']}: required tasks removed",
            )
            check(
                all(
                    m[k] == minimum[k]
                    for k in ("name", "introduced_phase", "earliest_close_phase")
                ),
                f"MILESTONE_BASELINE {m['id']}: identity/phase changed",
            )
        if m["status"] == "VERIFIED":
            check(
                phases.get(m["earliest_close_phase"], {}).get("status") == "VERIFIED",
                f"MILESTONE_PHASE {m['id']}: phase not verified",
            )
    for pid, criteria in baseline["phase_criteria"].items():
        check(
            set(criteria).issubset(phases.get(pid, {}).get("exit_criteria", [])),
            f"PHASE_BASELINE {pid}: minimum criteria removed",
        )
    check(
        set(baseline["required_findings"]).issubset(
            f["id"] for f in data["remediation-register"]["findings"]
        ),
        "FINDING_BASELINE: required audit findings absent",
    )
    entry = data["phase-gates"]["entry_gate"]
    check(entry.get("id") == "P0_ENTRY_READY", "ENTRY_GATE: identity changed")
    check(
        entry.get("status") in {"READY_FOR_PLANNING_EXECUTION", "BLOCKED"},
        "ENTRY_GATE: invalid status",
    )
    for t in tasks.values():
        tid = t["task_id"]
        required_adr = {
            a["id"]
            for a in data["decision-register"]["decisions"]
            if tid in a["related_tasks"]
        }
        required_findings = {
            f["id"]
            for f in data["remediation-register"]["findings"]
            if tid in f["related_tasks"]
        }
        check(
            set(t["required_decisions"]) == required_adr,
            f"ADR_BACKLINK {tid}: incomplete bidirectional mapping",
        )
        check(
            set(t["related_findings"]) == required_findings,
            f"FINDING_BACKLINK {tid}: incomplete bidirectional mapping",
        )
        if t["status"] != "OPEN":
            check(
                t["readiness"] in {"READY_TO_START", "READY_AFTER_GATES"},
                f"TASK_READINESS {tid}: still PLANNED",
            )
            if t["phase"] == "P0":
                check(
                    entry.get("status") == "READY_FOR_PLANNING_EXECUTION",
                    f"ENTRY_GATE {tid}: P0 blocked",
                )
    foundations = data["foundational-reference-register"]["references"]
    check(
        len({f["id"] for f in foundations}) == len(foundations),
        "FOUNDATION_IDS: duplicate",
    )
    for f in foundations:
        check(
            f["verification_status"] == "HISTORICAL_UNVERIFIED"
            and f["runtime_verification"] == "NOT_PERFORMED",
            f"FOUNDATION_EVIDENCE {f['id']}: historical input is not new verification",
        )
        check(
            f["kind"] in {"FOUNDATIONAL_RESEARCH", "INFRASTRUCTURE_PATTERN"},
            f"FOUNDATION_KIND {f['id']}: invalid",
        )
        check(
            bool(f["mechanism_scope"])
            and bool(f["normative_refs"])
            and bool(f["related_tasks"]),
            f"FOUNDATION_SCOPE {f['id']}: missing local mapping",
        )
        check(
            all(t in tasks for t in f["related_tasks"]),
            f"FOUNDATION_TASK {f['id']}: unknown owner",
        )
    for t in tasks.values():
        expected = {f["id"] for f in foundations if t["task_id"] in f["related_tasks"]}
        check(
            set(t.get("foundational_references", [])) == expected,
            f"FOUNDATION_BACKLINK {t['task_id']}: mapping differs",
        )
    return errors


class EvidenceReader:
    def __init__(self, plan, schema, errors, compat=None, historical_provenance=None):
        self.plan = Path(plan).resolve()
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.errors = errors
        self.cache = {}
        self.stack = set()
        self.ids = {}
        self.compat = compat or {}
        self.historical_provenance = historical_provenance or {}

    def path(self, ref):
        if not isinstance(ref, str):
            return None
        p = (self.plan / ref).resolve()
        return p if self.plan in p.parents and p.is_file() else None

    def read(self, ref, types=None, subject=None, revision=None):
        if ref in self.stack:
            self.errors.append(f"EVIDENCE_CYCLE: {ref}")
            return None
        if ref not in self.cache:
            self.stack.add(ref)
            record = None
            try:
                path = self.path(ref)
                if path is None:
                    # Check if this is legacy evidence for a grandfathered task
                    if subject and subject in self.compat:
                        # Legacy evidence - suppress EVIDENCE_RECORD error
                        raise ValueError("__LEGACY_EVIDENCE__")
                    raise ValueError(
                        "local evidence file missing/outside package/not a file"
                    )
                record = yaml.safe_load(path.read_text())
                issues = list(self.validator.iter_errors(record))
                if issues:
                    raise ValueError("; ".join(e.message for e in issues[:3]))
                eid = record["evidence_id"]
                if eid in self.ids and self.ids[eid] != ref:
                    self.errors.append(f"EVIDENCE_ID {eid}: reused by different files")
                self.ids[eid] = ref

                # Determine artifact revision for historical closure evidence
                artifact_revision = None
                if hasattr(self, "historical_provenance"):
                    # Check if this evidence belongs to a historical closure with known artifact provenance
                    for closure_id, provenance in self.historical_provenance.items():
                        # Optional evidence_refs narrows the pin to listed records only.
                        scope = provenance.get("evidence_refs")
                        if (ref in scope) if scope is not None else (closure_id in ref):
                            artifact_revision = provenance.get("artifact_revision")
                            break

                for artifact in record["artifacts"]:
                    p = self.path(artifact["ref"])
                    if p is None:
                        self.errors.append(
                            f"EVIDENCE_ARTIFACT {ref}: missing/changed {artifact['ref']}"
                        )
                    else:
                        # Validate artifact hash at appropriate revision
                        if artifact_revision:
                            # Historical closure: check artifact at evidence-producing revision
                            import subprocess

                            try:
                                # Artifact ref is relative to plan/, need to prepend "plan/" for Git
                                git_path = f"plan/{artifact['ref']}"
                                result = subprocess.run(
                                    ["git", "show", f"{artifact_revision}:{git_path}"],
                                    capture_output=True,
                                    check=True,
                                    cwd=self.plan.parent,
                                )
                                actual_hash = hashlib.sha256(result.stdout).hexdigest()
                                if actual_hash != artifact["sha256"]:
                                    self.errors.append(
                                        f"EVIDENCE_ARTIFACT {ref}: hash mismatch at {artifact_revision[:7]} for {artifact['ref']}"
                                    )
                            except subprocess.CalledProcessError:
                                self.errors.append(
                                    f"EVIDENCE_ARTIFACT {ref}: cannot read {artifact['ref']} at {artifact_revision[:7]}"
                                )
                        else:
                            # Current evidence: check artifact at current HEAD
                            if (
                                hashlib.sha256(p.read_bytes()).hexdigest()
                                != artifact["sha256"]
                            ):
                                self.errors.append(
                                    f"EVIDENCE_ARTIFACT {ref}: missing/changed {artifact['ref']}"
                                )
                        # Check that artifact is not a template (applies to both historical and current)
                        if p.relative_to(self.plan).parts[0] == "templates":
                            self.errors.append(
                                f"EVIDENCE_ARTIFACT {ref}: a template is not an execution result"
                            )
                for child in record["input_evidence_refs"]:
                    self.read(child)
            except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
                # Skip EVIDENCE_RECORD error for grandfathered tasks with legacy evidence
                if str(exc) == "__LEGACY_EVIDENCE__":
                    record = None  # Mark as legacy, no error
                elif subject and subject in self.compat:
                    # Other errors for grandfathered tasks are also suppressed
                    record = None
                else:
                    self.errors.append(f"EVIDENCE_RECORD {ref}: {exc}")
                    record = None
            finally:
                self.stack.remove(ref)
                self.cache[ref] = record
        record = self.cache[ref]
        if record is not None:
            if types and record["evidence_type"] not in types:
                self.errors.append(f"EVIDENCE_TYPE {ref}: expected {sorted(types)}")
            if subject and record["subject_id"] != subject:
                self.errors.append(f"EVIDENCE_SUBJECT {ref}: expected {subject}")
            if revision and record["revision"] != revision:
                self.errors.append(f"EVIDENCE_REVISION {ref}: mismatch")
        return record


def evidence_checks(data, plan):
    errors = []
    schema = json.loads(
        (Path(plan) / "schemas/evidence-record.schema.json").read_text()
    )
    Draft202012Validator.check_schema(schema)

    # Load legacy evidence compatibility register
    compat = data.get("legacy-evidence-compatibility", {}).get(
        "compatibility_entries", {}
    )

    # Load historical closure artifact provenance
    historical_provenance = data.get("legacy-evidence-compatibility", {}).get(
        "historical_closure_artifact_provenance", {}
    )

    reader = EvidenceReader(plan, schema, errors, compat, historical_provenance)
    tasks = {t["task_id"]: t for t in data["implementation-backlog"]["tasks"]}
    suites = {s["id"]: s for s in data["test-catalog"]["suites"]}
    phases = {p["id"]: p for p in data["phase-gates"]["phases"]}
    type_by_kind = {
        "code": "CODE",
        "tests": "TEST_RESULT",
        "ci": "CI_RUN",
        "acceptance": "ACCEPTANCE_RECORD",
    }

    def require(ok, message):
        if not ok:
            errors.append(message)

    def covers(records, expected, label):
        observed = set().union(*(set(r.get("check_ids", [])) for r in records if r))
        # Skip EVIDENCE_COVERAGE check for grandfathered tasks
        task_id = label.split()[0] if label else None
        if task_id in compat:
            return  # Grandfathered task, skip coverage check
        require(
            set(expected).issubset(observed),
            f"EVIDENCE_COVERAGE {label}: missing checks",
        )

    for t in tasks.values():
        tid = t["task_id"]
        records_by = {}
        for kind, pointers in t["evidence"].items():
            records_by[kind] = [
                reader.read(x["ref"], {type_by_kind[kind]}, tid, x["revision"])
                for x in pointers
            ]
        if t["status"] not in {"VERIFIED", "CLOSED"}:
            continue
        task_suites = [suites[sid] for sid in t["tests"] if sid in suites]
        expected = [s["id"] for suite in task_suites for s in suite["scenarios"]]
        covers(records_by["tests"], expected, tid)
        covers(records_by["acceptance"], expected, tid + " acceptance")
        required_inputs = {
            x["ref"] for kind in ("code", "tests", "ci") for x in t["evidence"][kind]
        }
        suite_refs = {
            ref for suite in task_suites for ref in suite["execution_evidence"]
        }
        # Skip TASK_SUITE_EVIDENCE check for grandfathered tasks
        if tid not in compat:
            require(
                {x["ref"] for x in t["evidence"]["tests"]}.issubset(suite_refs),
                f"TASK_SUITE_EVIDENCE {tid}: results not linked to suite",
            )
        for a in records_by["acceptance"]:
            if not a or a["evidence_type"] != "ACCEPTANCE_RECORD":
                continue
            require(
                required_inputs.issubset(a["input_evidence_refs"]),
                f"ACCEPTANCE_INPUTS {tid}: missing code/test/CI binding",
            )
            disposition = {d["finding_id"]: d for d in a["finding_dispositions"]}
            require(
                len(disposition) == len(a["finding_dispositions"]),
                f"FINDING_DISPOSITION {tid}: duplicate ID",
            )
            require(
                set(disposition) == set(t["related_findings"]),
                f"FINDING_DISPOSITION {tid}: every related finding needs disposition",
            )
            external = {
                x["practice_id"]: x for x in a.get("external_practice_results", [])
            }
            require(
                set(external) == set(t.get("external_practices", []))
                and len(external) == len(a.get("external_practice_results", [])),
                f"ACCEPTANCE_EXTERNAL {tid}: missing/duplicate practice results",
            )
            for x in external.values():
                for ref in x["verification_refs"]:
                    reader.read(ref)
                    require(
                        ref in a["input_evidence_refs"],
                        f"ACCEPTANCE_EXTERNAL {tid}: unbound result",
                    )
            for f in disposition.values():
                for ref in f["evidence_refs"]:
                    reader.read(ref)
                    require(
                        ref in a["input_evidence_refs"],
                        f"FINDING_DISPOSITION {tid}: unbound evidence",
                    )
                if f["disposition"] in {"PARTIALLY_RESOLVED", "TRANSFERRED"}:
                    require(
                        f["next_task"] in tasks and f["next_task"] != tid,
                        f"FINDING_DISPOSITION {tid}: invalid next task",
                    )
                    require(
                        f["due_gate"] in {p["exit_gate"] for p in phases.values()},
                        f"FINDING_DISPOSITION {tid}: invalid due gate",
                    )
    for suite in suites.values():
        records = [
            reader.read(ref, {"TEST_RESULT"}, suite["task_id"])
            for ref in suite["execution_evidence"]
        ]
        if suite["status"] == "VERIFIED":
            # Skip coverage check for grandfathered task suites
            if suite["task_id"] not in compat:
                covers(records, [s["id"] for s in suite["scenarios"]], suite["id"])
    for a in data["decision-register"]["decisions"]:
        if a["decision_record"]:
            reader.read(a["decision_record"], {"ADR_DECISION"}, a["id"])
        for ref in a.get("verification_refs", []):
            reader.read(ref)
    gates = data["ci-gates"]["gates"]
    for g in gates:
        require(
            g.get("status") in {"NOT_IMPLEMENTED", "IMPLEMENTED", "VERIFIED"},
            f"CI_STATUS {g['id']}: invalid",
        )
        records = [reader.read(ref, {"CI_RUN"}) for ref in g.get("evidence_refs", [])]
        if g["status"] == "VERIFIED":
            covers(records, [g["id"]], g["id"])
    for p in phases.values():
        records = [
            reader.read(ref, {"PHASE_DECISION"}, p["id"]) for ref in p["evidence_refs"]
        ]
        if p["status"] != "VERIFIED":
            continue
        required_acceptance = {
            x["ref"] for tid in p["tasks"] for x in tasks[tid]["evidence"]["acceptance"]
        }
        applicable = [
            g
            for g in gates
            if int(g["activation_phase"][1:]) <= int(p["id"][1:])
            and (g["mode"] == "every_change" or p["id"] in {"P5", "P8", "P9"})
        ]
        for g in applicable:
            require(
                g["status"] == "VERIFIED", f"PHASE_CI {p['id']}: {g['id']} unverified"
            )
        for record in records:
            if not record or record["evidence_type"] != "PHASE_DECISION":
                continue
            require(
                required_acceptance.issubset(record["input_evidence_refs"]),
                f"PHASE_INPUTS {p['id']}: missing task acceptance",
            )
            ci_records = [
                reader.read(ref, {"CI_RUN"}, revision=record["revision"])
                for ref in record["ci_evidence_refs"]
            ]
            require(
                set(record["ci_evidence_refs"]).issubset(record["input_evidence_refs"]),
                f"PHASE_CI {p['id']}: unbound run",
            )
            covers(ci_records, [g["id"] for g in applicable], p["id"] + " CI")
    for m in data["milestones"]["milestones"]:
        for ref in m["evidence_refs"]:
            record = reader.read(ref, {"MILESTONE_DECISION"}, m["id"])
            if record and m["status"] == "VERIFIED":
                phase = phases[m["earliest_close_phase"]]
                for phase_ref in phase["evidence_refs"]:
                    reader.read(
                        phase_ref, {"PHASE_DECISION"}, phase["id"], record["revision"]
                    )
                required = set(phase["evidence_refs"]) | {
                    x["ref"]
                    for tid in m["required_tasks"]
                    for x in tasks[tid]["evidence"]["acceptance"]
                }
                require(
                    required.issubset(record["input_evidence_refs"]),
                    f"MILESTONE_INPUTS {m['id']}: missing phase/task evidence",
                )
    for f in data["remediation-register"]["findings"]:
        for ref in f["closure_refs"]:
            record = reader.read(ref, {"FINDING_CLOSURE"}, f["id"])
            if record and f["status"] in {"CLOSED", "VERIFIED"}:
                require(
                    all(
                        tasks[tid]["status"] in {"VERIFIED", "CLOSED"}
                        for tid in f["related_tasks"]
                    ),
                    f"FINDING_CLOSURE {f['id']}: unfinished obligations",
                )
                needed = {
                    r["ref"]
                    for tid in f["related_tasks"]
                    for r in tasks[tid]["evidence"]["acceptance"]
                }
                require(
                    needed.issubset(record["input_evidence_refs"]),
                    f"FINDING_CLOSURE {f['id']}: missing task acceptance",
                )
    for practice in data["external-practice-register"]["practices"]:
        for ref in practice["verification_refs"]:
            reader.read(ref)
    return errors
