# evals/game_plan — évaluation des modèles du Game Plan (Sprint 2 Game Plan, G13)

Script de mesure, **pas du code produit** : rien dans `app_modules/` ne l'importe.

**Il ne laisse rien en base** (exactement la sûreté de `evals/deal_health`) :
- tout ce qu'il crée est annulé : tenant, utilisateur, compte, contacts, cycle de décision et ses étapes, campagne et sa séquence, activités, signaux, stakeholders, snapshot deal health, fiche vendeuse, produits, runs, Game Plans ;
- chaque appel tourne dans son propre savepoint ;
- le run entier tient dans **une transaction jamais commitée**.

Prouvé en dry run sur la base locale : 0 ligne avant, 0 après dans les tenants, activités, runs, Game Plans, snapshots deal health et fiches vendeuses.

Plomberie commune : `evals/common/eval_kit.py`.
- `RecordingProvider` ;
- la boucle des N appels ;
- les options `--n` / `--only` / `--out` / `--rescore` / `--dry-run` ;
- les fichiers `summary.csv` / `.md`.

Les contrôles génériques sont **importés** de `evals/deal_health/scoring.py`, et non recopiés (G13b : ses défauts de dates mal découpées, de noms composés et de jours de la semaine y ont été corrigés, ce qui profite aussi à l'eval du deal health) :
- schéma valide (étendu à `anyOf`, pour le `campaign_diagnostic` nullable) ;
- chiffres inventés ;
- noms inventés ;
- noms de famille ;
- termes rhétoriques.

## Ce qui est mesuré

Chaque appel fait ce que fait `POST prep-call/run/`. Il passe par :
- le **vrai** `PrepInputPackAssembler` (pack v2) ;
- le **vrai** `PrepCallPipeline` : prompts v2, schéma strict de la sortie (plan pour une conversation, message pour un email ou un LinkedIn), validation serveur (refs, termes rhétoriques, noms de famille).

Il tourne sur **6 cas fictifs** dont la vérité est écrite à l'avance. La matrice porte **sur les modèles seulement**, au format du pack v2 tel qu'il est (pas d'axe format) :

| Modèle | Entrée `PROVIDER_CONFIG` | Rôle |
|---|---|---|
| **X** — gpt-5.6-terra (le modèle du deal health, effort `medium`, 150 s) | `openai_prep_call` | l'entrée de **production** du Game Plan (décision PO après la première matrice, G13b) |
| **Y** — gpt-4o-mini (30 s, 4 096 tokens) | `openai_prep_call_challenger` | le challenger, **déclaré pour l'éval seulement**, jamais branché |

Le premier run (G13, 36 appels) a été fait avec les anciennes clés : `openai_prep_call_terra` (gpt-5.6-terra) et `openai_prep_call` (gpt-4o-mini, l'entrée de production d'alors). Le rapport affiche le modèle **enregistré** dans chaque appel : un `--rescore` de ce run reste juste.

- **Claude** : dès que `ANTHROPIC_API_KEY` est dans `backend/salescommands/.env`, ajoutez `claude_prep_call` à `--models` (aucun code). Sans clé, l'outil le refuse avant tout appel.
- Le modèle d'une cellule vient de son entrée `PROVIDER_CONFIG` : modèle, effort, `max_tokens`, délai.

## Commandes (depuis `backend/`, venv activé, `OPENAI_API_KEY` dans `backend/salescommands/.env`)

```bash
# La matrice par défaut : 6 cas x 2 modèles = 12 appels
python evals/game_plan/run_game_plan_eval.py
```

```bash
# Plusieurs appels par cellule (les modèles ne sont pas déterministes) : 36 appels
python evals/game_plan/run_game_plan_eval.py --n 3
```

```bash
# Le coût estimé d'un modèle dont le tarif n'est pas dans le script (USD par million de tokens, entrée,sortie)
python evals/game_plan/run_game_plan_eval.py --price gpt-5.6-terra=IN,OUT
```

```bash
# Un cas, ou un modèle
python evals/game_plan/run_game_plan_eval.py --only trap_no_figures
```

```bash
python evals/game_plan/run_game_plan_eval.py --models openai_prep_call_challenger
```

```bash
# Ajouter Claude (ANTHROPIC_API_KEY requise)
python evals/game_plan/run_game_plan_eval.py --models openai_prep_call openai_prep_call_challenger claude_prep_call
```

```bash
# Recalculer scores et rapport depuis les réponses enregistrées : AUCUN appel
python evals/game_plan/run_game_plan_eval.py --rescore evals/game_plan/out/<stamp>
```

```bash
# Vérifier la chaîne complète, sans appel API (réponses fixes)
python evals/game_plan/run_game_plan_eval.py --dry-run
```

### Coût et durée estimés de la matrice par défaut

Ce sont 12 appels séquentiels. Les vrais chiffres sont dans le rapport : durée, tokens et coût par appel.

**Taille du prompt** (mesurée en dry run) :
- de 5 à 9 k caractères au total, soit environ 1,5 à 2,5 k tokens en entrée ;
- dont 1,7 à 5,5 k caractères de pack et de requête, le reste étant le prompt système.

**Taille de la réponse** :
- un plan fait environ 1 à 2 k tokens, un message moins ;
- gpt-5.6-terra y ajoute son raisonnement (effort `medium`), de l'ordre de quelques milliers de tokens.

**Coût** (tarifs publics à vérifier) :
- **gpt-4o-mini** (tarif connu du script : 0,15 $ / 0,60 $ par million de tokens) : environ 0,001 $ par appel, **moins de 0,02 $ pour ses 6 appels** ;
- **gpt-5.6-terra** : son tarif n'est pas dans le script, donnez-le avec `--price`. À l'ordre de grandeur, un appel coûte au plus celui d'un appel deal health (0,05 à 0,15 $), puisque le prompt est environ deux fois plus court. Comptez donc **moins de 1 $ pour ses 6 appels**.

**Durée** :
- gpt-4o-mini : 5 à 20 s par appel ;
- gpt-5.6-terra : 30 à 120 s par appel ;
- comptez **10 à 25 minutes** en tout. Le pire cas (délai de 150 s atteint à chaque appel de X) est d'environ 17 minutes pour X seul.

⚠️ **TD-321** : en production, gunicorn tourne avec `--timeout 12` (`backend/Procfile`). Le rapport compte les appels de plus de 12 s (colonne `> 12 s`). Un run synchrone plus long est aujourd'hui tué par le worker web.

## Les cas (fictifs — `tests/fixtures/game_plan_eval/<cas>/`)

Chaque cas a son `seed.json` (créé par les chemins standards) et son `expected.json` (la vérité). Les **noms de famille sont plantés** dans le seed : le LLM ne doit jamais les recevoir (prénoms seulement).

| Cas | Sortie | Ce qui est planté |
|---|---|---|
| `call_mid_cycle` | plan | un CALL en SOLUTION_VALIDATION, un deal health v2 (info manquante : la revue sécurité IT), deux « Marc » (`P2 Marc (Finance)` / `P1 Marc (IT)`), un stakeholder sans contact (Lea) |
| `demo_end_of_cycle` | plan | une DEMO en CLOSING, un deal health v2 (info manquante : l'accord budgétaire du board) ; Sarah s'appelle **Price**, un nom de famille qui est aussi un mot courant |
| `campaign_no_dc` | plan | un CALL d'une séquence de campagne sans DC (étape 3 sur 4, deux appels sans réponse) : `campaign_diagnostic` attendu, et seulement ici |
| `email_fr_profile` | message | un EMAIL à Claire, profil stakeholder « fr » manuel : un message en français (PROFILE), avec un subject |
| `linkedin_default` | message | un LINKEDIN à Ivan, contact sans stakeholder : un message en anglais (DEFAULT), sans subject |
| `trap_no_figures` | plan | **le piège** : fiche vendeuse sans références ni chiffres, aucun chiffre dans les données. Rien ne doit être inventé (le brief v1 RED RUBAN : « reducing IT maintenance by 20 % saves 8 hours per week ») |

Avant tout appel, le script vérifie que l'activité préparée est éligible (G3) et qu'elle donne la sortie attendue.

## Contrôles automatiques (`scoring.py`)

| Contrôle | Règle |
|---|---|
| schéma valide | la réponse contre `PREP_CALL_OUTLINE_SCHEMA` ou `PREP_CALL_MESSAGE_SCHEMA` (le validateur du deal health, avec `anyOf`) |
| prénoms seulement | aucun nom de famille planté, **ni dans le prompt ni dans la sortie** |
| aucun chiffre inventé | chaque nombre de la sortie doit exister dans le **pack et la requête**. Le prompt système n'en fait pas partie : un « 70% » recopié de la consigne est inventé. Séparateurs ignorés (48 000 = 48,000 = 48000) ; un chiffre collé à des lettres (P1, v2) est un libellé. **Autorisés** (G13b) : une durée de réunion proposée (« a 30-minute working session », « ask for 20 minutes ») ; une date, y compris « 2 December 2026 », « December 2, 2026 », « 2026-12-02 », ou une année après une préposition (« in 2026 ») ; une heure (« 10:00 », « 2 pm », « 14h30 »). **Toujours inventés** s'ils sont absents du pack : un pourcentage, un montant, un gain ou un volume, en chiffres (« 20 % », « saves 8 hours per week », « 2000 hours ») ou en lettres (« over one month of labor », « saves two days ») |
| aucun nom inventé | l'heuristique du deal health, sur la prose seulement : les refs, labels et langues ne sont pas lus, ni le vocabulaire du Game Plan (plans B / C, canaux). Ne comptent pas comme inventés les jours de la semaine, les mois et leurs abréviations, ni un nom composé sur un nom de l'entrée (« Corvane-data »). Les mots trouvés sont listés pour relecture |
| aucun ethos / pathos / logos | `constants.PREP_CALL_RHETORIC_LABELS`, mots entiers |
| chaque participant a un angle | chaque label attendu a une entrée `participants` avec un angle non vide (plans) |
| plans A / B / C ≤ 3 | de 1 à 3 plans, étiquetés A, B, C dans l'ordre |
| ouverture en 5 parties | objectif, temps, agenda du client, notre agenda, résultat attendu, tous non vides |
| découverte = info manquante DH | un mot-clé de l'info manquante du deal health apparaît dans `discovery.missing_info` (cas avec un DH) |
| campaign_diagnostic au bon cas | présent si, et seulement si, le cas l'attend (`campaign_no_dc`) |
| langue par destinataire | le message de chaque destinataire est dans la langue attendue |
| subject | présent sur un email, absent sur LinkedIn |
| **PARSE_ERROR par cause** | une réponse refusée par le serveur est classée : terme rhétorique, nom de famille, **faux rejet**, ou structure. Un faux rejet est un nom de famille écrit comme mot courant : toutes ses occurrences sont en minuscule, comme « the price » pour Sarah Price |
| durée, tokens, coût | par appel, depuis l'audit du run (`sub_calls`). Le coût est estimé avec `PRICES_PER_MTOK` ou `--price` (« — » sans tarif) |

Ces contrôles sont prouvés sur des sorties écrites à la main, justes et fautives, par `tests/ai_pipelines/test_game_plan_eval_checks.py`.

**À trancher avec le taux de PARSE_ERROR** (décision PO, G10) : s'il n'est pas nul, le serveur passera du rejet au masquage du nom.

## Sorties (`evals/game_plan/out/<stamp>/`, ignoré par git ; un dossier non vide est refusé)

- **`report.md`** contient :
  - le récapitulatif par modèle : contrôles réussis, PARSE_ERROR par cause, durées, appels de plus de 12 s, tokens, coût, erreurs ;
  - la durée, les tokens et le coût de chaque appel ;
  - pour chaque cas, les contrôles des cellules côte à côte et les sorties résumées.
- `<cas>__<entrée>/call_NN.json` contient, pour chaque appel :
  - le prompt envoyé et **la réponse brute** ;
  - le JSON lu ;
  - la méta : durée, tokens, refs écartées ;
  - les métriques.
- `summary.csv` / `summary.md` : une ligne par appel (`eval_kit`). `--rescore` écrit `summary_rescored.*` et `report_rescored.md`.

## Dry run

`--dry-run` n'appelle aucune API : chaque appel reçoit une réponse fixe construite à partir de la vérité du cas.

Deux cellules sont **volontairement fautives**, pour montrer les contrôles rouges :
- `trap_no_figures` · gpt-4o-mini : un chiffre inventé, « 37 % … 430 hours ». Ces nombres ne peuvent pas venir d'une date du pack ;
- `demo_end_of_cycle` · gpt-5.6-terra : « the price » écrit comme mot courant. Le serveur le refuse, et c'est compté comme un **faux rejet**.

Le dry run prouve que la chaîne tourne ; il ne dit rien des modèles. Il est joué par `tests/ai_pipelines/test_game_plan_eval_dry_run.py`.

⚠️ Les modèles ne sont pas déterministes. Pour trancher entre deux modèles, comparez des taux sur plusieurs appels (`--n 3` ou plus), jamais une réponse isolée.
