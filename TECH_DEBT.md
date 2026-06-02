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
