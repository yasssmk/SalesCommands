# evals/next_steps — mesure des next steps (ligne de base, Sprint Next steps 3.0)

Script de mesure, **pas du code produit** : rien dans `app_modules/` ne l'importe.
Il ne laisse **rien** en base : tout ce qu'il crée (tenant, rep, compte, contact,
cycle de décision et ses étapes, conversation, runs, next steps) est annulé.
Chaque appel tourne dans son propre savepoint, et le run entier tient dans une
transaction qui n'est jamais commitée.

Il fait passer deux transcriptions de référence par le **vrai**
`NextStepsPipeline`. Rien n'est remplacé :
- la création de la conversation passe par `ActivityCreationService.create_with_entities`. Le cycle de décision est créé inline avec **ses étapes auto-créées**, et la conversation est posée sur l'étape du cas ;
- le prompt utilise le contexte v5 (date de conversation lue dans l'en-tête de la transcription, D7), la requête v1 et le prompt système ;
- le modèle, la température, `max_tokens`, le timeout et le retry de parsing sont ceux de la production ;
- le filtre de sécurité et `NextStepExtractor` s'appliquent comme en production.

Le script note les **next steps stockés**, c'est-à-dire ce que le rep voit. La
**réponse brute** est toujours enregistrée, y compris pour un appel en erreur.

La seule valeur remplacée est le nom de tenant envoyé comme « Seller »
(`--tenant-name`, `SalesCommands` par défaut). `ClientAccount.name` est unique,
donc le tenant d'éval porte un nom jetable.

Plomberie commune avec `evals/td279` : `evals/common/eval_kit.py` (RecordingProvider, boucle des N appels, `--n` / `--only` / `--model` / `--rescore` / `--dry-run`, `summary.csv` / `.md`).

## Commandes (depuis `backend/`, avec `OPENAI_API_KEY` dans l'environnement)

```bash
# La ligne de base : 2 variantes x 20 appels = 40 appels gpt-4o-mini
python evals/next_steps/run_next_steps_eval.py --n 20

# Une variante, quelques appels
python evals/next_steps/run_next_steps_eval.py --n 3 --only atelier

# Forcer un modèle DÉCLARÉ dans ai_pipelines/config.py PROVIDER_CONFIG
python evals/next_steps/run_next_steps_eval.py --n 20 --model gpt-5.4-mini-2026-03-17

# Recalculer le récap d'un run à partir des réponses enregistrées (après une
# correction de notation ou de expected.json) : AUCUN appel API, aucune base
python evals/next_steps/run_next_steps_eval.py --rescore evals/next_steps/out/<stamp>

# Vérifier la plomberie, sans appel API (réponses fixes)
python evals/next_steps/run_next_steps_eval.py --dry-run --n 2
```

**Coût et durée estimés de `--n 20`** (gpt-4o-mini, 40 appels séquentiels) :
- le prompt fait environ 10 à 12 k caractères, soit environ 3 k tokens en entrée ; la réponse, environ 0,5 à 1 k tokens en sortie ;
- au tarif public de gpt-4o-mini (0,15 $ par million de tokens en entrée, 0,60 $ par million en sortie, à vérifier), cela fait environ 0,001 $ par appel, donc **moins de 0,10 $ au total**, retries de parsing compris ;
- comptez **5 à 10 minutes** au total, environ 8 à 15 s par appel. Le pire cas est d'environ 20 minutes (timeout de 30 s à chaque appel).

## Variantes

| Variante | Transcription | Date (en-tête) | Étape DC de la conversation | Attendus |
|---|---|---|---|---|
| `atelier` | `../td279/transcript_atelier.txt` | 2026-10-20 | BUSINESS_CASE | A, B, C_prospect, C_vendeur (+ C_suivi, informatif) |
| `logistix` | `../td279/transcript_logistix.txt` | 2026-10-14 | QUALIFICATION | D (+ E, F, G, H, informatifs) |

## Vérité de référence (`expected.json`, à valider par le PO)

| Id | Attendu | Requis à partir de | Types acceptés | Fenêtre de date (bornes incluses) |
|---|---|---|---|---|
| A | EMAIL : envoyer le DPA et le SOC 2 (vendeur), avant vendredi | v1 | EMAIL | 2026-10-20 → 2026-10-23 |
| B | MEETING sécurité avec Laurent Petit (DSI), « dans deux semaines, un mardi » | v1 | MEETING | 2026-11-02 → 2026-11-06 (2026-11-03 attendu) |
| C_prospect | TASK **portée par le prospect** : Isabelle présente au contrôleur de gestion puis à Marc | v1 | TASK | 2026-10-20 → 2026-11-15 |
| C_vendeur | TASK vendeur : v1 du business case « la semaine prochaine » | v1 | TASK, EMAIL ⚠️ | 2026-10-26 → 2026-11-01 |
| C_suivi | suivi / relance de la validation du business case | **v2** (informatif en v1) | tous | 2026-10-20 → 2026-11-15 |
| D | MEETING avec Isabelle Roux (DAF), au plus tard fin novembre | v1 | MEETING | 2026-10-14 → 2026-11-30 |
| E | EMAIL : documentation technique pour Thomas | jamais (informatif) | EMAIL | aucune date attendue |
| F | TASK : business case pour Isabelle | jamais (informatif) | TASK | aucune date attendue |
| G | MEETING : session sécurité avec le DSI | jamais (informatif) | MEETING | aucune date attendue |
| H | EMAIL : questionnaire SOC 2 en amont | jamais (informatif) | EMAIL | aucune date attendue |

`required_from` dit à partir de quelle version du prompt next_steps l'attendu
compte dans le rappel (« attendus requis trouvés »). Les versions sont
comparées par leur numéro (v2 < v10). En dessous de sa version, ou avec
`null`, l'attendu est marqué « (info) » : il est mesuré comme les autres,
mais ne compte pas dans le rappel. La version prise en compte est celle du run
(`prompt_versions.next_steps`).

### Règles de match (tolérantes, documentées)

- Le match se fait sur le **titre** stocké, car la citation est une *justification* et plusieurs next steps peuvent partager la même.
- Les mots-clés sont comparés sans casse ni accents, la ponctuation valant un espace (« SOC-2 » donne « soc 2 »).
- Un mot-clé est un **mot entier**, sauf s'il se termine par `*`, auquel cas c'est un préfixe : `rencontr*` couvre « rencontre » et « rencontrer », mais `marc` ne couvre pas « marché ».
- Un signal correspond à un attendu quand **chaque groupe** de `all_of` a au moins un mot-clé dans le titre, et qu'**aucun** mot-clé de `none_of` n'y figure.
- Les exclusions qui séparent des attendus voisins :
  - B exclut `dpa`, `soc 2`, `document*` et `rapport*` : un next step sur les documents est A, jamais B ;
  - C_vendeur exclut `controleur`, `marc` et `final*` : la version finale du 15/11 n'est pas la v1 de la semaine prochaine.
- **Le type et la date ne servent pas au match.** Ils sont mesurés à part, sur le premier signal apparié.
- `quote_match.any_of` donne les mots-clés qui reconnaissent la **citation-justification propre** à l'attendu, avec la même syntaxe. Il sert uniquement à la mesure de fusion. Pour C_prospect, c'est la présentation elle-même (`controleur de gestion`, `puis a marc`) : « la version finale avant le quinze novembre » justifie aussi la v1 du vendeur.
- Les cas positifs et négatifs de ces règles sont figés dans `tests/evals/test_next_steps_scoring.py`.

### À valider par le PO

1. **C_vendeur** accepte EMAIL en plus de TASK (« on vous envoie une première version »). Faut-il TASK seul ?
2. **C_suivi** : j'ai lu « plus un suivi » comme une relance de la validation du business case. Est-ce bien ça, ou bien le récapitulatif promis « ce soir » ? C_suivi reste informatif, il ne compte pas dans « attendus requis trouvés ».
3. **B** : la fenêtre va du 2 au 6/11 (la semaine « dans deux semaines »). Faut-il exiger exactement le mardi 3/11 ?
4. Côté logistix, les next steps légitimes sont maintenant des attendus **informatifs** (E à H) ; « non appariés » ne compte donc plus que le vrai bruit. Restent hors vérité, et comptés « non appariés » : la version finale du business case (atelier) et le récapitulatif.
5. **C_prospect**, preuve propre : seulement la présentation (« contrôleur de gestion », « puis à Marc »). Avec « version finale / quinze novembre », la v1 vendeur qui cite l'échéance d'Isabelle compterait comme une fusion.

## Métriques (par appel dans `summary.csv`, agrégées sur N dans `summary.md`)

| Métrique | Définition |
|---|---|
| `<id>_present` | au moins un next step **stocké** correspond à l'attendu |
| `<id>_type_ok` | son type est dans les types acceptés (N/A si absent) |
| `<id>_date_in_window` | sa date est dans la fenêtre (N/A si absent ou sans date) ; `<id>_date_missing` : apparié mais sans date |
| `<id>_matches` / `duplicates` | nombre de signaux appariés ; doublons = appariés au-delà du premier, dans un même run |
| `duplicate_titles` | titres identiques après normalisation, dans un même run |
| `inventions` | next steps stockés dont la citation n'est **pas** dans la transcription (règle serveur : `TranscriptText.contains`, après retrait du label de locuteur, comme le contrôle a) de `people_evidence.py`) ; `inventions_raw` : même mesure sur la réponse brute |
| `unmatched` | stockés qui ne correspondent à aucun attendu, informatifs compris |
| `fusions` / `fusion_detail` / `<id>_absorbed_by` | **fusion** : un next step apparié à un attendu X, dont la citation est la preuve (`quote_match`) d'un **autre** attendu Y **absent** de l'appel. Y a été absorbé par X (`X<-Y`). Si Y est présent, la citation est seulement partagée et ce n'est pas une fusion. Cas de la ligne de base : D absorbé par F, `F<-D` |
| `emitted` / `persisted` | signaux de la réponse brute / stockés après filtre et extracteur |
| `new_<champ>`, `<id>_carried_ok`, `people_names_not_in_transcript` | nouveaux champs du 1.1 (étape, personnes, sujets, critère, `carried_by_prospect`) : **N/A sur la ligne de base**, car le prompt v1 ne les émet pas ; ils sont comptés dès que le prompt les émet |
| `prompt_leaks` | passages des transcriptions d'éval (suites de 5 mots, noms) trouvés dans le prompt **hors** de la transcription : doit être 0 |
| `duration_ms` / `wall_ms` / `error_type` | durée de l'appel réussi / durée réelle, erreurs comprises / type d'erreur (timeout, parsing, troncature, refus, provider) |

Un appel en erreur compte comme « absent » pour chaque attendu : les dénominateurs sont toujours N.

**Garde anti-fuite (point 7).** Avant tout appel, le prompt est rendu par les
builders de production et écrit dans `prompt_<variante>.txt`. Si une suite de
5 mots d'une transcription d'éval, ou l'un des noms listés dans
`expected.json`, apparaît hors de la transcription elle-même, le run s'arrête.
Un test vérifie la même chose sur le prompt de production.

## Sorties (`evals/next_steps/out/<stamp>/`, ignoré par git ; un dossier non vide est refusé)

- `prompt_atelier.txt` / `prompt_logistix.txt` : le prompt réel, système et user.
- `<variante>/call_NN.json` : **les réponses brutes**. Chaque fichier contient :
  - `attempts[]` : chaque prompt envoyé et sa `raw_response`, y compris le retry de parsing et l'erreur d'un appel qui a échoué ;
  - `parsed` ;
  - `persisted` : les next steps stockés ;
  - `meta` : modèle, durée, tokens, signaux écartés par le filtre ;
  - `error` / `error_type` et `metrics` ;
  - `decision_cycle_steps` / `conversation_step`.
- `summary.csv` contient une ligne par appel, et `summary.md` le récapitulatif.
- `--rescore` écrit `summary_rescored.csv` / `.md` à côté des fichiers d'origine, qui sont gardés. Il note les `persisted` enregistrés avec le `expected.json` actuel ; il ne rejoue pas le filtre de sécurité.

## Grille de lecture de `summary.md`

1. **Durées et erreurs.** Plus d'une erreur sur 20 appels, il faut regarder `error_type` avant de lire le reste.
2. **Bruit et inventions.** `fuites prompt` doit être 0. La colonne `attendus requis trouvés` donne le **rappel global** (x/4N pour atelier, x/N pour logistix).
   - Inventions stockées > 0 : le next step repose sur une citation absente de la transcription.
   - Inventions brutes > stockées : rien n'est écarté pour cette raison, l'écart vient du filtre de confiance et de l'extracteur.
   - Non appariés : du bruit, puisque les next steps légitimes connus sont des attendus informatifs ; regardez les titres dans `call_NN.json`.
   - Fusions > 0 : un attendu manque parce qu'un autre next step l'a absorbé, par exemple le rendez-vous avec Isabelle fondu dans la préparation du business case. C'est une perte réelle, pas un défaut de match ; la colonne « absorbé par » du tableau des attendus dit par qui.
3. **Attendus.** Pour chaque attendu, lisez dans l'ordre :
   - la présence (x/N) ;
   - le type correct et la date dans la fenêtre, comptés **sur les présents** ;
   - la date absente : le v1 met `null` quand il hésite ;
   - les doublons ;
   - les colonnes « types vus » et « dates vues », qui montrent la dispersion.
   Ordres de grandeur pour lire un taux sur 20 appels :
   - au moins 18/20 : acquis ;
   - de 10 à 17/20 : instable ;
   - moins de 10/20 : non acquis.
   Note pour **C_prospect** : le prompt v1 définit un next step comme une action « que le vendeur doit faire ».
4. **Nouveaux champs.** Tout est N/A sur la ligne de base. C'est la colonne qui bougera à partir de la 3.1.

⚠️ Les modèles ne sont pas déterministes, même à température 0. Comparez des
taux sur au moins 20 appels, jamais une réponse isolée. Pour comparer deux
prompts, relancez les deux mesures dans les mêmes conditions (même `--n`, même
modèle).
