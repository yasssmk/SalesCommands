# AUDIT_EXISTANT — SalesCommands Repository Map

**Date:** 2026-07-06
**Baseline commit:** `039e86e` (main, 2026-06-19)
**Scope:** Full repository (backend + frontend), read-only, factual. No fixes, no recommendations.
**Exclusions:** `node_modules`, `.venv`, `.git`, `migrations`, `.next`, `dist`, `build`, `frontend-Model/.yarn`.

---

## 1. Repository tree (~3 levels)

```
SalesCommands/
├── README.md                      (empty — title line only)
├── TECH_DEBT.md                   (TD-1 … TD-51 technical-debt journal)
├── AUDIT_DC_POST_LIVRAISON.md     (prior DC Workspace post-delivery audit, 2026-06-16)
├── crm-schema.mermaid
├── TEST_TRANSCRIPT.txt / test.py / TEST csv/
├── guide/
│   ├── MODULE_IMPLEMENTATION_WORKFLOW.md
│   └── To_IMPLEMENT/
├── .github/workflows/             (npm-stage-check.yml, yarn-stage-check.yml)
├── backend/
│   ├── manage.py / requirements.txt / pytest.ini / conftest.py / Procfile
│   ├── salescommands/             (settings.py, urls.py, asgi.py, wsgi.py)
│   ├── app_modules/               ← current module tree (UUID PK, multi-tenant)
│   │   ├── accounts/              (models.py, serializers.py, filters.py, views/, services/)
│   │   ├── activities/            (models.py, serializers.py, filters.py, views/, services/, signals/)
│   │   ├── ai_pipelines/          (models/, serializers/, views/, services/, pipelines/,
│   │   │                           prompts/, providers/, management/, config.py)
│   │   ├── campaigns/             (models/, serializers/, views/, services/, signals/,
│   │   │                           utils/, config/, constants.py)
│   │   ├── contacts/              (models.py, serializers.py, filters.py, views/)
│   │   ├── core_modules/          (models/ — ModuleBaseModel, StandardDepartment; serializers/)
│   │   ├── decision_cycles/       (models.py, serializers.py, views/, services/, signals/)
│   │   ├── product_catalog/       (models.py, serializers.py, views.py)
│   │   ├── sequences/             (pure Python, no Django app — base/outbound/targeted/
│   │   │                           renewal sequences + dispatcher)
│   │   ├── signals/               (models/ ×9+base, serializers/, views/, services/,
│   │   │                           signals/, filters.py, constants.py)
│   │   ├── tech_catalog/          (models.py, serializers.py, views.py)
│   │   └── territories/           (models.py, serializers.py, views/)
│   ├── apps/                      ← legacy first-generation app tree (still registered)
│   │   ├── accounts/  activities/  campaign/  core_apps/  leads/
│   │   ├── LLM_calls/  opportunities/  products/  sales_insight/
│   │   ├── sequence/  signals/
│   ├── core/                      (client_scope.py, error_messages.py, exceptions.py,
│   │   │                           apps_shared_methods.py, cache_utils.py, throttling.py,
│   │   └── http/ logging/ middlewares/ utils/ views/)
│   ├── permissions/               (mixins.py, owner_scope.py, scoping.py, policies.py, registry/)
│   ├── end_users/                 (auth, users, roles, teams, orgs, quotas, plans)
│   ├── product_admin/  ops/
│   └── tests/                     (ai_pipelines/ decision_cycles/ integration/
│                                   product_catalog/ signals/)
├── frontend/                      ← live Next.js app
│   ├── package.json / next.config.mjs / vitest.config.js / jsconfig.json
│   └── src/
│       ├── api/ app/ components/ config/ contexts/ hooks/ layout/
│       ├── menu-items/ sections/ themes/ utils/ views/ __tests__/
│       └── (public/ assets)
└── frontend-Model/                ← Mantis MUI template kept as reference (TD-44,
                                     not imported anywhere; ~124 known npm vulns)
```

---

## 2. Backend architecture (`backend/app_modules/`)

Two app trees coexist. `app_modules/` is the current generation (UUID PK, `ModuleBaseModel` + `ClientScopeManager` multi-tenancy). `backend/apps/` is the legacy generation — see the note at the end of this section.

### 2.1 accounts (`module_accounts`)
- **Purpose:** UUID-based `CompanyAccount` for the Administration module; replaces legacy `apps.accounts.Account` (`models.py:2-7`).
- **Models:** `CompanyAccount` → `parent_company` FK self, `partners` M2M self, `account_owner` FK User. Choices: `AccountType`, `AccountClassification`.
- **Serializers:** `AccountManagerSerializer`, `CompanyAccountListSerializer`, `CompanyAccountSerializer`, `CompanyAccountCreateSerializer`, `CompanyAccountUpdateSerializer`, `AccountWorkspaceSerializer`, `WorkspaceStatsSerializer`.
- **Views:** `CompanyAccountViewSet`, `CompanyAccountChoicesView`, `CompanyAccountBulkViewSet`.
- **Services:** `AccountFilterService` (`services/filter_service.py`). Note: `_filter_by_qualification` and `_filter_by_signals_freshness` are no-ops (TECH_DEBT TD-38).
- **Filters:** `CharInFilter`, `CompanyAccountFilter`.
- **Patterns:** ViewSet = `OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, ModelViewSet`; model = `ModuleBaseModel, ClientScopeManager.ModelMixin, ContactDetailsMixin`.

### 2.2 activities (`module_activities`)
- **Purpose:** Operational sales work (meetings/calls/emails/tasks) linked to accounts/contacts/users, optionally cycle/step/campaign (`models.py:2-11`).
- **Models:** `Activity` → `account` FK CompanyAccount, `contacts` M2M Contact, `owner` FK User, `invited_users` M2M User, `decision_cycle` FK, `decision_step` FK, `campaign` FK, `campaign_account` FK, `campaign_contact` FK, `source_activity` FK self, `source_decision_cycle` FK, `next_step_signal` FK NextStepSignal.
- **Serializers:** `ActivityAccountSerializer`, `ActivityContactSerializer`, `ActivityUserSerializer`, `ActivityDecisionCycleSerializer`, `ActivityDecisionStepSerializer`, `ActivityMinimalSerializer`, `ActivityCompactSerializer`, `ActivityListSerializer`, `ActivitySerializer`, `ActivityCreateSerializer`, `ActivityUpdateSerializer`.
- **Views:** `ActivityViewSet`, `ActivityChoicesView`.
- **Services:** `ActivityCreationService`; `ActivitySequenceService` + `SequenceScope` enum.
- **Filters:** `CharInFilter`, `ActivityFilter`. **Signals:** `signals/cache_invalidation.py`.

### 2.3 ai_pipelines (`module_ai_pipelines`)
- **Purpose:** LLM orchestration — transcript signal extraction, deal-health, next-steps, prep-call. `AIPipelineRun` audits every LLM invocation (stores sha256 `input_hash`, never the transcript) (`models/pipeline_run.py:2-16`).
- **Models:** `AIPipelineRun` → `source_activity` FK Activity, `source_decision_cycle` FK DecisionCycle; `PrepCallSnapshot` → `activity` FK, `pipeline_run` FK, `target_contact` FK Contact.
- **Serializers:** `PrepCallRunInputSerializer`, `PrepCallSnapshotSerializer`, `TranscriptSignalsExtractInputSerializer`, `DealHealthRunInputSerializer`.
- **Views:** `ActivityExtractionView`, `DealHealthRunView`, `LastRunView`, `PrepCallRunView`, `PrepCallByActivityView` (all `BaseAPIView`).
- **Services:** `TranscriptSignalExtractor`, `DealHealthEvidenceBuilder`, `DealHealthWriter`, `NextStepExtractor`, `safety_filter.py` (`passes_safety_filter`, `safe_float`), `prep_call/` (`input_pack_assembler.py`, `mode_resolver.py`, `rhetoric_guide.py`).
- **Other:** `pipelines/` (base, deal_health, next_steps, prep_call, transcript_signals), `providers/` (base, claude_provider, openai_provider), versioned `prompts/`, management command `cleanup_pipeline_runs`. No filters.

### 2.4 campaigns (`module_campaigns`)
- **Purpose:** Campaigns of type OUTBOUND (territory-based, auto-sequences) and TARGETED (manual). Lifecycle DRAFT→ACTIVE→PAUSED→COMPLETED/CANCELLED (`models/campaign.py:2-9`).
- **Models:** `Campaign` → `territories` M2M Territory, `owner`/`executor` FK User; `CampaignAccount` → `campaign` FK, `account` FK, `target_departments` M2M StandardDepartment, `target_contacts` M2M Contact; `CampaignContact` → `campaign_account` FK, `contact` FK; `CampaignObjective` → `campaign` FK; `CampaignMember` → `campaign`/`user`/`added_by` FK.
- **Serializers:** List/Detail/Create/Update families for Campaign, CampaignAccount, CampaignContact, CampaignObjective, CampaignMember (~19 classes).
- **Views:** `CampaignViewSet`, `CampaignAccountViewSet`, `CampaignContactViewSet`, `CampaignObjectiveViewSet`.
- **Services:** `CampaignAnalyticsService`, `CampaignLifecycleService`, `CampaignCreationService`, `CampaignExecutionService`.
- **Other:** `signals/signals.py` (auto-create TARGETED campaign on User post_save; auto-complete CampaignAccount on CampaignContact post_save), `utils/scheduling.py`, `config/settings.py`, `constants.py` (status enums + transition tables). No filters.

### 2.5 contacts (`module_contacts`)
- **Purpose:** Contact person linked to a CompanyAccount (`models.py:2-6`).
- **Models:** `Contact` → `account` FK CompanyAccount, `standard_department` FK StandardDepartment; `InfluenceLevel` choices.
- **Serializers:** `ContactAccountSerializer`, `ContactListSerializer`, `ContactSerializer`, `ContactCreateSerializer`.
- **Views:** `ContactViewSet`, `ContactChoicesView`, `ContactBulkViewSet`. **Filters:** `CharInFilter`, `ContactFilter`. No services.

### 2.6 core_modules (`core_modules`)
- **Purpose:** Shared bases for the `app_modules` tree.
- **Models:** `ModuleBaseModel` (abstract — §4.3), `StandardDepartment` (plain `models.Model`, tenant-shared reference).
- **Serializers:** `StandardDepartmentSerializer`. No views/urls mounted.

### 2.7 decision_cycles (`decision_cycles`)
- **Purpose:** `DecisionCycle` = buyer-seller decision process container; `DecisionStep` = individual step (`models.py:2-7`).
- **Models:** `DecisionCycle` → `owner` FK User, `account` FK CompanyAccount, `source_campaign` FK Campaign; `DecisionStep` → `cycle` FK, `previous_step` FK self, `standard_department` FK, `departments` M2M, `contacts` M2M; `DecisionStepContact`, `DecisionStepDepartment` (through models); `DealHealthSnapshot` → `decision_cycle` FK, `pipeline_run` FK AIPipelineRun; `DealProduct` → `decision_cycle` FK, `product_catalog_entry` FK ProductCatalog; `ManagerNote` → `decision_cycle` FK.
- **Serializers:** ~21 classes (List/Detail/Create/Update for cycles & steps, timeline serializers, DealHealthSnapshot, DealProduct, ManagerNote).
- **Views:** `DecisionCycleViewSet`, `DecisionStepViewSet`, `DecisionCycleChoicesView`, `DealProductViewSet` (+ shared `CycleScopedMixin`), `DealHealthSnapshotViewSet`, `ManagerNoteViewSet`.
- **Services:** `ReadinessScoreService`, `CycleAggregationService`, `NextStepDraftService`, `CompletenessScoreService`, `PeopleConsolidationService`, `StepAggregationService`, `StepStatusDerivationService`.
- **Signals:** `signals/readiness_recompute.py` — cross-module receivers (§6).

### 2.8 product_catalog (`product_catalog`)
- **Purpose:** Tenant-level product master catalog; unique on (client_id, name) (`models.py:2-16`).
- **Models:** `ProductCatalog` (no relational FKs beyond audit fields).
- **Serializers:** List/Detail/Create/Update. **Views:** `ProductCatalogViewSet`. No services/filters/signals.

### 2.9 sequences (not a Django app — no apps.py, not in INSTALLED_APPS)
- **Purpose:** Pure-Python campaign sequence definitions, ported from `apps/sequence/` with no `apps/` dependency (`base_sequence.py:2-11`).
- **Classes:** `Sequence` (ABC), `OutboundSequence`, `TargetedSequence`, `RenewalSequence`, `SequenceDispatcher` (routes sequence_type → class). No models/views/urls.

### 2.10 signals (`module_signals`)
- **Purpose:** Sales-signal extraction/validation. Concrete types inherit abstract `BaseSignal`; lifecycle PENDING→VALIDATED/REJECTED/MERGED managed by `SignalManager` (`models/base_model.py:2-15`).
- **Models:** abstract `BaseSignal` (§4.3) → `account` FK, `source_activity` FK Activity (SET_NULL), `source_run` FK AIPipelineRun, `decision_cycle` FK, `campaign` FK, `requested_by`/`validated_by` FK User. Concrete: `PainSignal` (+`target_department`, `related_techstack` FK TechCatalog), `ObjectiveSignal` (+`target_contact`, `target_department`), `TechStackSignal` (+`tech_catalog_entry` FK TechCatalog, `usage_department`), `BlockerSignal` (+`contact`), `ConstraintSignal` (+`target_department`), `ImpactSignal` (+`target_department`), `NextStepSignal` (+`suggested_contacts` M2M Contact), `PeopleSignal` (+`target_contact`, `target_department`). Non-signal: `SignalClusterArchival`.
- **Serializers:** base family (`SignalSourceSerializer`, `BaseSignalList/Detail/Create/UpdateSerializer`, `SignalLLMSerializer`); per-type List/Detail/Create/Update + `_XDisplayMixin` per type; cluster serializers (`SignalClusterListSerializer`, `SignalClusterDetailSerializer` + 7 private tech-stack sub-serializers).
- **Views:** `BaseSignalViewSet` + 8 concrete `*SignalViewSet`; `SignalClusterListView`, `SignalClusterDetailView`, `SignalClusterArchiveView`, `SignalClusterUnarchiveView`; `SignalCountsByActivityView`; `SignalChoicesView`.
- **Services:** `SignalManager`, `SignalClusterService`, `SignalDataService`, `signal_priority_service.py` (priority-score functions per type + `bucket_from_score`).
- **Filters:** `CharInFilter`, `SignalFilter`. **Signals:** `signals/cache_invalidation.py` (receivers on all 9 models).

### 2.11 tech_catalog (`tech_catalog`)
- **Purpose:** Tenant-level technology master catalog; identity = (company_name, product_name) (`models.py:2-15`).
- **Models:** `TechCatalog`. **Serializers:** List/Detail/Create/Update. **Views:** `TechCatalogViewSet`. Intentionally flat; no services/filters/signals.

### 2.12 territories (`territories`)
- **Purpose:** Sales segmentation — saved filters/segments of accounts or contacts (`models.py:2-6`).
- **Models:** `Territory` → `owner` FK User; `TerritoryType` choices.
- **Serializers:** `TerritoryValidationMixin`, Owner/List/Detail/Create/Update serializers.
- **Views:** `TerritoryViewSet`, `TerritoryBulkViewSet`. No services/filters.

### 2.13 Legacy `backend/apps/` tree
`apps/` is the first-generation app tree (integer PK, pre-multitenant refactor). It is **still registered and live**: `settings.py:203-246` lists `apps.core_apps`, `apps.accounts` (commented `#OBSOLETE`), `apps.signals`, `apps.campaign`, `apps.opportunities`, `apps.sequence`, `apps.activities`, `apps.leads`, `apps.LLM_calls`, `apps.products`, `apps.sales_insight` in `INSTALLED_APPS`; `salescommands/urls.py:81-91` mounts most of them under a "Path to validate" comment block. New module docstrings reference the migration ("separate from legacy apps.accounts.Account"; sequences "Ported from apps/sequence/"). `core/error_messages.py:193` still carries `CampaignErrorMessages` annotated `#TO DELETE`, superseded by `CampaignModuleErrorMessages` (`:292`).

---

## 3. Frontend architecture (`frontend/src/`)

**Stack:** Next.js `^15.5.19` (App Router, JSX not TS), React 18, MUI 5 (+ Ant Design icons), SWR `^2.3.4` (primary data layer; `@tanstack/react-query` present in deps but barely used), `@tanstack/react-table` 8, Formik `^2.4.6` + Yup, axios, next-auth + custom JWT-cookie flow, notistack, Vitest + Testing Library. Absolute imports rooted at `src/` (`jsconfig.json`).
`frontend-Model/` is the Mantis admin-dashboard starter the app was scaffolded from — not imported anywhere (TD-44).

### 3.1 Zone inventory

| Zone | Files | Contents |
|---|---|---|
| `api/` | 22 | `_swr.js`, `auth.js`, `menu.js`, `snackbar.js` + subfolders `accounts/` (activities.js, decisionCycles.js), `admin/` (accounts, roles, teams, users), `aiPipelines/` (activityExtraction, dealHealth, lastRun, prepCall), `businessData/` (contacts, productCatalog, techCatalog), `campaigns/` (campaigns.js), `signals/` (painImpacts, signalClusters, signalCounts, signals), `territories/` |
| `components/` | 123 | Root: `MainCard.jsx`, `WorkspaceLayout.jsx`, `WorkspaceBreadcrumb.jsx`, `ErrorBoundary.jsx`, `EditableTextBlock.jsx`, loaders. Subfolders: `@extended/` (13 MUI-extension primitives), `third-party/` (36 — `react-table/` ×16, dropzone, map, Notistack), `cards/` (33), `AsyncSelection/` (7), `csv/`, `chips/`, `filters/`, `table/` (2), `bulk/`, `tree/`, `auth/`, misc |
| `sections/` | 202 | `accounts/` 79 (dc-workspace 17, decision-cycles 22, signals 16, activities 10, contacts 7, workspace 7) · `activities/` 41 (signals 27, workspace 11, nextSteps 3) · `admin/` 39 (users 16, accounts 12, roles 7, teams 4) · `campaigns/` 22 (workspace 11, create 5) · `territories/` 12 · `auth/` 5 · `businessData/` 4 |
| `views/` | 21 | Thin per-route compositions: accounts (workspace, dc-workspace, decisionSteps), activities/workspace, admin (roles/teams/users lists), auth/login, businessData (accounts, techCatalog), campaigns (list, workspace), territories (list, workspace), maintenance (404/500/coming-soon/under-construction) |
| `hooks/` | 15 | `useAuth.js` (AuthProvider + tenantId), `useCurrentUser`, `useConfig`, `useUserPermissions`, `useOwnerScope`, `useMenuState`, `useLocalStorage`, `useLazyStyle`, `useRetryCountdown`, `useBulkOperationSync`, `usePipelineRunner`, `useTerritoryFilters`, `useDecisionStepEdit`, `useActivityAllSignals`, `useDCAllSignals` |
| `contexts/` | 1 | `ConfigContext.jsx` (theme/i18n/layout; only formal Context file — AuthProvider lives in `hooks/useAuth.js`) |
| `utils/` | 28 | `axiosClient.js`, `swrFetcher.js`, error chain (`errorHandler.js`, `errorMessages.js`, `displayError.js`, `formErrorHandler.js`, `bulkErrorHandler.js`), `snackbar.js`, `pollOperationStatus.js`, `retryLogic.js`, `validators.js`, `logSanitizer.js`, `monitoring.js`, csv utils ×3, route guards, locales ×4 |
| `app/` | 32 | Next App Router: groups `(auth)` and `(protected)`; routes for accounts/[id] (+ dc/[cycleId], decisionSteps/[stepId]), activities/[id], admin/{roles,teams,users}, businessData/{accounts,contacts,techCatalog}, campaigns (+[id]), territories (+[id]); `ProviderWrapper.jsx`; API route `api/csp-report/route.js`. Anomaly: `businessData/contacts/pages.jsx` is misnamed (not a valid Next page file) |
| `menu-items/` | 5 | `index.js` aggregates `home, goToMarket, businessData, admin`; feature-flag aware via `config/features` |
| `layout/` | 33 | `DashboardLayout/` (Mantis chrome: Drawer/Header/Footer/Navigation), `SimpleLayout/`, `ResourceGuardLayout.jsx` |
| `config/` | 5 | `auth.js` (API base URL + TIMEOUT_PROFILES), `features.js` (flags), `formatters.js`, `swr.js`, `theme-config.js` |
| `themes/` | 64 | MUI theme customization (Mantis-derived) |
| `__tests__/` | 26 | Vitest — mostly signals domain (17 files), nextSteps (3), activities workspace, aiPipelines API, hooks, smoke |

### 3.2 Recurring patterns
- **SWR read hooks** (`api/signals/signals.js:341-389`, `api/admin/users.js:127-224`): private `endpoints` object per file; keys built with `tenantKey(url, tenantId)` (`api/_swr.js:29`) → `[url, tenantId]` tuple, `null` disables fetch; no per-hook fetcher — global fetcher `utils/swrFetcher.js` injected via `SWRConfig` in `app/ProviderWrapper.jsx:109`; hooks return memoized renamed fields (`{signals, signalsLoading, …, mutateSignals}`); data unwrapped defensively (`data?.data?.results ?? data?.results ?? []`).
- **Mutations** are plain async functions (not hooks) calling `api.post/patch/delete` and returning normalized `{success, data, error, status, response}`.
- **Cache invalidation:** no tag system — SWR prefix mutation. `revalidateByPrefix` / `revalidateMultiple` (`api/_swr.js:72-93`) match `[url, tenantId]` tuples by URL prefix; bulk operations use `handleBulkRevalidation` (`_swr.js:302`) with 202/408/504 detection and progressive polling (`pollOperationStatus`).
- **axios:** `utils/axiosClient.js` factory builds 5 timeout-profile clients (`critical/widget/mutation/bulk/auth`); shared interceptors add correlation-id, auto Idempotency-Key on writes, single-flight 401 refresh, 408 tagging, 429 Retry-After parsing.
- **Forms:** 39 files use Formik. Canonical shape: `useFormik` + `<FormikProvider>` + `<Form>` inside an MUI `<Dialog>`, module-level Yup schema, `buildInitialValues()`/`sanitizePayload()` helpers, submit → api mutation → `handleFormikError` / `displaySuccessSnackbar` (e.g. `sections/admin/roles/FormRoleAdd.jsx:28-61`, every `Form{User,Account,Team,Contact,Territory,TechCatalog}Add/Edit.jsx`, inline signal forms).
- **Dialogs/modals:** `<Entity>Modal.jsx` (form container wrapping a `Form*Add/Edit`, ~24 files); `Alert<Entity>{Delete,BulkDelete,…}.jsx` confirmation dialogs; `*Drawer.jsx` slide-over detail panels (`SignalQuickDrawer`, `StepDetailDrawer`, `SignalClusterDetailDrawer`, …). ~50 section files render `<Dialog>` directly.
- **Tables:** react-table v8 helper suite in `components/third-party/react-table/` (16 files) but `useReactTable` is invoked in only one place — `components/table/Table.jsx` (shared generic table). Several feature tables hand-roll raw MUI `<Table>` instead (`sections/admin/roles/PermissionsMatrix.jsx`, `sections/accounts/dc-workspace/ProductsTab.jsx`, `components/csv/CSVDataPreview.jsx`, `sections/accounts/activities/ActivityTable.jsx`, admin `list.jsx` views). Adoption of the shared wrapper is partial.
- **Cards:** `components/MainCard.jsx` is the app-wide wrapper; `components/cards/` groups domain cards (`signals/` PainCard/ObjectiveCard/ImpactCard/TechStackCard/SignalCard/SignalDetailCard/SignalClusterCard, `statistics/` ×7, `nextSteps/AISuggestionCard`, ContactCard, UserCard, ActivityMiniCard…). Feature-local cards also exist (`sections/campaigns/CampaignCard.jsx`, `sections/territories/TerritoryCard.jsx`).
- **Error/snackbar chain:** component → `displayErrorSnackbar(err)` (`utils/displayError.js:65`) → `showSnackbar.fromError` (`utils/snackbar.js:240`) → `getErrorDisplayInfo` (`utils/errorMessages.js:234`, status→severity/title/fallback maps) → `openSnackbarBase` (`api/snackbar.js`) rendered by `components/@extended/Snackbar.jsx`. Forms route through `handleFormikError` (`utils/formErrorHandler.js`). Global SWR `onError` (`ProviderWrapper.jsx:207`) surfaces only 429s and pauses SWR.
- **Providers:** only two Contexts — `ConfigProvider` and `AuthProvider`. Provider tree (`ProviderWrapper.jsx:327-346`): Config → ThemeCustomization → Auth → SWRConfig → RTLLayout → Locales → ScrollTop → Notistack → Snackbar.

---

## 4. Detected standards & conventions

### 4.1 Naming conventions
- **Backend endpoints:** module mounts are kebab/plural (`company-accounts/`, `module-signals/`, `module-ai-pipelines/`, `decision_cycles/` — note mixed kebab vs snake in mount names). Detail routes use `<uuid:pk>`; verb actions as sub-paths (`/complete/`, `/validate/`, `/mark-completed/`); scoped reads as `by-account/`, `by-campaign/`, `by-activity/`.
- **Backend classes:** `<Entity>{List,Detail,Create,Update}Serializer`; `<Entity>ViewSet`; `<Entity>ChoicesView`; services as `<Domain><Role>Service`; error-message constant classes `<Domain>ErrorMessages`.
- **Frontend files:** React components `PascalCase.jsx`; non-React utils/api `camelCase.js`; Next route files `page.jsx`/`layout.jsx`; route groups `(auth)`/`(protected)`; dynamic segments `[id]`, `[cycleId]`, `[stepId]`.
- **Frontend components:** `Form<Entity>{Add,Edit,BulkEdit}`, `<Entity>Modal`, `Alert<Entity>{Delete,…}`, `*Drawer`, `*Tab`/`*Tabs`, `*Card`, `Wizard*`/`Inline*Form`, `Editable*`.
- **Frontend hooks/API:** read hooks `useGet<Entity>[By<Scope>]`; mutations `create/insert/update/delete<Entity>`; SWR helpers `tenantKey`/`matchKey`/`revalidate*`.
- **Section banner comments:** `// ==============================|| TITLE ||============================== //` throughout. Mixed French/English comments and emoji log markers (`✅`, `🔑`, `⏱️`) are common.

### 4.2 Docstring structure (backend)
Every module opens with a `# path` comment then a module docstring stating purpose; classes and methods carry docstrings; business rules are documented inline at length (why `source_activity` is SET_NULL, why LLM signals can't be created VALIDATED, M2M-after-save splitting). Some docstrings/comments are French. Representative: `ModuleBaseModel.save` — *"Uses self._state.adding instead of self.pk to detect new instances because UUID primary keys are auto-generated before save()."*

### 4.3 Base abstractions
- **`ModuleBaseModel`** (`app_modules/core_modules/models/moduleBaseModels.py:18`): abstract; UUID PK, `client_id` UUID (indexed, `editable=False`), `created_by`/`updated_by` FK User (SET_NULL), timestamps, `Meta.ordering=['-created_at']`, custom `save(*, user=, client_id=)` setting tenant/audit fields on create.
- **`ClientScopeManager`** (`core/client_scope.py:20`): container with `ModelMixin` (client-scoped unique_together/indexes helpers), `SerializerMixin` (client_id from `request.auth['client_account']`, scoped uniqueness validation), `ViewMixin` (`get_client_id` from JWT, `filter_queryset_by_client`), plus `perform_create/update/delete` enforcing tenant isolation (`client_id` immutable on update).
- **`BaseAPIView`** (`core/apps_shared_methods.py:40`) = `ClientScopeManager.ViewMixin + APIView`: generic single+batch CRUD, `StandardResultsSetPagination` (page_size 10 / max 100), central `handle_exception` (`:371`) mapping DRF exceptions to standardized payloads.
- **Standard ViewSet stack:** `OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet` (mixins from `permissions/`, driven by per-view `action_policies` dicts + the permission registry `permissions/registry/`).
- **`BaseSignal`** (`app_modules/signals/models/base_model.py:32`): abstract signal base — universal FKs (§2.10) + `canonical_key`, `source_quote`, `confidence`, `is_inferred`, `signal_category`, `metadata` JSON, `source`, `status` (default PENDING), `original_value` JSON. `save()` (`:291`) enforces: MANUAL → VALIDATED with `confidence=None` (create only); LLM-sourced may not be created VALIDATED.
- **`SignalManager`** (`signals/services/signal_manager.py:62`): stateless classmethods `create` (routes `signal_type` → model, propagates decision_cycle/campaign/step from `source_activity`), `validate` (TechStack requires `tech_catalog_entry`), `reject`, `reopen`, `edit` (snapshots `original_value`, flips LLM_EXTRACTED→LLM_MODIFIED).
- **`BaseSignalViewSet`** (`signals/views/base_views.py:78`): serializer routing by action, per-action optimized querysets, `perform_create` → `SignalManager.create`, PUT treated as PATCH, `@action` validate/reject/reopen with audit_log + `_invalidate_signal_caches`.
- **Error chain:** backend `core/error_messages.py` (gettext-lazy constant classes per domain) raised via `Standardized*` exceptions (`core/exceptions.py`) → formatted by `BaseAPIView.handle_exception` → frontend `utils/errorMessages.js` `getErrorDisplayInfo` → `displayErrorSnackbar` (`utils/displayError.js`). Note stray typo `CoreErrorMessages.AUTH_REQUIRED = "Authentication required33"` (`error_messages.py:24`).
- **Cache invalidation tags (backend):** Django-signal receivers per module (`signals/signals/cache_invalidation.py:141-396`, `activities/signals/cache_invalidation.py:65-76`) bust named tags (e.g. `SIGNALS_CACHE_TAG`, `SIGNAL_CLUSTERS_CACHE_TAG`); viewsets also invalidate explicitly (e.g. `DecisionCycleViewSet` invalidates `decision_cycles`, `activities`, `accounts` tags — TD-23). Redis backend via `django-redis` (`core/cache_utils.py`); campaign dashboard cached 30s (`campaign_views.py:716-735`).

---

## 5. REST endpoints inventory

Project root (`salescommands/urls.py`): `healthz/`, `core/`, `ops/`, `admin/`, the 10 app_modules mounts below, plus legacy mounts (`app/accounts/`, `leads/`, `activities/`, `opportunities/`, `signals/`, `campaign/`, `app/products/`, `insights/`, `client/`, `product_admin/`) under a "Path to validate" comment.

### core (`core/`)
- `operations/<key>/status/` → `OperationStatusView`

### accounts (`company-accounts/`)
- `choices/` → CompanyAccountChoicesView
- `bulk-create/` | `bulk-update/` | `bulk-delete/` → CompanyAccountBulkViewSet
- `` (list/create), `<uuid:pk>/` (CRUD) → CompanyAccountViewSet
- `<uuid:pk>/workspace/` | `/qualification/` | `/tech-stacks/` | `/hierarchy/` → CompanyAccountViewSet

### activities (`module-activities/`)
- `choices/` → ActivityChoicesView
- `create-with-entities/`, `my-activities/`, `by-account/`, `by-step/`, `overdue/`, `upcoming/`, `unlinked/by-account/<uuid>/` → ActivityViewSet
- `` , `<uuid:pk>/` CRUD → ActivityViewSet
- `<uuid:pk>/complete/` | `/reopen/` | `/cancel/` | `/record-no-answer/` → ActivityViewSet

### ai_pipelines (`module-ai-pipelines/`)
- `activity-extraction/run/` → ActivityExtractionView
- `deal-health/run/` → DealHealthRunView
- `last-run/` → LastRunView
- `prep-call/run/` → PrepCallRunView
- `prep-call/by-activity/<uuid>/` → PrepCallByActivityView
- (legacy `/transcript-signals/extract/` deprecated in Sprint B5 — TD-10, Sunset header 2026-12-01)

### campaigns (`campaigns/`)
- `my-campaigns/`, `targeted/`, `` , `<uuid:pk>/` CRUD → CampaignViewSet
- `<uuid:pk>/start|pause|resume|complete|cancel/` → CampaignViewSet
- `<uuid:pk>/dashboard/` | `/summary/` | `/playlist/` → CampaignViewSet
- `<uuid:pk>/generate-activities/` | `/log-response/` | `/cancel-planned/` → CampaignViewSet
- `accounts/by-campaign/`, `accounts/bulk-add/`, `accounts/bulk-remove/`, `accounts/enroll-target/`, `accounts/` + `<uuid:pk>/` CRUD, `accounts/<uuid:pk>/start-progress|request-callback|resume-callback|mark-completed|mark-stopped|toggle-contact/` → CampaignAccountViewSet
- `contacts/` + `<uuid:pk>/` CRUD, `contacts/<uuid:pk>/start-progress|request-callback|resume-callback|mark-completed|mark-stopped|pause|resume|reactivate/` → CampaignContactViewSet
- `objectives/by-campaign/`, `objectives/choices/`, `objectives/` + `<uuid:pk>/` CRUD → CampaignObjectiveViewSet

### contacts (`contacts/`)
- `choices/` → ContactChoicesView; `bulk-create|bulk-update|bulk-delete/` → ContactBulkViewSet
- `` , `<uuid:pk>/` CRUD; `<uuid:pk>/mark-email-invalid|mark-phone-invalid|mark-opted-out/` → ContactViewSet

### decision_cycles (`decision_cycles/`)
- `choices/` → DecisionCycleChoicesView; `` , `<uuid:pk>/` CRUD → DecisionCycleViewSet
- `by-account/<uuid>/`, `<uuid:pk>/close|reopen|people|readiness/` → DecisionCycleViewSet
- `<uuid:cycle_id>/products/` (+ `<uuid:pk>/`) → DealProductViewSet
- `<uuid:cycle_id>/health-snapshots/`, `.../latest/`, `.../<uuid:pk>/` → DealHealthSnapshotViewSet (read-only)
- `<uuid:cycle_id>/notes/` (list/create), `.../<uuid:pk>/` (retrieve/destroy) → ManagerNoteViewSet
- `steps/`, `steps/<uuid:pk>/` CRUD, `steps/<uuid:pk>/status/` → DecisionStepViewSet

### product_catalog (`product-catalog/`)
- `` (list/create), `<uuid:pk>/` (CRUD) → ProductCatalogViewSet

### signals (`module-signals/`)
- `by-activity/<uuid>/counts/` → SignalCountsByActivityView; `choices/` → SignalChoicesView
- Per type — prefixes `pain/`, `objective/`, `impact/`, `tech-stack/`, `blockers/`, `next-steps/`, `people/`, `constraints/`: `<prefix>/` (list/create), `<prefix>/<uuid:pk>/` (retrieve/patch/put/destroy), `<prefix>/<uuid:pk>/validate/` | `/reject/` | `/reopen/` → respective `*SignalViewSet`
- `clusters/` → SignalClusterListView; `clusters/archive/` → SignalClusterArchiveView; `clusters/unarchive/` → SignalClusterUnarchiveView; `clusters/<path:canonical_key>/` → SignalClusterDetailView

### tech_catalog (`tech-catalog/`)
- `` (list/create), `<uuid:pk>/` (CRUD) → TechCatalogViewSet

### territories (`territories/`)
- `choices/`, `bulk-delete/`, `` , `<uuid:pk>/` CRUD, `<uuid:pk>/accounts-count/`, `<uuid:pk>/workspace/` → TerritoryViewSet / TerritoryBulkViewSet

### end_users (`client/`)
- Auth: `login/`, `logout/`, `refresh-token/`, `user/`
- `client-accounts/` + `<uuid:pk>/` CRUD, `<uuid:pk>/seats|stats|users-summary/` → ClientAccountViewSet
- `users/` + `<uuid:pk>/` CRUD, `<uuid:pk>/soft/`, `superusers/`, `grant-superuser/`, `<uuid:pk>/change-password/`, `bulk-create|bulk-update|bulk-delete/`, `<uuid:pk>/performance/`, `team-performance/`, `<uuid:pk>/managed-users-performance/`, `managers/` → UserViewSet / UserBulkViewSet
- `roles/` + `<uuid:pk>/` CRUD, `roles/permissions-matrix/` → UserRoleViewSet
- `organizations/` + `<uuid:pk>/` CRUD, `<int:pk>/hierarchy/` → OrganizationViewSet
- `teams/` + `<uuid:pk>/` CRUD, `<uuid:pk>/members/`, `summary/`, `<uuid:pk>/duplicate/` → TeamViewSet
- `sales-quotas/`, `sales-plans/`, `sales-milestones/` CRUD + performance/dashboard/activate actions; shortcuts `my-performance/`, `my-team-performance/`, `my-quotas/`, `my-plans/`, `my-milestones/`

---

## 6. Cross-module dependencies (`app_modules`)

`core_modules` is the pure base: imported by every module, imports no sibling. Direction below = importer → imported.

| Importer | Imports from | Representative files |
|---|---|---|
| campaigns | **activities** (heaviest edge) | `utils/scheduling.py:12`, `views/campaign_views.py:55,182`, `views/campaign_contact_views.py` (×5 blocks), `services/campaign_analytics_service.py:21`, `campaign_lifecycle_service.py`, `campaign_execution_service.py:25`, serializers |
| campaigns | sequences | `models/campaign.py:219`, `campaign_execution_service.py:28` (`SequenceDispatcher`) |
| campaigns | accounts, contacts, territories | creation service, account views, serializers |
| campaigns | decision_cycles | `views/campaign_account_views.py:794` |
| activities | **campaigns** (→ bidirectional pair) | `views/views.py:651,705,741` (`CampaignExecutionService`) |
| activities | decision_cycles, contacts, accounts | `services/activity_creation_service.py:22-24,90,309`, `serializers.py:12-14` |
| activities | signals | `serializers.py:989-990,1047` (`NextStepSignal`, `SignalManager`) |
| signals | activities | `models/next_step_signal.py:132`, `views/signal_counts_view.py:37`, `serializers/base_serializer.py:128` |
| signals | decision_cycles (constants only) | `services/signal_cluster_service.py:127` (`CycleOutcome`) |
| ai_pipelines | **signals** (heavy, one-directional) | `views/activity_extraction_view.py:91-106`, `services/transcript_signal_extractor.py`, `deal_health_evidence_builder.py`, `next_step_extractor.py`, prep_call assembler |
| ai_pipelines | activities, decision_cycles, tech_catalog, contacts | prep-call view/serializers, deal-health view/writer, `context.py:67` (TechCatalog) |
| decision_cycles | activities | `models.py:556-633`, `views/views.py` ×4, step services |
| decision_cycles | signals | `services/readiness_score_service.py:20,94`, `people_consolidation_service.py:24,75` |
| decision_cycles | contacts | models/serializers/services |
| accounts | territories, contacts, campaigns, decision_cycles, signals | `views/views.py:218,701,883,902`, `services/filter_service.py:82,442` — accounts is a hub |
| contacts | accounts | `views_bulk.py:28`, `serializers.py:16` |
| territories | accounts, contacts | `views/views.py:468,526` |
| sequences | activities (constants) | all sequence classes import `ActivityType` |
| tech_catalog / product_catalog | (none — leaf modules) | imported by ai_pipelines / decision_cycles respectively |

**Direction summary for the named pairs:**
- **signals ↔ ai_pipelines:** one-directional — `ai_pipelines → signals` only.
- **campaigns ↔ activities:** **bidirectional** (campaigns imports activities extensively; activities' views import `CampaignExecutionService` back).
- **decision_cycles ↔ signals:** bidirectional but asymmetric — decision_cycles reads signal models for scoring; signals imports only decision-cycle constants.
- **accounts:** hub — imports 5 modules, imported by 4.

**Django-signal (event) wiring across modules:**
- `campaigns/signals/signals.py:17` — `post_save` on `end_users.User` → auto-creates the user's TARGETED campaign.
- `decision_cycles/signals/readiness_recompute.py` — listens to `module_signals.{Pain,Objective,Impact,People,Blocker,Constraint}Signal` (`:115-190`), `DealProduct` (`:199`), and `module_activities.Activity` (`:213-234`) to recompute readiness. This is the main reactive cross-module coupling.
- Per-module cache-invalidation receivers (signals, activities) are in-module only.

---

## 7. Existing BI/analytics layer

**There is no standalone BI/analytics app, no cross-domain KPI service, and no dedicated dashboard-feeding layer.** Analytics is embedded per domain, computed server-side with ORM `annotate`/`aggregate`, and the frontend renders pre-aggregated payloads:

- **Campaigns — the one real analytics service:** `campaigns/services/campaign_analytics_service.py` — `get_dashboard()` (`:54`), `get_summary()` (`:85` — completion_rate, time_progress), `get_objectives_progress()` (`:176`), `get_activities_breakdown()` (`:214` — by_status/by_type/by_outcome via `Count`), accounts breakdown, timeline, executor performance, pipeline value via `Sum('decision_cycle__estimated_value')` (`:464-476`). Exposed at `GET /campaigns/{id}/dashboard/` (Redis-cached 30s, `campaign_views.py:704,716-735`) and `/summary/` (`:745`).
- **Signals:** `SignalCountsByActivityView` (`signals/views/signal_counts_view.py:58-88`) — per-activity pending/validated/rejected counts across 6 signal models via conditional `Count` aggregates.
- **Decision cycles:** readiness/deal-health scoring services (`readiness_score_service.py`, `completeness_score_service.py`, `step_aggregation_service.py`, `step_status_derivation_service.py`, `people_consolidation_service.py`) plus queryset annotations (`views/views.py:712-713,757-759`). `ai_pipelines/views/deal_health_view.py` + `deal_health_evidence_builder.py` produce the LLM deal-health snapshot but delegate scoring to decision_cycles services.
- **Territories:** single `accounts-count` action (`territories/views/views.py:383`).
- **end_users:** performance/quota/plan endpoints (`users/<pk>/performance/`, `team-performance/`, sales-quotas/plans/milestones dashboards) in the legacy-adjacent `end_users` app.

**Frontend:** per-page KPIs are predominantly consumed from these backend endpoints via SWR, not recomputed client-side — `api/campaigns/campaigns.js:123-124,439-495` (`useGetCampaignWorkspace` merges campaign detail + backend dashboard into `stats`), `api/signals/signalCounts.js:20-46`, `api/territories/territories.js:39`. Light client-side counting (`.filter().length` badges, selection counts) exists in list components, but there is no frontend analytics/dashboard aggregation module and no org-wide dashboard page. `config/features.js:38` has `DASHBOARD: false // Coming soon`.

---

## 8. Notifications infrastructure

**There is no notification system in this repository.** Verified absences (repo-wide search):
- No Notification model or notify service in the backend (zero matches for notification models/services).
- No Celery or any task queue (no `@shared_task`, no worker in `Procfile`); Redis (`django-redis`) is used only as a response/queryset cache.
- No WebSockets/Django Channels (no `channels` dependency; `salescommands/asgi.py` is stock). The campaign "channel" hits are the email/call delivery-channel field (`campaigns/models/campaign.py:70-75`), unrelated.
- No email sending (no `send_mail`/`EMAIL_BACKEND`/SMTP config).

**What exists instead (frontend-only, in-app):**
- Snackbar/toast stack: notistack + custom `Snackbar` (§3.2 error chain), CSV-import toast helpers (`utils/csvImportNotifications.js`).
- Polling/timers: one SWR `refreshInterval: 60000` on a single campaign resource (`api/campaigns/campaigns.js:571`); `setInterval` for JWT refresh (`hooks/useAuth.js:192,474`), monitoring flush (`utils/monitoring.js:271`), retry countdown (`hooks/useRetryCountdown.js:64`). Freshness otherwise relies on SWR revalidation.

---

## 9. Dead code & inconsistency watchlist (factual)

### 9.1 PainImpact remnants
- **Backend: the model is dropped and unserved.** Migration `signals/migrations/0014_drop_painimpact_add_impactsignal_and_scope.py` deletes all rows (`:80`) and the model (`:135`). No route, viewset, serializer, or model named PainImpact remains in non-migration backend code. Sole survivor: stale comment `permissions/registry/signals_registry.py:28` (“* PainImpactViewSet”, also `:7,:68,:93`).
- **Frontend: still fully wired.** `api/signals/painImpacts.js` exports `useGetPainImpactsByPain` (`:193`), `useGetPainImpactsByAccount` (`:225`), `createPainImpact` (`:267`), `updatePainImpact` (`:301`), `deletePainImpact` (`:335`) — all targeting `/module-signals/pain-impacts/`, which no longer exists server-side. Consumers:
  - `sections/accounts/signals/pain/AddPainImpactDialog.jsx` (imports create/update at `:64`; calls at `:330,:333`)
  - `sections/accounts/workspace/AccountSignalsTab.jsx` (`:53` imports AddPainImpactDialog, `:61` deletePainImpact, `:352` call, `:486` render)
  - `sections/accounts/signals/SignalClusterDetailDrawer.jsx` (`:69,:79,:1135,:1986`)
  - `api/signals/signalClusters.js:56,:172` (endpoint `painImpactList: "/module-signals/pain-impacts/"`)
- `PainCard.jsx` references PainImpact only in doc comments / callback props (`:17,:325,:326`). `SignalList.jsx` has no reference. No file named `WrapUpCaptureSection` exists anywhere in the repo.

### 9.2 “coming soon” / “future” / “stub” / “TODO” in UI code
Feature flags: `config/features.js:38,43,46,54` — `DASHBOARD / ACTION_CENTER / SALES_PLAN / PRODUCTS_MANAGEMENT: false // Coming soon`; `:129` `message: 'Coming soon'`.

| File | Line(s) | Content |
|---|---|---|
| `app/coming-soon-wip/page.jsx` | 30,62,115,123 | WIP page; TODO internal analytics |
| `views/maintenance/coming-soon.jsx` | 63 | "Coming Soon" |
| `sections/accounts/decision-cycles/Decision-steps/DecisionStepSignalsTab.jsx` | 17,20,47 | "(STUB)", "Phase 3 Stub" |
| `.../DecisionStepAIPrepTab.jsx` | 17,20,48 | "(STUB)", "Phase 3 Stub" |
| `app/(protected)/accounts/[id]/decisionSteps/[stepId]/page.jsx` | 17-18 | "stub - Phase 3" ×2 |
| `sections/accounts/contacts/ExpandingContactDetail.jsx` | 265,276 | Chip "Coming Soon" |
| `sections/admin/users/ExpandingUserDetail.jsx` | 41,55 | "under construction. Coming soon!" |
| `sections/admin/accounts/TerritoryFilterPanel.jsx` | 300,310,320 | Qualification/Tech-stack/Engagement filters coming soon (cf. TD-38 stubbed backend filters) |
| `sections/territories/FormTerritoryEdit.jsx` / `FormTerritoryAdd.jsx` | 533 / 456 | "More filters coming soon…" |
| `sections/territories/TerritoryCard.jsx` | 84 | `console.log('Contacts page coming soon')` |
| `sections/activities/workspace/ActivityOverviewTab.jsx` | 2273,2296,2395 | "COMING SOON BANNER", AI meeting prep |
| `views/accounts/workspace/index.jsx` / `views/territories/workspace/index.jsx` | 312 / 204 | Chip "Coming Soon" |
| `utils/locales/en.json` | 38,40,159,177 | "Coming Soon", "Contacts module coming soon" |
| `views/admin/teams/mockTeamsData.js` / `sections/admin/teams/TeamModal.jsx` | 4 / 88 | TEMPORARY MOCK DATA / TODO real API |

**Campaign-related** (closest to “Campaign Renewals”; no string literally says “Renewals”):
- `sections/campaigns/create/StepSelectType.jsx:116,136` — “Coming soon” badge on a campaign-type card.
- `sections/campaigns/workspace/CampaignOverviewTab.jsx:6,51,54` — “Dashboard coming soon”, KPIs “in a future release”.
- `sections/campaigns/workspace/CampaignCompletionModal.jsx:8,205,207` — TODO “Add to Follow-up Campaign” bulk-add; TODO “TARGETED singleton — implement when TARGETED campaign feature lands”; tooltip “Follow-up Campaign feature coming soon.”
- Backend has a `RenewalSequence` class (`app_modules/sequences/renewal_sequence.py`) with no UI surface.

### 9.3 Orphaned files
There are two parallel signal-capture trees: `sections/accounts/signals/…` and `sections/activities/signals/…`.
- **`sections/accounts/signals/wizard/WizardSignalAdd.jsx` — orphaned** (no importer anywhere). Consequently reachable-only-through-it files are also orphaned: `wizard/WizardNav.jsx`, `wizard/WizardSummary.jsx`, `wizard/sections/{PainSection,ObjectiveSection,TechStackSection}.jsx` (imported only at `WizardSignalAdd.jsx:59-63`).
- **Still live inside that same wizard folder:** `wizard/forms/{buildEditInitialValues.js, InlinePainForm.jsx, InlineObjectiveForm.jsx, InlineTechStackForm.jsx}` — imported directly by `accounts/signals/SignalEditDialog.jsx:43-46`.
- **`SignalEditDialog.jsx` — both copies imported (not orphaned):** the accounts copy via `SignalClusterDetailDrawer.jsx:71` → `AccountQualificationTab.jsx:59` → account workspace view; the activities copy heavily used (`AccountSignalsTab.jsx:52`, `dc-workspace/SignalsTab.jsx:31`, `ActivityNextStepsTab.jsx:38`, `ActivitySignalsTab.jsx:33`, tests). Note `AccountSignalsTab` imports the **activities** copy, not the accounts one.

### 9.4 Duplicated components (same purpose, different implementation)
- **Whole duplicated wizard subtree:** `accounts/signals/wizard/*` vs `activities/signals/wizard/*` (accounts copy partly orphaned; activities copy live and richer — has `InlineImpactForm.jsx`, `WizardCaptureStep.jsx`, `WizardValidationStep.jsx`).
- **Two `SignalEditDialog.jsx`** (accounts vs activities) — same purpose, different capability (accounts copy lacks the impact form).
- **Two `buildEditInitialValues.js`** (the accounts copy's header comment even points to the activities path).
- **Multiple signal list/table renderers:** `AccountSignalsTab.jsx`, `ActivitySignalsTab.jsx`, `dc-workspace/SignalsTab.jsx`, `accounts/signals/SignalList.jsx`, stub `DecisionStepSignalsTab.jsx`.
- **Three breadcrumbs:** `components/@extended/Breadcrumbs.jsx`, `components/WorkspaceBreadcrumb.jsx`, `sections/campaigns/workspace/CampaignBreadcrumbs.jsx`.
- **Two `EditableField.jsx`** (255 vs 251 lines): `sections/accounts/workspace/` and `sections/accounts/decision-cycles/`, plus overlapping `Editable*` families in both places.
- **Two `ActivityMiniCard.jsx`:** `components/cards/ActivityMiniCard.jsx` and `components/cards/activities/ActivityMiniCard.jsx`.
- **Tables:** shared `components/table/Table.jsx` (only `useReactTable` call) coexists with hand-rolled MUI tables (§3.2).
- **`UserCSVImportModal.jsx` and `UserCSVImportModalOLD.jsx`** both present in `sections/admin/users/`.
- No dedicated page-header component exists; page titles are ad hoc.

### 9.5 TechStack “clusterable” references
- Only literal occurrence of the word: `api/signals/signalClusters.js:14` (comment — “any clusterable signal type”). No `CLUSTERABLE`/`is_clusterable` constant exists anywhere.
- Authoritative backend set — `signals/services/signal_cluster_service.py:637-642`: `_SUPPORTED_CLUSTER_TYPES = {PAIN, OBJECTIVE, IMPACT, TECH_STACK}`. **TechStack is clusterable and fully supported**; its cluster identity is the catalog FK (`models/tech_stack_signal.py:7-30,136-137,373` — `canonical_key = "techstack:<tech_catalog_entry.id>"`).
- Frontend cluster UI covers techstack (`signalClusters.js:150,160,236,447`; `SignalClusterCard.jsx:149` comment “Three types are clustered today” — comment count is out of date vs the 4-type backend set).
- ConstraintSignal cluster status: see §10.k.

---

## 10. QA hotspots — targeted factual checks

### a. `GET /campaigns/<uuid>/playlist/` (QA: 8 s / 408)
- Route `campaigns/urls.py:84-86` → `CampaignViewSet.playlist` (`views/campaign_views.py:766-809`) → `CampaignExecutionService.get_playlist` (`campaign_execution_service.py:267-369`), serialized with `ActivityListSerializer(many=True)`.
- **No pagination**: the view builds `{'results': …, 'total_count': …}` manually (`:803-808`); the docstring mentions a `limit` param that is never read; `get_playlist`'s docstring states "No limit applied" (`:271`).
- Queryset (`:288-304`) is well-prefetched (`select_related` account/owner/campaign_contact/campaign_account/decision_step; `Prefetch('contacts', …select_related('standard_department'))`; `_contacts_count` annotation) — the serializer's method fields read prefetched data and are not N+1.
- The queryset is **evaluated twice**: `queryset.count()` (`:309`) then `list(queryset)` (`:310`), plus one aggregate for `min_pos_map` (`:314-328`).
- **Write-on-GET:** `get_playlist` first calls `_reschedule_overdue_chains(campaign, today)` (`:286`; body `:989-1055`) on every request — it loads all PLANNED non-callback activities, then per overdue campaign_contact issues an `update()` (`:1033-1036`), a `.first()` lookup (`:1047-1052`), and `_cascade_schedule_from` (`:1055` → SELECT + `bulk_update`, `:1072-1097`) — roughly 3 queries + writes per overdue contact, inside the GET.
- In-memory priority sort per today-bucket item (`:362`, `_calculate_priority` `:855-902`, no queries).

### b. Targets tab — `DeleteOutlined` ReferenceError
- `sections/campaigns/workspace/TargetsTab.jsx:588` — `startIcon={<DeleteOutlined />}` in the bulk-action bar "Remove" button (`:584-593`).
- Icon imports at the top of the file (`:22-25`) are only `PauseCircleOutlined, PlayCircleOutlined, StopOutlined, ReloadOutlined` — **no `DeleteOutlined` import**. The error surfaces when `selectedRows.size > 0 && !isFinal` renders the bulk bar.

### c. Campaign contact COMPLETED → COMPLETED rejection
- Statuses: `CampaignContactStatus` (`campaigns/constants.py:95-110`). Transition table `CAMPAIGN_CONTACT_TRANSITIONS` (`constants.py:113-135`) gives terminal states empty allow-lists: `COMPLETED: []` (`:133`), `STOPPED: []` (`:134`).
- Enforcement: `CampaignContact._transition_to` (`models/campaign_contact.py:108-115`) — `if new_status not in allowed: raise StandardizedValidationError(... "Cannot transition contact from '<s>' to '<s>'")`. `mark_completed()` (`:148-152`) on an already-COMPLETED contact therefore raises.

### d. TechStackSignal ↔ TechCatalog + disabled “which tool” select
- Model: `tech_catalog_entry = FK('tech_catalog.TechCatalog', PROTECT, null=True, blank=True)` (`models/tech_stack_signal.py:177-194`) — nullable to allow PENDING LLM signals without a catalog match (`clean()` rule at `:442-450`); drives `canonical_key = "techstack:<id>"` (`:372-373`).
- Serializers (`serializers/tech_stack_serializer.py`): read = compact object via `get_tech_catalog_entry` (`:83-98`); **create requires it** (`extra_kwargs :388`, `validate() :417-420`); **update excludes it** — not in writable fields (`:495-508`), documented as immutable because repointing changes cluster identity (`:452-457`).
- Frontend: `AsyncTechCatalogSelect` in `InlineTechStackForm.jsx:495-514` (“Tool *”, step S1). Disabled condition: `disabled={isEditMode}` (`:513`) with comment “In edit mode, the FK is immutable on the backend” (`:511-512`) and an explanatory caption (`:519-525`). So the select is disabled in edit mode by design, enabled on create. An identical copy exists in the accounts wizard tree (§9.3/9.4).

### e. DC ownership at creation; permissions on `/decision_cycles/<uuid>/notes/`
- Single DC-creation path: `DecisionCycleViewSet.create` (`decision_cycles/views/views.py:239-288`) → `DecisionCycleCreateSerializer.create` (`serializers.py:1230-1245`): `if 'owner' not in validated_data and user: validated_data['owner'] = user` — **the requesting user (e.g. the SDR) becomes owner**; the serializer only accepts `account_id, name, description, is_active` (`:1190`), so owner is never client-supplied. 5 pipeline steps auto-created (`views.py:290-318`). No separate “create from campaign activity” service; `source_campaign` is a separately backfilled FK.
- Notes (`ManagerNoteViewSet`, `views/manager_note_views.py:40`): **create** = manager/admin only (`:204-208`, tier from JWT `is_admin`/`is_manager`, `:125-143`); **list/retrieve** = manager/admin OR cycle owner (`:167-171,184-188`, `_is_cycle_owner` = `cycle.owner_id == user.id`); **destroy** = note author OR admin (`:245-251`). Parent-cycle lookup is tenant-scoped, not team-scoped (`_resolve_parent_cycle` `:76-90`; tracked as TD-27).

### f. Activity completion — owner vs “executant”
- **No “executant” concept exists on Activity** (grep returns nothing); the only responsible-user field is `owner` (`activities/models.py:176`). `Campaign` has an `executor` FK, but `SECONDARY_OWNER_FIELDS` adds `executor_id` to owner-scope only for the `campaigns` module (`permissions/owner_scope.py:162-172`), not activities.
- `ActivityViewSet.complete` (`views/views.py:562-683`) has **no owner-identity check** — guards are state-based only: reject CANCELLED (`:591-594`); for campaign activities the previous sequence step must be COMPLETED (`:596-610`); outcome validated (`:616-619`); already-COMPLETED → updates outcome/notes only (`:622-646`); campaign activities delegate to `CampaignExecutionService.process_result` (`:650-660`).
- Access control: `complete` is not in `action_policies` (`:98-128`), so it falls through to role-based registry permission (`permissions/mixins.py:116-171`); object reach depends on scope — under `mine` only `owner_id == user.id` rows are visible; under `client`/`team` (or when no `owner_scope` param is passed — `owner_scope.py:105-119` returns the unfiltered queryset) any same-tenant user with the update permission can complete. Factually: both owner and any in-scope permitted user can complete; there is no dual owner/executant gate.

### g. Signal `scope` field
- Field is `scope_level`, enum `ScopeLevel` = BUSINESS / DEPARTMENT / PERSONAL (`signals/constants.py:371`). Present on **three** models only: `ObjectiveSignal` (`objective_signal.py:123-128`, required, no default; `clean()` `:234-297` enforces PERSONAL→target_contact, DEPARTMENT→target_department, BUSINESS→neither), `PainSignal` (`pain_signal.py:152-156`, default BUSINESS), `ImpactSignal` (`impact_signal.py:173-176`, required, descriptive). Not present on People/Constraint/TechStack/Blocker/NextStep (TechStack has a distinct `usage_scope`, `tech_stack_signal.py:206`).
- Frontend edit: `SignalEditDialog.jsx` routes to inline forms (`:189-204`). `InlineObjectiveForm.jsx:75-91` hard-codes `SCOPE_OPTIONS` with all three values — **DEPARTMENT is selectable**; choosing it renders a Target Department `Select` fed by `useGetContactChoices().standardDepartments` (`:586-620`); PERSONAL renders `AsyncContactSelect`; a `useEffect` clears the non-applicable target (`:308-317`) and submit always emits both target fields, nulling the inapplicable one (`:275-283`). People and Constraint types have no inline edit form at all (no scope to edit; not routed in `SignalEditDialog`).

### h. Deal-health pipeline (sync/async, timeout, result delivery)
- `DealHealthPipeline` (`ai_pipelines/pipelines/deal_health.py:51`), single LLM call. **Fully synchronous** — `DealHealthRunView.post` (`views/deal_health_view.py:68-132`) calls `pipeline.run()` inline in the request thread inside `transaction.atomic()` (`deal_health.py:92`). No Celery/threads/background tasks.
- Timeout: `PROVIDER_CONFIG[...]['timeout_s'] = 30` for both providers (`config.py:64-75`), applied in `BasePipeline._call_llm` (`base.py:305-306`); `LLMTimeoutError` → run status TIMEOUT (`deal_health.py:128-134`). One automatic retry on parse failure only (`base.py:337-358`).
- Frontend: **direct response, no polling** — `runDealHealth` (`api/aiPipelines/dealHealth.js:52-85`) POSTs with `{profile: "bulk"}` (~18 s client timeout per comment `:43`) and receives the snapshot in the 201 body; `useGetDealHealthSnapshot` (`:100-123`) separately GETs `/decision_cycles/{id}/health-snapshots/latest/` and is revalidated in a `finally` block (`:70-72`) so a server-side snapshot created after a client timeout is picked up on next mount.

### i. “Next Step” tab in Activity
- Component `sections/activities/workspace/ActivityNextStepsTab.jsx`. Two data sources: (1) AI suggestion cards = `NextStepSignal` rows via `useActivityAllSignals` → `useGetSignalsByActivity(activityId, "next-steps")` filtering `source_activity=activityId` (`api/signals/signals.js:308-309,433-441`); (2) “Upcoming Activities” = `activity.sequence_context.next_activities`, a serializer-computed field (`UpcomingActivitiesSection.jsx:36`), no separate fetch.
- `sequence_context` is computed by `ActivitySequenceService.get_sequence_context` (`activity_sequence_service.py:83`; serializer cache `serializers.py:756-772`). Scope: `decision_cycle` wins; else `campaign` scope filters by `campaign_contact_id` and returns `Activity.objects.none()` when `campaign_contact_id` is null (`:304-307`). `next_activities` includes only PLANNED/IN_PROGRESS activities ranked after the current one (`:149-152`).
- Linkage of follow-ups: `Activity.next_step_signal` FK (`models.py:354-367`), `source_activity` self-FK (`:282-293`). The convert flow (`ActivityModal.jsx:281-312`; `ActivityNextStepsTab.jsx:267-271,393-397`) sends `source_activity_id` + `next_step_signal_id` but **not** `campaign_contact_id`/`campaign_id`, and passes `decisionCycleId=null`. Such an activity belongs to neither the decision-cycle sequence nor the campaign_contact sequence, so the sequence service never returns it — it is linked only through `source_activity`/`derived_activities`, which this tab does not query. This is the observable mechanism behind “created activity doesn't appear.”

### j. Prep call implementation
- Prompt built in `ai_pipelines/prompts/prep_call/` (`system.py`, `context.py:build_context_layer`, `brief_v1.py:build_brief_request`), assembled by `PrepCallPipeline.run` (`pipelines/prep_call.py:124-131`).
- Inputs — `PrepInputPackAssembler.build` (`services/prep_call/input_pack_assembler.py:31-65`), scoped to an Activity: account name; the upcoming activity; optional `target_contact` (with role from validated PeopleSignal); and the activity's **DecisionCycle** — current step/goal/criteria, deal value, validated signals of all types, maturity snapshot from the latest DealHealthSnapshot, levers, competitive context. **No campaign fields are included** — campaign context is not an input.
- Output stored in **`PrepCallSnapshot`** (`models/prep_call.py:22`, table `prep_call_snapshots`): LLM JSON in the `brief` JSONField (`:68`), plus `activity`/`pipeline_run`/`target_contact` FKs, `brief_mode`, `input_hash` (SHA-256 dedup), `snapshot_date`. Persisted in `_persist_snapshot` (`prep_call.py:281-307`); structural validation `_validate_brief` (`:313-377`). Synchronous like deal-health; DB-hash idempotence, no Redis layer-1 (view comment `prep_call_view.py:76-78`; TD-50).
- Frontend: `api/aiPipelines/prepCall.js` — POST `/module-ai-pipelines/prep-call/run/` (`{activity_id, contact_id?}`, snapshot in response), GET `/prep-call/by-activity/<uuid>/`. UI: `PrepCallBrief.jsx`, `ActivityPreparationTab.jsx`, `PrepCallEmptyState.jsx`. Single-contact only (TD-46).

### k. ConstraintSignal — flat or clusterable?
- **Mixed state.** The model behaves like a cluster member: `canonical_key = "constraint:<what>:<dimension>"` computed in `save()` (`constraint_signal.py:156-161`), docstring claims it “participates in the cluster model” (`:10-18`), composite `(account, canonical_key)` index (`:146-149`), and cache invalidation busts `SIGNAL_CLUSTERS_CACHE_TAG` (`cache_invalidation.py:348-362`).
- But the cluster service **excludes it**: `SignalClusterType` (`constants.py:451-473`) lists only PAIN/OBJECTIVE/TECH_STACK/IMPACT, and `_SUPPORTED_CLUSTER_TYPES` (`signal_cluster_service.py:637-642`) matches; `_assert_signal_types_supported` (`:644-684`) raises `CLUSTER_SIGNAL_TYPE_INVALID` for `constraint`. Serializers are the flat Base family (no cluster fields). Net: ConstraintSignal computes cluster identity but no cluster is ever listed/aggregated for it, and no frontend cluster UI references it.

### l. People signals
- **Model exists:** `PeopleSignal(BaseSignal)` (`people_signal.py:40`, table `module_signals_people`) — `role` (required), `influence`, `target_contact` FK, `target_department` FK, `notes`; requires ≥1 target (`clean()` `:162-180`); explicitly non-clustering (`canonical_key` forced None, `:154-156`).
- **Endpoints exist:** `/module-signals/people/` list/create + detail + validate/reject/reopen (`urls.py:27,275-300`), full serializer family.
- **Backend consumers:** readiness scoring (`readiness_score_service.py:118-124`), people consolidation, deal-health evidence builder, prep-call input pack; readiness recompute listens on its save/delete. Note stale comment `accounts/services/filter_service.py:465`: “PeopleSignal will be removed in Sprint 2.”
- **Frontend surface — partial:** API fully wired (`'people'` in `SIGNAL_TYPES`, `signals.js:37,90-94`); `SignalTypeChip.jsx:27` has a `people` entry; DC people consolidation reads `/decision_cycles/{id}/people/` (`api/accounts/decisionCycles.js:221,1055`). **No inline create/edit form** — `SignalEditDialog.jsx` routes only pain/objective/impact/tech-stack/blockers/next-steps (`:189-204`); no standalone People-signals page or menu entry (cf. TD-30: quick drawer renders an empty body for people/constraints).

---

## 11. Open questions (need product / tech-lead input)

1. **Legacy `backend/apps/` tree:** it is still in `INSTALLED_APPS` and URL-mounted under “Path to validate”. Which legacy endpoints are still consumed (by the frontend or externally), and what is the decommission plan? (`apps.accounts` is marked `#OBSOLETE` yet mounted.)
2. **PainImpact frontend surface:** `api/signals/painImpacts.js`, `AddPainImpactDialog.jsx` and their call sites still target `/module-signals/pain-impacts/`, dropped in migration 0014. Is the Pain-Impact UX meant to be removed, or remapped onto `ImpactSignal`? (Product decision — the audit only establishes the mismatch.)
3. **Duplicated accounts vs activities signal trees:** which copy is canonical going forward (accounts `WizardSignalAdd` subtree is orphaned; `AccountSignalsTab` already imports the activities `SignalEditDialog`)? Consolidation ownership is unclear.
4. **Activity completion authorization:** current behavior allows any in-scope permitted user (not just the owner) to complete an activity, and no executant concept exists on Activity. Is this the intended permission model for campaign execution (owner vs executor of the campaign)?
5. **ConstraintSignal clustering intent:** model docstring says clusterable, cluster service rejects it. Which is the target state?
6. **`/campaigns/<uuid>/playlist/` contract:** is the write-on-GET rescheduling (`_reschedule_overdue_chains`) intended to stay in the read path, and is the “no limit / no pagination” contract a product requirement (“reps must see all their activities”) at expected data volumes?
7. **Manager-notes scoping:** notes are tenant-wide for managers/admins (TD-27) and the front thread UI is flagged off-product-intent (TD-29). Target scope (team vs tenant) and target UX are open.
8. **BI/dashboard roadmap:** `DASHBOARD`, `ACTION_CENTER`, `SALES_PLAN`, `PRODUCTS_MANAGEMENT` feature flags are off with “Coming soon”; only campaigns has a real analytics service. Is a cross-domain BI layer planned, and where should per-page KPIs live?
9. **Notifications:** nothing exists (no model, queue, websocket, email). If alerting is on the roadmap, greenfield choices (polling vs websocket vs email) are entirely open.
10. **`frontend-Model/`:** TD-44 schedules deletion “once the library is no longer consulted” — is it still consulted?
11. **PeopleSignal lifecycle:** model is live and consumed by readiness/prep-call, but `filter_service.py:465` says “will be removed in Sprint 2”, and no dedicated UI form exists. Keep, expand UI, or remove?
12. **Mount-name inconsistency:** URL mounts mix kebab-case (`company-accounts/`, `tech-catalog/`) and snake_case (`decision_cycles/`). Intentional or to be harmonized? (Any change is breaking for the frontend.)

---

*End of audit. Sources: repository code at commit `039e86e`; corroborating internal docs `TECH_DEBT.md` (TD-1…TD-51) and `AUDIT_DC_POST_LIVRAISON.md` (2026-06-16). All file:line references are from this baseline.*
