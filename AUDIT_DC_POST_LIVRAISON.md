# DC Workspace Post-Delivery Consistency Audit

**Date:** 2026-06-16
**Baseline commit:** `ce32c9a` (main)
**Scope:** Backend data contracts, business rules, security, pipeline — no UX/UI

---

## 1. Spec Consistency Overview

| Spec Section | Item | Present | Gap | Risk |
|---|---|---|---|---|
| §11.1 | PeopleSignal model | Yes | None | — |
| §11.2 | ConstraintSignal model | Yes | None | — |
| §11.3 | PainSignal.target_department | Yes | None | — |
| §11.3 | ImpactSignal.target_department | Yes | None | — |
| §11.4 | TechStackSignal decision_cycle reactivation | Yes | Shadow-override lifted | — |
| §11.5 | BlockerSignal actor attribution (contact + dept) | Partial | No `target_department` FK — only contact-level | Medium |
| §16 | DealHealthSnapshot | Yes | None | — |
| §16 | DealProduct | Yes | None | — |
| §16 | ProductCatalog (separate module) | Yes | None | — |
| §10 | DealHealthPipeline | Yes | TEMPERATURE=0.2 (spec says 0.0) | High |
| §10.3 | Output schema keys | Partial | `global_reading` not `global_diagnostic`; `discovery_gaps` not `gaps`; kind `qualification` not `qualif` | High |
| §10.4 | Prompts 3-layer | Yes | None | — |
| §10 | Evidence Pack Service | Yes | None | — |
| §10 | deal-health GET by-cycle endpoint | No | Missing — no `GET /by-cycle/{id}/` route | High |
| §10 | deal-health history endpoint | No | Missing — no history route | High |
| §12 QA Rule 7 | No duplication dimensions/themes | No | Rule absent from system prompt | Medium |
| §15 | DC workspace endpoints (11 checked) | 10/11 | `GET /themes/` absent (cut sprint Step 4) | Low — themes served via health-snapshot JSON |
| §3 | 5 tabs (no Overview) | 6 tabs | OverviewTab.jsx added beyond spec | Low — additive |
| — | ManagerNote model | Yes | Out-of-spec addition (not in §16) | Low — tracked TD-27/TD-29 |

---

## 2. Backend Models

### 2.1 PeopleSignal

| Field | Spec | Code | Gap |
|---|---|---|---|
| `role` | PeopleRole choices, required | `CharField(PeopleRole.choices)` | None |
| `influence` | InfluenceLevel choices, optional | `CharField(InfluenceLevel.choices, null=True, blank=True)` | None |
| `target_contact` | FK Contact, nullable | FK `module_contacts.Contact`, SET_NULL, null/blank | None |
| `target_department` | FK StandardDepartment, nullable | FK `core_modules.StandardDepartment`, SET_NULL, null/blank | None |
| `notes` | TextField | `TextField(blank=True)` | None |
| `clean()` | Requires at least one target | Raises ValidationError if both null | None |
| `canonical_key` | Forced None (no clustering) | `save()` forces `self.canonical_key = None` | None |

### 2.2 ConstraintSignal

| Field | Spec | Code | Gap |
|---|---|---|---|
| `what` | SignalWhat choices, required | `CharField(SignalWhat.choices)` | None |
| `dimension` | SignalDimension choices, required | `CharField(SignalDimension.choices)` | None |
| `summary` | TextField, required | `TextField()` — no blank/null | None |
| `target_department` | FK StandardDepartment, nullable | FK SET_NULL, null/blank | None |
| `rigidity` | FIRM/FLEXIBLE, required | `CharField(Rigidity.choices)` | None |
| `notes` | TextField, optional | `TextField(blank=True)` | None |
| `canonical_key` | `"constraint:{what}:{dimension}"` | Computed in `save()` with same format | None |

### 2.3 PainSignal — Extension

| Field | Spec | Code | Gap |
|---|---|---|---|
| `target_department` | FK added, nullable, non-conditional | FK SET_NULL, null=True, blank=True | None |

### 2.4 ImpactSignal — Extension

| Field | Spec | Code | Gap |
|---|---|---|---|
| `target_department` | FK added, nullable, non-conditional | FK SET_NULL, null=True, blank=True | None |
| `scope_level` | ScopeLevel choices | No default (unlike PainSignal which defaults BUSINESS) | Intentional — caller must supply |

### 2.5 TechStackSignal — Extension

| Field | Spec | Code | Gap |
|---|---|---|---|
| `decision_cycle` | Shadow-override `= None` lifted | Inherited from BaseSignal, SET_NULL, null/blank | None |
| `campaign` | Still overridden `= None` | `campaign = None` | Intentional |
| `signal_category` | Still overridden `= None` | `signal_category = None` | Intentional |

### 2.6 BlockerSignal

| Field | Spec | Code | Gap |
|---|---|---|---|
| `contact` FK | Actor attribution — contact | FK Contact, SET_NULL, null/blank | None |
| `target_department` FK | Actor attribution — department | **ABSENT** | **Gap: no department-level actor attribution** |

### 2.7 DealHealthSnapshot

| Field | Spec | Code | Gap |
|---|---|---|---|
| `decision_cycle` | FK CASCADE | `ForeignKey(DecisionCycle, CASCADE)` | None |
| `diagnostic` | JSONField | `JSONField()` — required | None |
| `snapshot_date` | auto_now_add | `DateTimeField(auto_now_add=True)` | None |
| `pipeline_run` | FK AIPipelineRun | FK SET_NULL, null/blank | None |
| Index | `(decision_cycle, -snapshot_date)` | `dhs_cycle_date_idx` present | None |

### 2.8 DealProduct

| Field | Spec | Code | Gap |
|---|---|---|---|
| `decision_cycle` | FK CASCADE | `ForeignKey(DecisionCycle, CASCADE)` | None |
| `product_catalog_entry` | FK ProductCatalog | FK PROTECT | None |
| `quantity` | IntegerField | `IntegerField(default=1)` | None |
| `unit_price` | Nullable override | `DecimalField(null=True, blank=True)` | None |
| `notes` | TextField | `TextField(blank=True, default='')` | None |
| `line_total` | Computed property | Present — falls back to `default_unit_price` | None |
| UniqueConstraint | `(decision_cycle, product_catalog_entry, client_id)` | Framework injects `client_id` via `get_meta_constraints` | None |

### 2.9 ProductCatalog

| Field | Spec | Code | Gap |
|---|---|---|---|
| Separate module | `app_modules/product_catalog/` | Yes | None |
| `name` | Required | `CharField(max_length=255)`, validated in `clean()` | None |
| `description` | Optional | `TextField(blank=True, default='')` | None |
| `value_proposition` | Present | `TextField(blank=True, default='')` | None |
| `default_unit_price` | Nullable decimal | `DecimalField(null=True, blank=True)` | None |
| Tenant uniqueness | `(client_id, name)` | Framework-injected via `unique_fields=['name']` | None |

### 2.10 ManagerNote (OUT-OF-SPEC)

| Field | Type | Notes |
|---|---|---|
| `decision_cycle` | FK DecisionCycle, CASCADE | Required |
| `content` | TextField | Required |
| `created_by` | FK User (inherited from ModuleBaseModel) | Used as author — no separate `author` FK |
| `client_id` | FK (inherited) | Tenant isolation |
| Index | `(decision_cycle, -created_at)` | `mn_cycle_date_idx` |

**Flag:** ManagerNote was not in spec §16. Added during sprint. No dedicated `author` FK, no `visibility` or `is_pinned` fields. Tracked as TD-27 (tenant-wide scope) and TD-29 (frontend mismatch).

### 2.11 Enums (signals/constants.py)

| Enum | Present | Values |
|---|---|---|
| PeopleRole | Yes | DECISION_MAKER, ECONOMIC_BUYER, CHAMPION, BLOCKER, END_USER, PROCUREMENT, INFLUENCER |
| InfluenceLevel | Yes | HIGH, MEDIUM, LOW |
| SignalWhat | Yes | OPS, TECH, DATA, PEOPLE, GROWTH |
| SignalDimension | Yes | TIME, COST, QUALITY, SCALE, RISK |
| Rigidity | Yes | FIRM, FLEXIBLE |

---

## 3. Pipeline deal-health

### 3.1 Registration

`AIPipelineType.DEAL_HEALTH` registered in `ai_pipelines/constants.py:91` as `'DEAL_HEALTH'`. Documented as cycle-level, single-stage, snapshot-producing.

### 3.2 Pipeline Class (`ai_pipelines/pipelines/deal_health.py`)

| Item | Spec | Code | Gap |
|---|---|---|---|
| TEMPERATURE | 0.0 (§10.4 conservative) | **0.2** (line 64) | **Deviation** |
| `transaction.atomic()` | Wraps snapshot + run finalize | Wraps LLM call + writer (line 100), but `_finalize_run(SUCCESS)` is **outside** atomic block (line 164) | **Gap: snapshot and run finalization in separate transactions** |
| `_create_run()` | Should be inside atomic | Called **before** atomic block (line 91) | **Gap: orphaned AIPipelineRun possible on partial crash** |

### 3.3 Prompts (3 layers)

| Layer | File | Present |
|---|---|---|
| System | `prompts/deal_health/system.py` | Yes |
| Context | `prompts/deal_health/context.py` | Yes |
| Diagnostic | `prompts/deal_health/diagnostic_v1.py` | Yes |

### 3.4 QA Rules in System Prompt

| Rule | Spec | Present | Gap |
|---|---|---|---|
| Rule 1 | "missing evidence" never means "weak" | Yes — Rule 2 in system.py: `NEVER use "weak", "low", "absent"` | None |
| Rule 4 | Discovery gaps in neutral tone | Yes — Rule 5: `Use phrasing like 'not yet qualified...' — never 'the rep failed to'` | None |
| Rule 6 | No internal terms (DRI); use "levers" | Yes — Rule 6: `Never use internal framework names (DRI, MEDDPICC labels, etc.)`. Output schema uses `levers` key | None |
| Rule 7 | No duplication between dimensions and themes | **ABSENT** — no anti-duplication constraint in system.py or diagnostic_v1.py | **Gap** |

### 3.5 Output Schema (diagnostic_v1.py `_OUTPUT_SCHEMA`)

| Spec §10.3 | Code | Gap |
|---|---|---|
| `global_diagnostic` | `global_reading` | **Key name mismatch** |
| `dimensions[]` (7 items) | 7 items, order enforced | None |
| Status enum: confirmed/suggested/unclear/missing_evidence/contradictory | Matches | None |
| `gaps[]` | `discovery_gaps` | **Key name mismatch** |
| Gap kind: `qualif`/`procedural` | `qualification`/`procedural` | **Value mismatch (`qualif` vs `qualification`)** |
| `levers` with key `cost` | `cost` present (line 44) | None |
| `themes[]` | Present (line 47) | None |

### 3.6 Evidence Pack (`deal_health_evidence_builder.py`)

- **Present:** Yes, fully implemented
- **Privacy-aware:** Yes — all signal serializers expose only `source_quote`, never raw transcripts
- **Includes validated signals:** Yes — filters `status=SignalStatus.VALIDATED` for all 7 signal types
- **Includes previous snapshot:** Yes — `_build_previous_snapshot` queries most recent by `snapshot_date` desc
- **No LLM calls:** Correct — purely deterministic assembly

### 3.7 Deal Health Writer (`deal_health_writer.py`)

- **No own `transaction.atomic()`** — relies on pipeline caller's atomic block
- **Structural validation:** Validates `global_reading`, 7 dimensions (order, status enum), `discovery_gaps` (kind enum), all 4 lever groups. Raises `PromptParseError` on failure.

### 3.8 Endpoints

| Endpoint | Present | Gap |
|---|---|---|
| `POST /module-ai-pipelines/deal-health/run/` | Yes (urls.py:30) | None |
| `GET /module-ai-pipelines/deal-health/by-cycle/{id}/` | **No** | **Missing** |
| `GET /module-ai-pipelines/deal-health/history/` | **No** | **Missing** |

Note: Health snapshots are served via DC workspace endpoints (`GET /decision-cycles/{cycle_id}/health-snapshots/` + `latest/`), not via the ai-pipelines URL namespace. The spec may have intended the ai-pipelines namespace.

---

## 4. Endpoints

### 4.1 DC Workspace Endpoints

| Endpoint | Exists | Method | Permission | Tests | Gap |
|---|---|---|---|---|---|
| `GET /decision-cycles/by-account/{account_id}/` | Yes | GET | `ScopedPermission` + `client_id` filter | Yes | None |
| `GET /decision-cycles/{id}/` | Yes | GET | `ScopedPermission` + `ScopedQuerysetMixin` | Yes | None |
| `POST /decision-cycles/{id}/close/` | Yes | POST | `ScopedPermission` default action policy | Yes | None |
| `GET /decision-cycles/{id}/people/` | Yes | GET | `action_policies['people'] = {read, client}` | Yes | None |
| `GET /decision-cycles/{id}/readiness/` | Yes | GET | `action_policies['readiness'] = {read, client}` | Yes | None |
| `GET /decision-cycles/{cycle_id}/products/` | Yes | GET | `action_policies: read/client` | Yes | None |
| `POST /decision-cycles/{cycle_id}/products/` | Yes | POST | `action_policies: create/mine` | Yes | None |
| `PATCH /decision-cycles/{cycle_id}/products/{id}/` | Yes | PATCH | `action_policies: update/mine` | Yes | None |
| `DELETE /decision-cycles/{cycle_id}/products/{id}/` | Yes | DELETE | `action_policies: delete/mine` | Yes | None |
| `GET /decision-cycles/{cycle_id}/health-snapshots/` | Yes | GET | `http_method_names=['get']` + read policies | Yes | None |
| `GET /decision-cycles/{cycle_id}/health-snapshots/latest/` | Yes | GET | Same as above | Yes | None |
| `GET /decision-cycles/{id}/themes/` | **No** | — | — | — | Cut in sprint Step 4; themes served via health-snapshot JSON payload |
| `POST /decision-cycles/{cycle_id}/notes/` | Yes | POST | `_is_manager_or_admin()` via `get_auth_ctx` | Yes | None |
| `GET /decision-cycles/{cycle_id}/notes/` | Yes | GET | manager/admin OR cycle owner | Yes | None |
| `DELETE /decision-cycles/{cycle_id}/notes/{id}/` | Yes | DELETE | author OR admin | Yes | None |

### 4.2 Permission Security Audit

| Check | Result | Detail |
|---|---|---|
| DealProductViewSet `action_policies` | **PASS** | All write actions scoped `mine`; reads scoped `client` |
| `_resolve_parent_cycle()` reuse | **PASS** | DealProduct + DealHealthSnapshot use `CycleScopedMixin` which delegates to `DecisionCycleViewSet.get_queryset()` — no custom Q-objects |
| ManagerNote `_resolve_parent_cycle()` | **INTENTIONAL BYPASS** | Raw `DecisionCycle.objects.get(id=cycle_id, client_id=client_id)` — tenant isolation holds but ownership scope bypassed. Documented TD-27 |
| DealHealthSnapshot write endpoints | **PASS** | No create/update/delete exposed — `http_method_names=['get', 'head', 'options']` |
| ManagerNote permissions via `get_auth_ctx` | **PASS** | Uses tier-based JWT role flags, not `user.is_manager` boolean |
| `client_id` filtering | **PASS** | All querysets filter `client_id` via `ScopedQuerysetMixin` or explicit filter |
| `getattr(user, 'is_X')` truthy method bug | **PASS** | `is_admin`/`is_manager` are `BooleanField` on `UserRole`, not methods |
| ManagerNote destroy — manager excluded | **NOTE** | Only author OR admin can delete. A manager who did not author a note cannot delete it. Matches spec "author/admin deletes" |

---

## 5. Services

### 5.1 ReadinessScoreService

- **Present:** Yes (`decision_cycles/services/readiness_score_service.py`)
- **Output:** `{'score': int, 'dimensions': [{'name', 'filled', 'weight', 'detail'}]}` — matches spec (extra `detail` field is additive)
- **Pure logic:** Yes — stateless, read-only DB queries, no LLM
- **Side effects:** `recompute_and_store()` classmethod writes, clearly separated from `calculate()`

### 5.2 PeopleConsolidationService

- **Present:** Yes (`decision_cycles/services/people_consolidation_service.py`)
- **Read-only:** Yes — no writes, no `save()` calls
- **Output:** `{'qualified': [...], 'unqualified': [...]}` — matches spec
- **Logic:** Correctly identifies contacts NOT in validated PeopleSignals. Sources unqualified from Activity.contacts M2M and DecisionStepContact, subtracts those with validated PeopleSignal

### 5.3 EvidencePackService (DealHealthEvidenceBuilder)

- **Present:** Yes (`ai_pipelines/services/deal_health_evidence_builder.py`)
- **Privacy-aware:** Yes — all signal serializers expose `source_quote` only, no raw transcripts
- **Includes:** Validated signals (7 types), cycle context, readiness score, people data, previous snapshot
- **No LLM calls:** Correct — purely deterministic

---

## 6. QA Business Rules

| Rule | Spec Ref | Present in Prompts | Gap |
|---|---|---|---|
| Rule 1: "Missing evidence" never "Weak" | §12 Rule 1 | Yes — `system.py` Rule 2: `NEVER use "weak", "low", "absent", or "not a priority"` | None |
| Rule 4: Discovery gaps in neutral tone | §12 Rule 4 | Yes — `system.py` Rule 5: `Use phrasing like 'not yet qualified in captured evidence' — never 'the rep failed to'` | None |
| Rule 6: No internal terms (DRI) in UI | §12 Rule 6 | Yes — `system.py` Rule 6: `Never use internal framework names (DRI, MEDDPICC labels, etc.)` | None |
| Rule 6: Output uses "levers" not "DRI" | §12 Rule 6 | Yes — schema key is `levers` | None |
| Rule 7: Qualification detail shown once (themes) | §12 Rule 7 | **ABSENT** — no anti-duplication rule between dimensions and themes | **Gap** |

---

## 7. Test Coverage

| Test File | Present | Nominal | Error | Permission | Tenant Isolation |
|---|---|---|---|---|---|
| `signals/test_people_signal_model.py` | Yes | Yes | Yes (clean() violations) | N/A (model) | No |
| `signals/test_people_signal_api.py` | Yes | Yes | Yes | No | Yes (cross-tenant 404) |
| `signals/test_constraint_signal_model.py` | Yes | Yes | Yes (clean() violations) | N/A (model) | No |
| `signals/test_constraint_signal_api.py` | Yes | Yes | Yes | No | Yes (cross-tenant 404) |
| `signals/test_pain_impact_target_dept.py` | Yes | Yes | No | N/A | No |
| `signals/test_techstack_dc_reactivation.py` | Yes | Yes | No | N/A | No |
| `decision_cycles/test_deal_health_snapshot.py` | Yes | Yes | No | N/A (model) | No |
| `decision_cycles/test_deal_health_snapshot_api.py` | Yes | Yes | Yes (405 on writes) | Yes (writes blocked) | Yes (cross-tenant, cross-cycle) |
| `decision_cycles/test_deal_product.py` | Yes | Yes | Yes (duplicate, protect) | N/A (model) | No |
| `decision_cycles/test_deal_product_api.py` | Yes | Yes | Yes | No | Yes (cross-tenant, cross-cycle) |
| `product_catalog/test_product_catalog_model.py` | Yes | Yes | Yes | N/A (model) | Yes (same name cross-tenant) |
| `product_catalog/test_product_catalog_api.py` | Yes | Yes | Yes | Yes (individual 403) | Yes (cross-tenant) |
| `decision_cycles/test_readiness_score_service.py` | Yes | Yes | Yes (PENDING excluded) | N/A | No |
| `decision_cycles/test_people_consolidation_service.py` | Yes | Yes | Yes (PENDING excluded) | N/A | No |
| `ai_pipelines/test_deal_health_pipeline.py` | Yes | Yes | Yes (5 error variants) | N/A | No |
| `ai_pipelines/test_deal_health_evidence_builder.py` | Yes | Yes | Yes (empty cycle) | N/A | No |
| `ai_pipelines/test_deal_health_view.py` | Yes | Yes | Yes (502, 400) | Yes (401 unauth) | Yes (cross-tenant 400) |
| `decision_cycles/test_dc_workspace_actions.py` | Yes | Yes | Yes (404) | No | Yes (cross-tenant) |
| `decision_cycles/test_manager_note_model.py` | Yes | Yes | No | N/A (model) | No |
| `decision_cycles/test_manager_note_api.py` | Yes | Yes | Yes (400, 404) | Yes (individual 403, non-author 403) | Yes (cross-tenant) |
| `ai_pipelines/test_pipeline_atomic.py` | Yes | Yes | Yes (rollback on crash) | N/A | No |

**Summary:** All 21 test files present. API-level tests consistently cover tenant isolation. Permission tests present where role-based access applies (ProductCatalog, ManagerNote, DealHealthView). Model/service-level tests cover nominal + error but no tenant isolation (expected — that's the API layer's job).

---

## 8. Risks Identified

| # | Category | Severity | File:Line | Description |
|---|---|---|---|---|
| R1 | Spec deviation | **Critical** | `ai_pipelines/pipelines/deal_health.py:64` | TEMPERATURE=0.2, spec §10.4 requires 0.0 (conservative extraction) |
| R2 | Data integrity | **Critical** | `ai_pipelines/pipelines/deal_health.py:91-164` | `_create_run()` outside `transaction.atomic()` + `_finalize_run(SUCCESS)` outside atomic block. Snapshot and run finalization in separate transactions. Orphaned AIPipelineRun records possible on partial crash. |
| R3 | Spec deviation | **High** | `ai_pipelines/prompts/deal_health/diagnostic_v1.py` | Output schema key names differ from spec §10.3: `global_reading` vs `global_diagnostic`, `discovery_gaps` vs `gaps`, kind `qualification` vs `qualif` |
| R4 | Spec deviation | **High** | `ai_pipelines/views/deal_health_view.py` + `urls.py` | Missing `GET /by-cycle/{id}/` and history endpoints for deal-health (spec §10) |
| R5 | Business rule | **High** | `ai_pipelines/prompts/deal_health/system.py` | QA Rule 7 (no dimension/theme duplication) absent from system prompt |
| R6 | Spec deviation | **Medium** | `signals/models/blocker_signal.py` | No `target_department` FK — department-level blocker attribution absent (spec §11.5) |
| R7 | Security | **Medium** | `decision_cycles/views/manager_note_views.py:76-90` | `_resolve_parent_cycle()` bypasses ownership scope — any manager sees any tenant cycle. Documented TD-27 but tenant-wide coaching is broader than team-scoped intent |
| R8 | Functional | **High** | `accounts/services/filter_service.py:347-484` | `_filter_by_qualification` and `_filter_by_signals_freshness` are confirmed stubs — API params silently return unfiltered results |
| R9 | Security | **High** | TECH_DEBT.md TD-33 | Production throttle rate 500/min vs expected 30/min — possible misconfiguration |
| R10 | Security | **High** | TECH_DEBT.md TD-11 | Cache replay leakage: cached signal responses scoped by `source_activity` only, not `source_run` — stale signals from prior runs may leak |
| R11 | Data integrity | **Medium** | `permissions/checks.py:235` | Object-level permission checks not implemented (TODO in code) |
| R12 | Tech debt | **High** | `app_modules/accounts/views/views.py:359,760,803` + `services/filter_service.py:302,327` | 5 cross-layer wrong imports: `from apps.accounts.models import {Contact, TechStack, BuyingProcess}` inside `app_modules/` — will break if legacy `apps/` layer is removed |
| R13 | Data integrity | **Medium** | `decision_cycles/serializers.py:1033` | Deprecated `DecisionStep.manager_notes` free-text field still exposed as writable in `DecisionStepUpdateSerializer` despite being replaced by cycle-level ManagerNote model (TD-28) |
| R14 | Data integrity | **Medium** | TECH_DEBT.md TD-23 | 60s cache stale on `GET /decision_cycles/by-account/{uuid}/` after DC creation — `invalidate_tag` not called in `DecisionCycleViewSet.create` |

---

## 9. Technical Debt Introduced

| TD Ref | Status | Description |
|---|---|---|
| TD-26 | OPEN | Migrations 0015+0016 (ManagerNote) not squashed — schema churn. 0015 was hand-written with mismatches, 0016 auto-generated to reconcile. |
| TD-27 | OPEN | ManagerNote coaching is tenant-wide, not team-scoped. Any manager can access any cycle in the tenant. |
| TD-28 | OPEN | `DecisionStep.manager_notes` deprecated field still in DB. |
| TD-29 | OPEN | OverviewTab + ManagerNotesThread frontend does not match product intent (PO flagged). |
| TD-32 | OPEN | `test_nextstep_list_includes_source_quote_and_metadata` uses non-existent `summary` field — test always fails with TypeError. |
| TD-33 | OPEN | Production throttle rate 500/min vs expected 30/min. |
| TD-22 | OPEN | Four `get_*_data` methods in `CompanyAccountSerializer` are stubs returning None. |
| TD-11 | OPEN | Cache replay leakage — signals scoped by `source_activity`, not `source_run`. |
| TD-10 | OPEN | Deprecated `/transcript-signals/extract/` endpoint still live. |
| — | OPEN | 7 active `from apps.signals` imports in legacy `apps/` layer (not yet migrated to `app_modules`). |
| — | OPEN | 5 cross-layer wrong imports: `from apps.accounts.models` inside `app_modules/accounts/` (views.py:359,760,803 + filter_service.py:302,327). These will break when legacy `apps/` is removed. |
| TD-23 | OPEN | 60s cache stale on `GET /decision_cycles/by-account/{uuid}/` — `invalidate_tag` not called in `DecisionCycleViewSet.create`. |
| TD-28 | OPEN | `DecisionStep.manager_notes` deprecated field still exposed as writable in `DecisionStepUpdateSerializer:1033`. |
| — | OPEN | `campaign = None` and `signal_category = None` shadow overrides on TechStackSignal — intentional but fragile. |
| — | OPEN | `_filter_by_qualification` and `_filter_by_signals_freshness` stubs in `filter_service.py` — API params silently ignored. |
| — | OPEN | Multiple TODOs in `permissions/checks.py:235`, `territories/views/views.py:394,408,447`, `decision_cycles/constants.py:77`, `accounts/serializers.py:253`. |

`TECH_DEBT.md` exists at repo root and tracks TD-1 through TD-37. Well-maintained.

---

## 10. Out-of-Spec Additions

### 10.1 ManagerNote

- **Model:** `decision_cycles/models.py` — DecisionCycle FK + content TextField + inherited audit fields
- **Views:** Full CRUD in `manager_note_views.py` — manager/admin create, owner/manager/admin read, author/admin delete
- **Tests:** `test_manager_note_model.py` + `test_manager_note_api.py` — nominal, error, permission, tenant isolation covered
- **Documentation:** Referenced in TECH_DEBT.md (TD-27, TD-28, TD-29). No dedicated spec document.
- **Impact:** Backend is solid and well-tested. Frontend (ManagerNotesThread.jsx) flagged by PO as not matching product intent (TD-29). Coaching scope is tenant-wide, not team-scoped (TD-27).

### 10.2 OverviewTab

- **Frontend:** `frontend/src/sections/accounts/dc-workspace/OverviewTab.jsx` exists
- **Spec §3** defines 5 tabs (Timeline, People, Products & Financial, Strategic, Signals) — no Overview
- **Impact:** Additive — does not break existing tabs. Contains ReadinessScoreGauge + DealHealthView + ManagerNotesThread. Acceptable as a dashboard entry point but should be acknowledged as beyond-spec.

### 10.3 6 Tabs vs 5

The delivered DC Workspace has 6 tabs: Overview + Timeline + People + Products & Financial + Strategic + Signals. The spec §3 defined 5 (no Overview). The Overview tab consolidates readiness, deal health, and manager notes into a single landing view. This is an additive change that does not conflict with spec tabs.

---

## 11. Recommendations

### Critical — Fix Before Prep-Call

| # | Item | Action |
|---|---|---|
| 1 | TEMPERATURE=0.2 | Change to 0.0 in `deal_health.py:64` — single-line fix, spec §10.4 is explicit |
| 2 | Atomic boundary gap | Move `_create_run()` inside `transaction.atomic()` and include `_finalize_run(SUCCESS)` within the same atomic block. Test with `test_pipeline_atomic.py`. |

### High — Fix in Current Sprint

| # | Item | Action |
|---|---|---|
| 3 | Output schema key names | Decide: align code to spec (`global_diagnostic`, `gaps`, `qualif`) or update spec to match code (`global_reading`, `discovery_gaps`, `qualification`). Either way, frontend + writer validation must match. |
| 4 | Missing deal-health GET endpoints | Clarify if `GET /health-snapshots/` + `latest/` on DC namespace satisfies the spec intent, or if ai-pipelines namespace routes are also needed. |
| 5 | QA Rule 7 missing | Add anti-duplication instruction to system prompt: themes should synthesize across signals, not repeat dimension-level detail. |
| 6 | Stubbed filters | Either implement `_filter_by_qualification` / `_filter_by_signals_freshness` or remove the API params to avoid silent no-ops. |
| 7 | TD-33 throttle rate | Verify 500/min is intentional for production or reduce to 30/min per original spec. |

### Acceptable — Defer to Polish/Next Sprint

| # | Item | Rationale |
|---|---|---|
| 8 | BlockerSignal target_department | Low usage risk — contact-level attribution covers most cases. Add department FK when blocker UX is refined. |
| 9 | ManagerNote scope (TD-27) | Tenant-wide coaching is functional. Team-scoping is a product decision for next sprint. |
| 10 | OverviewTab beyond spec | Additive, no harm. Document as intentional in spec update. |
| 11 | Migration squash TD-26 | No functional risk. Squash before next major migration batch. |
| 12 | Legacy `apps.signals` imports | All in legacy layer, not `app_modules`. Migrate when legacy layer is addressed. |
| 13 | TD-32 broken test | Fix `summary` field reference — trivial but not blocking. |
