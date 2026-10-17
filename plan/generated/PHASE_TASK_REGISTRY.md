# 阶段与任务注册表（自动生成）

唯一源：`machine/implementation-backlog.yaml` 与 `machine/phase-gates.yaml`。不要手工修改。

共 61 个任务。当前任务状态：{"CLOSED": 8, "OPEN": 53}

## P0 — Repository & Governance

准入：P0_ENTRY_READY；退出：G-P0；任务数：4。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-001 | Repository bootstrap | 无任务依赖，仍须阶段门禁 | CLOSED |
| V2-002 | Normative documentation index | 无任务依赖，仍须阶段门禁 | CLOSED |
| V2-003 | Architecture fitness harness | 无任务依赖，仍须阶段门禁 | CLOSED |
| V2-004 | Secret and dependency CI gates | 无任务依赖，仍须阶段门禁 | CLOSED |

## P1 — Narrative Kernel

准入：G-P0；退出：G-P1；任务数：5。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-005 | Core entity IDs and alias resolution | V2-001 | CLOSED |
| V2-006 | Entity Relationship Tracking | V2-005 | CLOSED |
| V2-061 | Character Knowledge & Intent Core | V2-005, V2-006 | CLOSED |
| V2-007 | Event timeline promise core | V2-005 | CLOSED |
| V2-008 | NarrativeDelta implementation | V2-006, V2-007, V2-061 | OPEN |

## P2 — Canon Kernel

准入：G-P1；退出：G-P2；任务数：4。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-009 | Canon persistence schema and repository | V2-008 | OPEN |
| V2-010 | CanonCommitService | V2-009 | OPEN |
| V2-011 | Canon idempotency and CAS | V2-010 | OPEN |
| V2-012 | Snapshot rebuild and projection | V2-010 | OPEN |

## P3 — Genre Kernel

准入：G-P2；退出：G-P3；任务数：4。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-013 | GenreProfile and GenrePack loader | V2-005 | OPEN |
| V2-014 | Genre hard policy engine | V2-013 | OPEN |
| V2-015 | Urban Business canon extension | V2-014, V2-010 | OPEN |
| V2-016 | Eastern Fantasy canon extension | V2-014, V2-010 | OPEN |

## P4 — Planning & Contracts

准入：G-P3；退出：G-P4；任务数：1。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-017 | Contract Compiler | V2-012, V2-014 | OPEN |

## P5 — Context & Model Gateway

准入：G-P4；退出：G-P5；任务数：2。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-018 | Context Compiler | V2-017 | OPEN |
| V2-019 | Model Gateway and provider abstraction | V2-018 | OPEN |

## P6 — Single-Chapter Production

准入：G-P5；退出：G-P6；任务数：3。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-020 | Single Chapter Workflow | V2-019, V2-011 | OPEN |
| V2-021 | NarrativeDelta extractor | V2-020 | OPEN |
| V2-027 | Workflow retry and checkpoint | V2-020 | OPEN |

## P7 — Quality & Repair

准入：G-P6；退出：G-P7；任务数：9。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-022 | Q0 deterministic validators | V2-021 | OPEN |
| V2-023 | Q1 Canon validators | V2-021, V2-012 | OPEN |
| V2-024 | Q2 Genre validators | V2-021, V2-014 | OPEN |
| V2-025 | Q3 Transition validators | V2-021, V2-017 | OPEN |
| V2-026 | CommitPermit integration | V2-022, V2-023, V2-024, V2-025 | OPEN |
| V2-029 | QualityAggregator | V2-022, V2-023, V2-024, V2-025 | OPEN |
| V2-030 | Diagnosis engine | V2-029 | OPEN |
| V2-031 | Patch-first Repairer | V2-030 | OPEN |
| V2-032 | Repair regression validator | V2-031 | OPEN |

## P8 — Dual-Genre 10-Chapter Certification

准入：G-P7；退出：G-P8；任务数：8。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-028 | Kill restart fault harness | V2-027 | OPEN |
| V2-033 | Three-chapter smoke certification | V2-026, V2-027, V2-032 | OPEN |
| V2-034 | Urban 10-chapter certification | V2-033, V2-015 | OPEN |
| V2-035 | Fantasy 10-chapter certification | V2-033, V2-016 | OPEN |
| V2-036 | Fault injection suite | V2-034, V2-035 | OPEN |
| V2-037 | Context inspector | 无任务依赖，仍须阶段门禁 | OPEN |
| V2-038 | Canon inspector | 无任务依赖，仍须阶段门禁 | OPEN |
| V2-039 | Lineage inspector | 无任务依赖，仍须阶段门禁 | OPEN |

## P9 — 30-Chapter Certification

准入：G-P8；退出：G-P9；任务数：1。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-040 | 30-chapter certification runner | V2-036 | OPEN |

## P10 — Genesis & Reference Intelligence

准入：G-P9；退出：G-P10；任务数：8。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-041 | Idea-driven Genesis | V2-040 | OPEN |
| V2-042 | Reference ingestion | V2-040 | OPEN |
| V2-043 | BookNarrativeProfile | V2-042 | OPEN |
| V2-044 | ReferenceEvidencePack | V2-043 | OPEN |
| V2-045 | Originality firewall | V2-044 | OPEN |
| V2-046 | Genesis Tournament | V2-041, V2-044, V2-045 | OPEN |
| V2-047 | GenesisSpec compiler | V2-046 | OPEN |
| V2-048 | GenesisCommit integration | V2-047, V2-010 | OPEN |

## P11 — Human Calibration / Learning

准入：G-P10；退出：G-P11；任务数：9。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-049 | Corpus Registry | V2-040 | OPEN |
| V2-050 | GoldenSet migration | V2-049 | OPEN |
| V2-051 | RegressionSet migration | V2-049 | OPEN |
| V2-052 | ExperimentDefinition | V2-049 | OPEN |
| V2-053 | Benchmark runner | V2-052 | OPEN |
| V2-054 | Blind pairwise evaluator | V2-053 | OPEN |
| V2-055 | Human evaluation ingestion | V2-054 | OPEN |
| V2-056 | Calibration pipeline | V2-055 | OPEN |
| V2-057 | Promotion gate | V2-056 | OPEN |

## P12 — 100-Chapter Reliability

准入：G-P11；退出：G-P12；任务数：3。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
| V2-058 | Backup restore validation | V2-012 | OPEN |
| V2-059 | Release manifest | V2-004, V2-058 | OPEN |
| V2-060 | 100-chapter reliability runner | V2-040, V2-057, V2-058 | OPEN |

## P13 — Reader / Market Feedback

准入：G-P12；退出：G-P13；任务数：0。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
本阶段任务将在对应阶段前细化，当前不宣称可直接执行。

## P14 — 300+ Chapter / Million-word Evolution

准入：G-P13；退出：G-P14；任务数：0。

| ID | 名称 | 依赖 | 状态 |
|---|---|---|---|
本阶段任务将在对应阶段前细化，当前不宣称可直接执行。

