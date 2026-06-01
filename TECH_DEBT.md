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
