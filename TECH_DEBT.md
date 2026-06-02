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
| TD-5 | Contrat sémantique `NextStepSignal.source_quote` = justification        | Sprint B2    | OPEN     | Sprint B4 (pipeline next-steps LLM) | Le prompt B4 doit explicitement instruire le LLM que `source_quote` est la justification de la suggestion, pas un passage aléatoire. Documenté dans le docstring du modèle. |
| TD-6 | `BlockerSignal.contact` attribution déférée à la validation             | Sprint B3    | OPEN     | Sprint F5 (Signals Tab vue Grouped) | Le pipeline B3 n'extrait pas l'attribution `contact` (FK Contact, nullable) depuis le transcript — fuzzy mapping LLM "le DSI" → Contact UUID trop fragile. Le wizard de validation du Sprint F5 doit exposer un sélecteur de contact (AsyncContactSelect filtré par `account_id`) sur les BlockerSignal PENDING avant promotion en VALIDATED. Mirror du pattern Impact v1 (metric_text / human_impact deferred). |
| TD-7 | `NextStepSignal.suggested_contacts` attribution déférée à la validation | Sprint B4    | OPEN     | Sprint F6 (Next Steps Tab UI) | Le pipeline B4 n'extrait pas l'attribution `suggested_contacts` (M2M Contact) depuis le transcript — fuzzy mapping LLM "Jane" / "the CTO" → Contact UUID trop fragile. Le wizard de validation du Sprint F6 (Next Steps Tab) doit exposer un sélecteur multi-contacts pour les NextStepSignal PENDING avant matérialisation en Activity. Mirror du pattern TD-6 (Blocker contact) et Impact v1 (metric_text / human_impact deferred). |
| TD-8 | View-layer AI pipeline dedup filter ne discrimine pas par `pipeline_type` | Sprint B4    | OPEN     | Sprint B5 (endpoint unifié `/activity-extraction/run/`) | `TranscriptSignalsExtractView._check_db_dedup` filtre les `AIPipelineRun` par `(client_id, source_activity, input_hash, status__in=DEDUP_STATUSES)` SANS inclure `pipeline_type`. Conséquence : si la même URL exposait Qualification ET NextSteps (B4 introduit le 2nd pipeline avec même `input_hash` mais `pipeline_type` distinct), le second pipeline retournerait à tort `409 ALREADY_EXTRACTED`. Non bloquant en B4 (NextStepsPipeline n'expose pas d'endpoint — invoqué en interne uniquement). Doit être résolu dans le design de l'endpoint unifié `/activity-extraction/run/` au Sprint B5 : la dédup doit soit filtrer par `pipeline_type`, soit unifier la notion de "extraction completed" au niveau de l'orchestration. |
