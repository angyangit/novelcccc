# Project Status

**Document Type**: Derived Summary  
**Canonical Dynamic State**: `plan/machine/*`

This document is intentionally **not** a second source of truth for fast-moving task, phase, ADR, readiness, execution-packet, or next-action state.

Before acting, always read the live machine sources:

- Tasks: `plan/machine/implementation-backlog.yaml`
- Gates: `plan/machine/phase-gates.yaml`
- Decisions: `plan/machine/decision-register.yaml`
- Tests: `plan/machine/test-catalog.yaml`
- Remediation: `plan/machine/remediation-register.yaml`

If this document ever conflicts with `plan/machine/*`, the machine SSOT wins.

---

## Canonical Repository

**Repository**: `https://github.com/AY123/AiNoverCC.git`  
**Branch**: `main`

Resolve current HEAD live:

```bash
git fetch origin --prune
git rev-parse origin/main
```

Do not treat a SHA written in this document as current authority.

---

## Stable Project Context

ANovelOS is an automatic-creation and reliable-production system for Chinese web fiction. The engineering objective is to improve reading competitiveness while keeping engineering verification, human reading outcomes, and market outcomes as separate evidence layers.

The repository currently follows Plan v1.3.1 with a P0–P14 roadmap. P0 repository/governance foundations have a completed historical closure. P1 is the domain-foundation stage in which identity, relationship, character knowledge/intent, Event/Promise temporal semantics, and subsequent NarrativeDelta/Canon foundations are built under explicit ADR and acceptance gates.

The following are stable historical facts, not live execution authorization:

- V2-001 through V2-004 established and closed the P0 repository/governance baseline.
- V2-005 closed Entity Identity & Alias Resolution.
- V2-006 closed Entity Relationship Tracking.
- V2-061 closed Character Knowledge & Intent Core.
- V2-007 closed Event Timeline Promise Core under ADR-003.
- ADR-004 defines the finite change language and reducer preconditions consumed by later NarrativeDelta work.

For whether any task/ADR above is currently OPEN, CLOSED, ACCEPTED, REQUIRED, READY, IN_PROGRESS, or otherwise actionable, read `plan/machine/*` live.

---

## Governance Notes

### V2-006 Task Identity Reconciliation (2026-10-08)

The historical machine V2-006 definition ("Character relationship knowledge core") was reconciled with the implemented and closed V2-006 ("Entity Relationship Tracking") through formal scope split and rehoming:

- V2-006 retained as "Entity Relationship Tracking"
- V2-061 created as "Character Knowledge & Intent Core"
- Plan v1.3.0 → v1.3.1 increased the task count from 60 to 61

Governance record:

`plan/changes/2026-10-08_V2_006_TASK_IDENTITY_RECONCILIATION.md`

Historical closure tags preserved:

- `v2.005-complete` → `bd303e64dab6475bd12b69d273afa6c64eaa38ad`
- `v2.006-complete` → `bba1061ef27669ece55530bfdd846767b2fe21af`

---

## CI and Platform Notes

Current operational repository and CI platform:

- GitHub repository: `AY123/AiNoverCC`
- Canonical branch: `main`
- CI: GitHub Actions under `.github/workflows/`

Historical GitLab CI evidence may remain inside historical closure artifacts for traceability. It is not current operational authority.

Common local validation commands:

```bash
python3 -B plan/scripts/validate_plan.py --check
python3 -B plan/scripts/validate_plan.py --self-test
python3 -B plan/scripts/test_governance.py
python3 -B plan/scripts/test_ai_execution.py
pytest tests/architecture/ tests/contract/ -q
```

Use `--write-views` only when machine sources were intentionally changed and generated views must be refreshed.

---

## P2 Implementation and Evidence Status

**Context**: The machine state in `plan/machine/implementation-backlog.yaml` is designed to track formal closure evidence, not implementation merge status. When implementation proceeds without complete closure evidence registration, a gap emerges between GitHub reality and machine state.

**Current P2 Status (as of 2026-10-21)**:

### V2-009 Canon Persistence

**Implementation**: ✅ MERGED to main
- Merge SHA: `cde9b44` (PR #18)
- Files: migrations/, src/anovel/canon/repository.py, tests/integration/test_v2_009.py
- CI: Tests pass in GitHub Actions POSTGRES_ENV gate
- Execution packet: EXISTS at `plan/validation/execution/V2-009/execution-packet.yaml`

**Machine Status**: `status: OPEN` (formal closure evidence incomplete)
- Reason: No `plan/validation/execution/V2-009/closure/` directory
- Missing: Typed CODE/TEST_RESULT/CI_RUN/ACCEPTANCE_RECORD evidence per schema
- Gap: Implementation merged without following formal closure protocol

**Original Acceptance Coverage**: All 4 criteria have test coverage (AT-V2-009-01 through 05)

### V2-010 CanonCommitService

**Implementation**: ✅ MERGED to main
- Merge SHA: `f136353` (PR #19)
- Files: src/anovel/canon/commit_service.py (975 lines), tests/integration/test_v2_010.py (1,449 lines), test_commit_receipt_schema.py, test_isolation_level.py, commit-receipt.schema.json
- CI: Tests pass in GitHub Actions POSTGRES_ENV gate
- Execution packet: DOES NOT EXIST (`execution_packet_ref: null`)

**Machine Status**: `status: OPEN` (no execution packet or closure evidence)
- Reason: Implementation bypassed formal execution protocol entirely
- Missing: Execution packet, typed evidence records, closure directory
- Gap: Larger protocol deviation than V2-009

**Original Acceptance Coverage**: 
- Criterion 1 (Permit rejection): ✅ FULL (AT-V2-010-01)
- Criterion 2 (Transaction atomicity): ⚠️ PARTIAL (AT-V2-010-03, 04 test atomicity and rollback, but not explicit failure injection)
- Criterion 3 (Long-term evidence locatability): ❌ NOT_PROVEN (no test for historical artifact retrieval)
- Criterion 4 (Edit rejection + rebuild): ❌ NOT_PROVEN (system has immutable commits, but not explicitly tested)
- Criterion 5 (Cancel/commit ordering): ⚠️ PARTIAL (AT-V2-010-05, 09 cover idempotent recovery and restart, but not cancel-first scenarios)

**Additional Tests Beyond Original Criteria**: AT-V2-010-06 through 11 (idempotency conflict, character persistence, preconditions, concurrent race)

### V2-011 and V2-012

**Status**: OPEN, not started, no implementation authorization

**Note on V2-011 Scope**: V2-010 already implements V2-011's stated acceptance criteria (idempotent recovery, idempotency conflict, concurrent CAS). If V2-011 proceeds, scope clarification needed to avoid redundant implementation.

### P2 Gate

**Phase Status**: `NOT_VERIFIED` (correct - phase incomplete)
- V2-009: Implementation merged, evidence incomplete
- V2-010: Implementation merged, evidence incomplete
- V2-011: Not started
- V2-012: Not started

**Interpretation Guidance for AI Agents**:
- `OPEN` status in machine does NOT mean "not implemented"
- `OPEN` means "formal closure evidence incomplete per protocol"
- Check both machine state AND GitHub history for complete picture
- Implementation merge and formal task closure are separate states

### Production Readiness Notes

**PermitVerifier**: Current implementation is `TestPermitVerifier` for integration testing only. Production deployment requires:
- Trusted permit authority infrastructure
- Cryptographic signature verification
- Expiration and revocation mechanisms
- Audit logging
- Rate limiting

This is a documented limitation, not an evidence gap. See `.github/PR_V2_010_DESCRIPTION.md` lines 122-134.

---

## Authority References

Machine sources:

- `plan/machine/implementation-backlog.yaml` — task identities, dependencies, status, readiness, execution packets, acceptance mappings
- `plan/machine/phase-gates.yaml` — phase membership and gates
- `plan/machine/test-catalog.yaml` — acceptance test registry
- `plan/machine/decision-register.yaml` — ADR state and decision records
- `plan/machine/remediation-register.yaml` — findings and remediation obligations

Human-readable execution/governance guidance:

- `AGENTS.md`
- `plan/AI_EXECUTION_PROTOCOL.md`
- `plan/09_TASK_EXECUTION_GUIDE.md`
- `plan/10_DECISIONS_AND_REMEDIATION.md`

Historical records remain useful for audit and traceability but must not override current machine authority.

---

## For New AI Agents

1. Read `AGENTS.md`.
2. Read `plan/machine/phase-gates.yaml`.
3. Read `plan/machine/implementation-backlog.yaml`.
4. Read `plan/machine/decision-register.yaml`.
5. Determine the current task, required ADRs, readiness, execution packet, and next legal action from those live machine sources.
6. Only then read task-specific normative specs, ADRs, execution packets, tests, and evidence.

**Do not infer the current implementation task or next action from this file.**

---

**END OF STATUS**
