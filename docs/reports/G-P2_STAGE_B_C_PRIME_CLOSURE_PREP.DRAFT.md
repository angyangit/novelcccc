# G-P2 Stage B — Candidate C' Owner Review DRAFT

> **DRAFT — preparation only.** This Markdown document is not a typed PHASE_DECISION, is not a CI_RUN evidence record, and does not register G-P2 as VERIFIED. It is not an Owner signature. No change to `plan/machine/phase-gates.yaml` is authorized at this point.

## 1. Canonical baseline and exact provenance

- Repository: `https://github.com/angyangit/novelcccc.git` (private).
- Candidate C' / verified main HEAD at start of this review: `65e2fc0e9f44e16653650a4866095f57328cdc7c`.
- Merge PR: https://github.com/angyangit/novelcccc/pull/1 ; merged as `65e2fc0e9f44e16653650a4866095f57328cdc7c` with parents `7a1e8e4595a9c574f480579d4eddc006ee9d0ab0` and `e27d31361bcdf74ea798677786332a6cff4663ec`.
- GitHub Actions **push to main**, run `40104699607`, `conclusion: success`, `head_sha: 65e2fc0e9f44e16653650a4866095f57328cdc7c`: https://github.com/angyangit/novelcccc/actions/runs/40104699607
- Baseline machine state: `P2/G-P2 = NOT_VERIFIED`; `evidence_refs: []`; tasks `V2-009` through `V2-012` are `CLOSED`. This document does **not** change those fields.
- Previous historical Stage A material remains at `plan/validation/closure/G-P2-455d7b9/`; its `455d7b9...` references describe a **different** candidate. Do not relabel its original records or CI identifiers.
- The already-committed `plan/validation/plan-validation.json` is a prior dirty-worktree snapshot referring to `7a1e8e4...`, **not** a standalone attestation of C'. The **remote main CI** is the current independent verification source.

## 2. Six actual GitHub CI job identities

All six jobs belong to run `40104699607`, executed on commit `65e2fc0e9f44e16653650a4866095f57328cdc7c`, and GitHub reports `completed / success`. These are verifiable live run/job bindings **for preparation**, not yet authored typed `CI_RUN` records with immutable artifact SHA-256.

| Required gate | GitHub job ID | Result | Verifiable job |
| --- | --- | --- | --- |
| STATIC | `120903858561` | SUCCESS | https://github.com/angyangit/novelcccc/actions/runs/40104699607/job/120903858561 |
| SCHEMA_CONTRACT | `120903858662` | SUCCESS | https://github.com/angyangit/novelcccc/actions/runs/40104699607/job/120903858662 |
| UNIT | `120903858540` | SUCCESS | https://github.com/angyangit/novelcccc/actions/runs/40104699607/job/120903858540 |
| ARCH_FITNESS | `120903858401` | SUCCESS | https://github.com/angyangit/novelcccc/actions/runs/40104699607/job/120903858401 |
| POSTGRES_ENV | `120903858533` | SUCCESS | https://github.com/angyangit/novelcccc/actions/runs/40104699607/job/120903858533 |
| SECRET_DEPENDENCY | `120903858596` | SUCCESS | https://github.com/angyangit/novelcccc/actions/runs/40104699607/job/120903858596 |

The SCHEMA_CONTRACT job log reports Plan Validation `PASS` with `fatal_errors: []`, governance `25 passed` and CommitReceipt schema integration `7 passed`. The PostgreSQL job succeeded through service check, Alembic migration, V2-009/010/011/012 acceptance/integration sets, isolation and environment-security regression. This demonstrates the covered behavior tested in that workflow, not all possible production behaviors.

Available Actions run artifacts observed: `unit-test-results` (artifact ID `12564565928`), `arch-test-results` (`12564267049`), `security-results` (`12564157589`). **Do not invent SHA-256** or claim absent per-job archives; obtain and hash actual artifacts/log copies if formally building typed `CI_RUN` witnesses. Use the real per-job commands/check IDs, UTC timestamps and exit statuses verified against source logs. The CI proof revision must remain C'.

## 3. Task evidence continuity and historical revision semantics

| Task | Machine status | Typed evidence present and status | Original subject revision |
| --- | --- | --- | --- |
| V2-009 — Canon persistence/repository | CLOSED | CODE, TEST_RESULT, CI_RUN, ACCEPTANCE_RECORD: PASS; acceptance ACCEPTED | `455d7b9e7aaa4d71a056800d529333ba408d6f41` |
| V2-010 — CanonCommitService | CLOSED | same four kinds: PASS; acceptance ACCEPTED | `455d7b9e7aaa4d71a056800d529333ba408d6f41` |
| V2-011 — Idempotency / CAS | CLOSED | same four kinds: PASS; acceptance ACCEPTED | `455d7b9e7aaa4d71a056800d529333ba408d6f41` |
| V2-012 — Snapshot / projection | CLOSED | same four kinds: PASS; acceptance ACCEPTED | `455d7b9e7aaa4d71a056800d529333ba408d6f41` |

For each `V2-xxx`, the four existing paths are `plan/validation/tasks/V2-xxx/{code-evidence,test-evidence,ci-evidence,acceptance-evidence}.yaml` and the retrospective packet is `plan/validation/execution/V2-xxx/execution-packet.yaml`.

These historical task-evidence records bind the original implementation revision and must **not** be rewritten as though the task code was first completed in C'. Current successful GitHub CI on C' is *additional integration evidence*, not a replacement for old GitLab identities.

The execution packets explicitly disclose retrospective reconstruction and distinguish GitLab code merges from prior Owner IMPLEMENT authorization. PR #1 merged this repair, but neither the merge nor this document proves a prior formal authorization existed. Any Owner acceptance of this retrospective record is only prospective governance acceptance of historical facts, not retroactive creation of a pre-implementation permission.

## 4. Exit criteria — review assessment, not final decision

| G-P2 exit criterion | Existing substantive support | Review disposition |
| --- | --- | --- |
| Transaction atomicity, Compare-and-Swap, idempotency and PostgreSQL evidence | V2-009 persistence/migrations; V2-010 commit transaction; V2-011 `idempotency_key` retry/conflict semantics and `update_branch_head_cas` branch-head conditional updates; GitHub POSTGRES_ENV success at C' | Technical test gate SATISFIED within tested scope; Owner formal acceptance pending |
| Unique root commit and complete receipt | V2-009/010 historical CODE/TEST/ACCEPTANCE witnesses; ADR-006 implementation, root uniqueness and receipt tests included in successful remote run | Supported within recorded contract/test scope; Owner review pending |
| Snapshot rebuilding and cross-project isolation | V2-012 projection/snapshot evidence and integration tests, cross-project scoped relations and isolation tests; GitHub POSTGRES_ENV success at C' | Supported within recorded contract/test scope; Owner review pending |

Do not infer production deployment, live provider, P3 readiness, ADR-007 acceptance or complete market/reader outcomes from this CI.

## 5. Findings and explicit accuracy review

The four ACCEPTANCE_RECORD documents enumerate 11, 12, 4 and 6 FULL/RESOLVED dispositions respectively for V2-009/010/011/012, with shared finding IDs appearing in more than one task. They are historical per-task claims, **not** a count of unique resolved findings. Their actual scope/responsibility must be assessed against the finding register before any new `FINDING_CLOSURE` is recorded.

**Known historical wording issue to present to Owner:** `plan/validation/tasks/V2-011/acceptance-evidence.yaml` still says that `canon_hash` duplicate detection proves “Canon CAS idempotency” in several finding rationales. The later repaired execution packet correctly distinguishes `idempotency_key` uniqueness-based retry/conflict behavior from `update_branch_head_cas` conditional branch-HEAD updating. Treat the older rationale as a retrospective wording limitation, not a fresh proof that CAS works through canon_hash. The acceptance evidence itself is preserved unchanged at this preparation stage. Before issuing final PHASE_DECISION, Owner must explicitly accept a narrowly scoped clarification/limitation or request a properly authorized factual correction and any necessary re-verification. Never silently modify the historical evidence revision.

## 6. Governance / migration boundaries

- Github PR #1's explicit one-off voluntary main-control risk acceptance does **not** extend to a new Closure D' PR.
- GitHub private `main` was observed with `protected: false`; required-check enforcement / technical protection is **not** established. Keep it as an open, separately actionable risk; do not claim safeguards exist just because CI runs automatically.
- Canonical development repository is GitHub. The old GitLab repo and pipeline records remain historical provenance.
- Old local obsolete Closure D `ebb25f2` is excluded and must not be pushed or merged.

## 7. Proposed PHASE_DECISION fields (illustrative **non-executable** DRAFT)

This outline is intentionally not a valid committed `PHASE_DECISION` and cannot trigger VERIFIED:

```yaml
record_type: plan_execution_evidence
schema_version: '1.0'
evidence_type: PHASE_DECISION
subject_id: P2
revision: 65e2fc0e9f44e16653650a4866095f57328cdc7c
# evidence_id: allocate uniquely at the time of formally authorized closure
# status: PASS only after full review and validation
# decision: VERIFIED only after explicit Owner authorization
# producer, executed_at, environment_fingerprint: derive from the actual authorized decision
# artifacts: populate verified real refs and SHA-256; never invent
# input_evidence_refs: include accepted task evidence and actual applicable finding dispositions
# ci_evidence_refs: point to the six registered GitHub CI_RUN records for C'
# rationale: describe three G-P2 criteria, historical authorization limitations, and residual main-protection risk
```

Under `plan/09_TASK_EXECUTION_GUIDE.md` §7.1, closure-only D' must be based on C', must preserve `PHASE_DECISION.revision = C'`, and must have its **own** successful applicable CI before phase closure can be claimed. D' may modify closure metadata, phase status/refs and generated views only; any business implementation, tests, quality-gate or requirement change would require reevaluating the candidate.

## 8. Final Owner decision requested, not presupposed

**Recommended:** Accept Candidate C' as having successfully passed the repository's technical six-gate validation, subject to the recorded acceptance-evidence wording review. Decide whether existing retrospective implementation attestations and their known scope limitations are sufficient for formal G-P2 closure. Separately decide an appropriate main-branch protection remedy or **new** narrowly scoped manual-control exception for the future Closure D' PR.

The next **separately authorized** action would be to create formally typed, properly hashed six GitHub `CI_RUN` records, finalize the Owner-approved `PHASE_DECISION` and only the relevant machine closure metadata, open a closure-only PR, verify its CI, request explicit merge authorization, merge, and validate the merged closure commit D'. No step above has been taken by this preparation document.

**Stop point:** Owner review; G-P2 remains NOT_VERIFIED; ADR-007 and V2-013 remain unauthorized.
