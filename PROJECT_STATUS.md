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
