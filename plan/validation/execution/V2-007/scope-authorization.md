# V2-007 Scope Authorization

## Task Identity

**Task:** V2-007 Event Timeline Promise Core  
**ADR:** ADR-003 (revision 38edb6e)  
**Authorization:** Owner-authorized implementation and remediation

## Execution Context

**Canonical Repository:** TomAy47287015/ainoveloacc  
**Canonical Base:** 5877a66771b273527462a72886c0942e5e325f77 (dev_cc)  
**Implementation Branch:** impl/v2-007-event-timeline-promise-core  
**Remediation Start:** 3c6d1e8be1f2f7f68fda2eecbc4d7b8d20a95ab8

## Authorized Scope

### In Scope

**Domain Implementation:**
- Event Timeline domain model (src/anovel/domain/events.py)
- Promise lifecycle domain model (src/anovel/domain/promises.py)
- Pure domain semantics (no database, no Canon, no Provider)
- Deep immutability (tuple/MappingProxyType)
- Project isolation with explicit EntityRegistry context

**Test Coverage:**
- Authoritative contract tests (tests/contract/test_v2_007.py)
- All ADR-003 acceptance criteria and milestones
- Semantic blocker remediation tests (R1-R6)

**Execution/Validation Records:**
- Execution packet updates (plan/validation/execution/V2-007/)
- Machine state synchronization
- Validation artifact generation
- This scope authorization document

### Explicitly Out of Scope

**Deferred to V2-009:**
- Database persistence layer
- CanonCommitService integration
- Repository implementation
- Idempotency retry mechanisms

**Deferred to Future Tasks:**
- Retcon Event (immutability exceptions)
- Temporal constraint solver
- Causality graph
- Mystery/Clue as Promise subtypes

**Never Permitted:**
- Modifications to .gitlab-ci.yml (no gate weakening, no allow_failure)
- V2-008 or later task initiation
- ADR-004 or later ADR work
- Calendar engine / timezone / historical calendar systems beyond minimal ISO 8601

## Historical Note

This scope authorization artifact is established during **forward remediation** on 2026-10-15.

**Sequence Transparency:**
- V2-007 implementation commits (fd78108...fba7639) were created when execution-packet.yaml action was still PREPARE
- This represents historical execution sequencing mismatch
- This artifact does NOT claim to have existed before those implementation commits
- Forward-only remediation establishes proper governance binding going forward
- No historical commits are rewritten or backdated

## Authorization Record

**Authorized By:** Owner (implicit via task assignment and remediation authorization)  
**Scope Finalized:** 2026-10-15  
**Document Purpose:** Fixed scope reference for execution packet change_review binding

This document serves as the canonical scope definition for V2-007 implementation and remediation work, establishing clear boundaries for what is and is not permitted within this task's execution context.
