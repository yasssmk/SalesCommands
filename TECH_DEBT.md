# Technical Debt Journal

Suivi des dettes techniques connues, leur statut, et le sprint qui les résoudra.

## Convention

| Statut      | Sens                                |
| ----------- | ----------------------------------- |
| OPEN        | Identifiée, pas encore planifiée    |
| PLANNED     | Sprint identifié pour la résolution |
| IN PROGRESS | Sprint en cours                     |
| RESOLVED    | Mergée                              |

## Liste

| ID   | Titre                                                                   | Découverte   | Statut   | Sprint résolution              | Notes                                                                             |
| ---- | ----------------------------------------------------------------------- | ------------ | -------- | ------------------------------ | --------------------------------------------------------------------------------- |
| TD-1 | Absence de tests systémiques                                            | Sprint B1    | RESOLVED | Sprint B1 (pytest infra livré) | Convention pytest désormais obligatoire à chaque sprint                           |
| TD-2 | Drift `source_activity` nullability sur Pain/Objective/Impact/TechStack | Audit B1     | RESOLVED | PR #7                          | Migration 0016 revert step F (source_activity nullable préservé)                  |
| TD-3 | Collision migrations `standard_departments` (core_apps ↔ core_modules)  | Pytest B1    | RESOLVED | PR #7                          | Option A — SeparateDatabaseAndState sur core_apps.0002 + core_modules.0001        |
| TD-4 | Drift `campaign.stakeholders`                                           | Sprint chore | RESOLVED | PR #9                          | AlterField campaign.stakeholders — through_fields + AUTH_USER_MODEL swappable ref |
| TD-5 | Contrat sémantique `NextStepSignal.source_quote` = justification        | Sprint B2    | RESOLVED | PR #14 (Sprint B4)             | Résolu : le prompt B4 v1 (`prompts/next_steps/next_steps_v1.py`) impose explicitement le contrat dans les EMISSION RULES + exemple concret DSI/AE. `source_quote` = justification extraite du transcript, pas un passage aléatoire. |
| TD-6 | `BlockerSignal.contact` attribution déférée à la validation             | Sprint B3    | OPEN     | Sprint F5 (Signals Tab vue Grouped) | Le pipeline B3 n'extrait pas l'attribution `contact` (FK Contact, nullable) depuis le transcript — fuzzy mapping LLM "le DSI" → Contact UUID trop fragile. Le wizard de validation du Sprint F5 doit exposer un sélecteur de contact (AsyncContactSelect filtré par `account_id`) sur les BlockerSignal PENDING avant promotion en VALIDATED. Mirror du pattern Impact v1 (metric_text / human_impact deferred). |
| TD-7 | `NextStepSignal.suggested_contacts` attribution déférée à la validation | Sprint B4    | OPEN     | Sprint F6 (Next Steps Tab UI) | Le pipeline B4 n'extrait pas l'attribution `suggested_contacts` (M2M Contact) depuis le transcript — fuzzy mapping LLM "Jane" / "the CTO" → Contact UUID trop fragile. Le wizard de validation du Sprint F6 (Next Steps Tab) doit exposer un sélecteur multi-contacts pour les NextStepSignal PENDING avant matérialisation en Activity. Mirror du pattern TD-6 (Blocker contact) et Impact v1 (metric_text / human_impact deferred). |
| TD-8 | View-layer AI pipeline dedup filter ne discrimine pas par `pipeline_type` | Sprint B4    | RESOLVED | Sprint B5 (endpoint unifié `/activity-extraction/run/`) | Résolu : `ActivityExtractionView._find_existing_run` filtre par `(client_id, source_activity, input_hash, pipeline_type, status__in=DEDUP_STATUSES)`. Chaque sous-pipeline est dédupliqué indépendamment. L'ancien endpoint `/transcript-signals/extract/` conserve son filtre sans `pipeline_type` (acceptable car il ne lance que Qualification). |
| TD-9 | Prompt LLM quality evaluation v1 → v2 | Sprint B4 | OPEN | Sprint dédié post-F7 | Calibration empirique des 6 prompts LLM (Pain / Objective / Impact / TechStack / Blocker / NextStep) sur une batterie de 8-15 transcripts réels couvrant étapes/profils/densités/edge cases différents. Itération v2 sur la base des erreurs observées. À planifier ENTRE le sprint F7 (fin frontend post-call) et le démarrage des sprints Copilote (Decision Cycle Workspace / Prep Call). |
| TD-10 | Old `/transcript-signals/extract/` endpoint deprecated in B5 | Sprint B5 | OPEN | Chore sprint post-migration frontend | L'ancien endpoint reste fonctionnel mais retourne les headers `Deprecation: true` + `Sunset: 2026-12-01` + `Link: </module-ai-pipelines/activity-extraction/run/>; rel="successor-version"`. À supprimer dans un sprint chore dédié APRÈS que le frontend ait entièrement migré vers `/activity-extraction/run/`. |
| TD-11 | Cache replay leakage: signals returned are ALL matching `source_activity`, not only those from the specific run | Sprint B5 | OPEN | Sprint F (signals tab refactor) | `ActivityExtractionView._serialize_cached_qualif_signals` and `_serialize_cached_nextstep_signals` query by `source_activity` without filtering by `source_run`. Signals created manually or by prior runs on different transcripts will leak into the cached response. Fix requires adding a `source_run` FK on each signal model to allow precise scoping. Acceptable for MVP. |
| TD-12 | N+1 on cached qualification signals serialization | Sprint B5 | OPEN | Chore perf sprint | `_serialize_cached_qualif_signals` issues 5 separate DB queries (one per signal type) without `prefetch_related`. Should be consolidated or prefetched for production scale. |
| TD-13 | Pre-existing migration drift: `CharField` without `max_length` → `varchar(None)` | Audit B5 | OPEN | Chore migration cleanup | `apps/accounts/migrations/0001_initial.py` contains `CharField` fields without `max_length`, producing `varchar(None)` columns. Works on PostgreSQL but breaks SQLite test runs. Needs a data-safe migration to add explicit `max_length` constraints. |
