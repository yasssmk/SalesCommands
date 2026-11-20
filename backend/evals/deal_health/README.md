# evals/deal_health — évaluation format × modèle du deal health (Sprint « Deal health v2 », étape 7)

Script de mesure, **pas du code produit** : rien dans `app_modules/` ne l'importe.
Il ne laisse **rien** en base : tout ce qu'il crée (tenant, utilisateurs,
compte, contacts, cycle de décision et ses étapes, activités, signaux,
stakeholders, notes manager, produits, runs, snapshots) est annulé. Chaque
appel tourne dans son propre savepoint, et le run entier tient dans une
transaction qui n'est jamais commitée (le pattern `evals/next_steps`).

Plomberie commune avec `evals/next_steps` et `evals/td279` :
`evals/common/eval_kit.py` (RecordingProvider, boucle des N appels,
`--n` / `--only` / `--out` / `--rescore` / `--dry-run`, `summary.csv` / `.md`).

## Ce qui est mesuré

Le **vrai** `DealHealthPipeline` (constructeur d'évidence, prompts v2.1,
schéma strict, writer), sur **5 cas fictifs** dont la vérité est écrite à
l'avance, dans une **matrice** :

| | Modèle X — `openai_deal_health` (gpt-5.6-terra) | Modèle Y — `openai_deal_health_challenger` (gpt-5.4) |
|---|---|---|
| **Format A** — sections + JSON compact (`sections`) | A · X | A · Y |
| **Format B** — JSON intégral (`json`) | B · X | B · Y |

- Le modèle Y est **déclaré pour l'éval seulement** dans `ai_pipelines/config.py` (jamais branché). Si `gpt-5.4` ne répond pas sur votre compte, remplacez-le par un autre modèle OpenAI de niveau qualité dans cette entrée.
- **Claude** : dès que `ANTHROPIC_API_KEY` est dans `backend/salescommands/.env`, ajoutez simplement `claude_deal_health` à `--models` (aucun code). Sans clé, l'outil le refuse avant tout appel.
- Le format d'une cellule est imposé pour son appel seulement (`context_v2.DEAL_HEALTH_INPUT_FORMAT`), et le modèle par l'entrée `PROVIDER_CONFIG` de la cellule.

## Commandes (depuis `backend/`, venv activé, `OPENAI_API_KEY` dans `backend/salescommands/.env`)

```bash
# La matrice complète : 5 cas x 2 formats x 2 modèles = 20 appels
python evals/deal_health/run_deal_health_eval.py

# Plusieurs appels par cellule (les modèles ne sont pas déterministes)
python evals/deal_health/run_deal_health_eval.py --n 3

# Un cas
python evals/deal_health/run_deal_health_eval.py --only technical_fit_fr

# Ajouter Claude (ANTHROPIC_API_KEY requise)
python evals/deal_health/run_deal_health_eval.py --models openai_deal_health openai_deal_health_challenger claude_deal_health

# Un seul format
python evals/deal_health/run_deal_health_eval.py --formats sections

# Recalculer les scores et le rapport depuis les réponses enregistrées : AUCUN appel
python evals/deal_health/run_deal_health_eval.py --rescore evals/deal_health/out/<stamp>

# Vérifier la chaîne complète, sans appel API (réponses fixes)
python evals/deal_health/run_deal_health_eval.py --dry-run
```

**Coût et durée estimés de la matrice par défaut** (20 appels séquentiels ;
les vrais chiffres sont dans le rapport : tokens et durée par appel) :
- le prompt fait environ 9 à 13 k caractères (mesuré en dry run), soit environ 3 à 4 k tokens en entrée ; la réponse (le schéma complet) et le raisonnement (effort `medium`), environ 5 à 10 k tokens en sortie ;
- soit de l'ordre de **0,05 à 0,15 $ par appel**, donc **environ 1 à 3 $ pour les 20 appels** (tarifs publics à vérifier) ;
- comptez **15 à 40 minutes** (un modèle de raisonnement met 30 à 120 s par appel) ; le pire cas est d'environ 50 minutes (délai de 150 s atteint à chaque appel).

## Les cas (fictifs — `tests/fixtures/deal_health_eval/<cas>/`)

Chaque cas a son `seed.json` (le DC tel qu'il est créé) et son `expected.json` (la vérité). Les noms de famille sont **plantés** dans le seed : le LLM ne doit jamais les recevoir (prénoms seulement).

| Cas | Étape déclarée | Étape réelle | Info manquante (niveau) | Objection cachée | Décideur |
|---|---|---|---|---|---|
| `qualification_sparse` | QUALIFICATION | QUALIFICATION | budget (BUSINESS) | un outil précédent rejeté par les chauffeurs | Sofia |
| `technical_fit_fr` (preuves en français) | TECHNICAL_FIT | TECHNICAL_FIT | sécurité / hébergement (BUSINESS) | l'équipe IT déjà débordée | Mathilde |
| `solution_validation_contradictory` | SOLUTION_VALIDATION | SOLUTION_VALIDATION | gains chiffrés (DEPARTMENT) | un concurrent moins cher | Nadia |
| `business_case_wrong_step` | BUSINESS_CASE | **TECHNICAL_FIT** | revue sécurité / intégration (BUSINESS) | la sécurité IT bloquera sans revue | Arthur |
| `closing_budget_fail` | CLOSING | **BUSINESS_CASE** | budget gelé (BUSINESS) ; BANT budget = `not_validated` | dépenses gelées par la DAF | Helena |

L'étape déclarée est dérivée des activités du seed, comme en production ; le script vérifie qu'elle est la bonne avant tout appel.

## Contrôles automatiques (`scoring.py`)

| Contrôle | Règle |
|---|---|
| schéma valide | la réponse contre `DEAL_HEALTH_RESPONSE_SCHEMA` (mots-clés : type, properties, required, additionalProperties false, items, enum) |
| prénoms seulement | aucun nom de famille planté, **ni dans le prompt ni dans la sortie** |
| aucun nombre inventé | chaque nombre de la sortie existe dans l'entrée (séparateurs ignorés : 48 000 = 48,000 = 48000). Un chiffre collé à des lettres (P1, v2, Q3) est un libellé, pas une quantité |
| aucun nom inventé | heuristique : un mot à majuscule hors début de phrase (ou à majuscule interne, ou en capitales de 3 lettres et plus), absent de l'entrée et hors du vocabulaire autorisé (étapes, sigles métier, mois…). Les champs de code (`status`, `theme`, `rigidity`…) ne sont pas lus. Les mots trouvés sont listés dans le rapport, pour relecture |
| info manquante (niveau) | une entrée de `missing_info` contient un mot-clé de l'info plantée, **au bon niveau** |
| étape réelle | `estimated_step.step` = l'étape réelle attendue |
| aucune fuite de garde-fou | aucune phrase de `constants.DEAL_HEALTH_GUARDRAIL_LEAK_PHRASES` (« do not invent », « unsupported capabilities »…) dans le texte |
| aucun ethos / pathos / logos | `constants.DEAL_HEALTH_RHETORIC_LABELS`, mots entiers |
| top_arguments sans tâche | heuristique : un champ d'argument (need, value, benefit, advantage, feature) qui commence par un verbe d'action de la liste `REP_TASK_VERBS` (build, send, schedule, prepare…) à l'impératif ou en -ing est une tâche du commercial, pas un argument |
| informatifs | objection cachée vue, décideur nommé, BANT attendu (cas 5) |
| durée et tokens | par appel, depuis l'audit du run (`sub_calls`) |

Ces contrôles sont prouvés sur des sorties enregistrées, correctes et fautives, par `tests/ai_pipelines/test_deal_health_eval_checks.py`.

## Sorties (`evals/deal_health/out/<stamp>/`, ignoré par git ; un dossier non vide est refusé)

- **`report.md`** : le rapport côte à côte. Il contient :
  - le récapitulatif par cellule (contrôles réussis, durées, tokens, erreurs) ;
  - les plafonds (50 000 / 200 000 caractères) et le délai (150 s), avec l'indication s'ils ont été atteints ;
  - pour chaque cas, le tableau des contrôles des 4 cellules, puis les 4 sorties résumées : résumé, plan d'action, arguments, info manquante, étape, constats.
- `<cas>__<format>__<entrée>/call_NN.json` : le prompt envoyé, **la réponse brute**, le JSON lu, la méta (durée, tokens, troncature), les métriques.
- `summary.csv` / `summary.md` : une ligne par appel (`eval_kit`).
- `--rescore` écrit `summary_rescored.*` et `report_rescored.md` à côté des originaux.

## Dry run

`--dry-run` n'appelle aucune API : chaque appel reçoit une réponse fixe construite à partir de la vérité du cas. La cellule `qualification_sparse` · format B est **volontairement fautive** (un chiffre inventé, une tâche dans `top_arguments`), pour montrer deux contrôles rouges dans le rapport. Le dry run prouve que la chaîne tourne ; il ne dit rien des modèles. Il est joué par `tests/ai_pipelines/test_deal_health_eval_dry_run.py`.

⚠️ Les modèles ne sont pas déterministes. Pour trancher entre deux cellules, comparez des taux sur plusieurs appels (`--n 3` ou plus), jamais une réponse isolée.
