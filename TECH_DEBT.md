# Technical Debt Journal

Suivi des dettes techniques connues, leur statut, et le sprint qui les résoudra.

## Convention

| Statut | Sens |
|---|---|
| OPEN | Identifiée, pas encore planifiée |
| PLANNED | Sprint identifié pour la résolution |
| IN PROGRESS | Sprint en cours |
| RESOLVED | Mergée |

## Liste

| ID | Titre | Découverte | Statut | Sprint résolution | Notes |
|---|---|---|---|---|---|
| TD-1 | Absence de tests systémiques | Sprint B1 | RESOLVED | Sprint B1 (pytest infra livré) | Convention pytest désormais obligatoire à chaque sprint |
| TD-2 | Drift `source_activity` nullability sur Pain/Objective/Impact/TechStack | Audit B1 | IN PROGRESS | chore/fix-pre-existing-migration-drifts | Option A : revert step F via migration 0016 |
| TD-3 | Collision migrations `standard_departments` (core_apps ↔ core_modules) | Pytest B1 | IN PROGRESS | chore/fix-pre-existing-migration-drifts | Option A : SeparateDatabaseAndState sur 2 migrations publiées |
| TD-4 | Drift `campaign.stakeholders` | Sprint chore | OPEN | À déterminer (audit en cours) | Sera intégrée au sprint chore courant si simple, sinon sortie en sprint dédié |
