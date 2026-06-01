# Rapport UX/Workflow — Prep Call (Activity Workspace)

**Version** : 1 (mai 2026)
**Objectif** : décrire de façon exhaustive le copilote de préparation d'avant-call (« Prep Call », nom de travail) : son but, son UX (volontairement mince), son contrat d'input, et surtout le coeur du sprint — la construction du prompt et du guide rhétorique. Document de référence pour la conversation d'implémentation : comprendre le but, dériver le plan, et concevoir la méthode / le prompt LLM.
**Scope** : l'onglet Preparation de l'Activity Workspace, le pipeline LLM `prep-call`, le contrat d'input (Prep Input Pack), le prompt, et le guide rhétorique en fichier constant.
**Hors scope** : extraction post-call (rapport Activity post-call), Deal Health (rapport DC) — tous deux fournissent la matière consommée ici.

> **Principe de ce sprint** : le Prep Call est à ~80% de l'ingénierie de prompt + assemblage de données, ~20% d'UX légère. La valeur d'un copilote incarné est dans l'intelligence du brief, pas dans des boutons. Si l'UX devait être riche, ce serait le signe que l'incarnation a échoué.

---

## 1. Ce que c'est

Avant un RDV important, l'AE déclenche le Prep Call. Le copilote lit ce que le deal a accumulé (signaux validés, dernier Deal Health, contexte du call à venir) et produit un **brief tactique incarné** : où on en est, l'objectif du call, comment convaincre, ce qu'il faut creuser, et le next step à obtenir.

Le Prep Call **incarne le copilote**. Il ne montre pas de la donnée — il **dit quoi faire**. C'est un ordre de mission, pas une lecture.

### 1.1 Distinction avec Deal Health (anti-doublon)

- **Deal Health** = la _lecture_ du deal (exhaustive, au niveau deal). Il **montre**.
- **Prep Call** = le _brief tactique_ pour CE call avec CETTE personne (distillé, sélectif, directif). Il **dit quoi faire**.

Deal Health = « voici où on en est ». Prep Call = « voici ta combinaison pour ce match ». L'un nourrit l'autre.

### 1.2 Le copilote vraiment réussi produit

Pas un dashboard. Six sorties concrètes :

- une lecture claire ;
- une priorité ;
- un angle rhétorique ;
- une question à poser ;
- une preuve à utiliser ;
- un next step à obtenir.

---

## 2. L'UX (mince)

- **Emplacement** : onglet **Preparation** de l'Activity Workspace.
- **Sans LLM** : état vide + bouton CTA « Préparer ce call ».
- **Avec LLM** : le brief affiché en texte structuré + contexte. Lisible en 2 minutes.
- **Édition** : l'AE peut ajuster le brief (le copilote propose, l'AE avise).
- **Stockage** : `Activity.preparation_notes`.
- **Déclenchement** : à la demande (bouton), pas auto — on ne crame pas de tokens sur des calls qui n'auront pas lieu.

Composants à créer : `PrepCallTab`, `PrepCallEmptyState` (CTA), `PrepCallBrief` (affichage + édition), hooks `usePrepCall` (dernier brief), `usePrepCallRunner` (lancement + polling). Stack habituelle (JSX, MUI, @ant-design/icons, SWR).

---

## 3. Structure du brief (la sortie)

Précédé du contexte, le brief tient en **3 blocs + next step** :

```
PREP — Démo PoC · Marie Dupont (Champion, Sales Ops) · Solution Validation

CONTEXTE
Marie est ton alliée mais ne porte pas le budget. La douleur est reconnue,
pas encore prouvée comme prioritaire.

1. OBJECTIFS DU CALL
   Principal · armer Marie pour défendre le projet en interne.
   Secondaire · identifier qui tient le budget.
   Nature de l'enjeu · CONVICTION business (pas l'ethos — elle te fait déjà
   confiance ; pas l'objection — rien ne bloque encore).
   Réussite si · Marie repart avec un argument chiffré + un nom de décideur.

2. RHÉTORIQUE (comment convaincre)
   Registre · factuel et posé. Elle te fait confiance — l'emphase la rendrait
   méfiante. Démontre, ne survends pas.
   Argument clé · le ROI temps.
   Pour le rendre tangible · « 10h/semaine, c'est un mois de travail par an
   jeté dans la consolidation. » (ancré sur SON chiffre)
   Preuve · la démo qui ramène ses 10h à 1h.

3. À CREUSER (les gaps)
   Impact business — ÉLICITATION ·
   « Quand vous remontez ces chiffres à votre direction, ça se passe comment ? »
   Budget — DIRECT (Marie est ton alliée) ·
   « Qui valide ce type d'investissement chez vous ? »

NEXT STEP À OBTENIR
   Un créneau avec le décideur budgétaire, fixé PENDANT le call.
   Pas « je vous envoie un récap » — propose deux dates séance tenante.
```

### 3.1 Bloc 1 — Objectifs du call

Le copilote **propose**, l'AE ajuste. Un objectif principal + éventuellement un secondaire. Chaque objectif est **typé par nature** : gagner en ethos (crédibilité) ? montrer la valeur (solution -> objectif) ? lever une objection / un coût ? Plus un **critère de réussite** explicite. Les objectifs sont **stockés de façon structurée** (pas du texte libre) pour permettre la comparaison visé/réalisé ultérieure (§6).

### 3.2 Bloc 2 — Rhétorique

Le coeur incarné. Selon l'objectif + l'interlocuteur, le copilote donne : le **registre** (incarné, jamais nommé), l'**argument clé**, une **reformulation parlante ancrée** (pas une métaphore gratuite), et la **preuve** à ressortir. Le guide rhétorique (§5) pilote ce bloc.

### 3.3 Bloc 3 — Gaps

Les informations manquantes prioritaires, chacune avec une **stratégie de récupération** : **question directe** (info qu'on peut demander frontalement) ou **élicitation** (info à faire émerger indirectement). Distinction de qualif vs procédural héritée du Deal Health.

### 3.4 Next step à obtenir

Toujours un **engagement concret et daté** : quel meeting, avec qui, pourquoi. **Règle dure : jamais « je reviens vers vous »** — le copilote propose une action mobilisatrice à décrocher pendant le call.

---

## 4. Le contrat d'input — Prep Input Pack

Le pipeline `prep-call` consomme le pack défini dans le doc Voyage §3.2 : `prep_context` (+ `step_expectations`), `maturity_snapshot`, `levers`, `stakeholder_focus`, `discovery_gaps` (qualif + procéduraux), `competitive_context`, `evidence_scope`. Tous les champs sont dérivables de ce qu'on capture déjà ; le `stakeholder_focus` au niveau contact arrive en V2 (MVP = département).

Mapping bloc de sortie <- source d'input :

- Contexte / Objectifs <- `prep_context` + `step_expectations` + `maturity_snapshot`
- Rhétorique <- `levers` + `stakeholder_focus` + `competitive_context`
- Gaps <- `discovery_gaps`
- Next step <- `step_expectations` + next steps en attente

---

## 5. Le guide rhétorique (fichier constant)

Le coeur réutilisable du copilote. Un **fichier de constantes** (`prep_call/rhetoric_guide.py` ou équivalent) que le pipeline charge pour, selon le contexte (objectif typé + maturité + interlocuteur), sélectionner un **registre**, un **format de réponse**, et des **garde-fous**. Jamais exposé en UI — c'est de la structure de prompt.

### 5.1 Les 6 registres (bibliothèque interne)

| #   | Registre                       | But                                     | Procédés                                         | Quand l'utiliser                                                 | À éviter si                                                            |
| --- | ------------------------------ | --------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 1   | **Démonstratif (logos)**       | convaincre par la logique et les faits  | raisonnement en 3 temps, causalité, chiffres     | profil analytique (CFO, IT, investisseur) ; démontrer le ROI     | le public veut être inspiré                                            |
| 2   | **Narratif (pathos)**          | faire ressentir, créer l'identification | récit vécu, contraste frustration->soulagement   | audience terrain (users, champion) ; faire ressentir le problème | le public attend du concret                                            |
| 3   | **Épidictique (valorisation)** | magnifier une vision / transformation   | glorification du progrès, de la maîtrise         | clôture de cycle, vision                                         | grandiloquent sans preuves                                             |
| 4   | **Délibératif (action)**       | pousser à la décision                   | appel à l'action, antithèse « subir vs piloter » | closing, fin de call, décideurs                                  | public pas encore convaincu                                            |
| 5   | **Analogique**                 | simplifier le complexe par une image    | analogie courte et frappante                     | amorce, vulgariser un concept                                    | en complément seulement ; jamais seul ; métaphore mal choisie brouille |
| 6   | **Aphoristique**               | frapper par une formule courte          | punchline, sentence                              | climax, phrase finale                                            | en abuser tue la clarté                                                |

### 5.2 Mapping contexte -> registre (heuristique du prompt)

```
SI objectif = démontrer ROI / convaincre profil analytique (CFO, IT)
   -> registre dominant : démonstratif (logos), format factuel/chiffré

SI objectif = faire ressentir le problème / audience terrain
   -> registre dominant : narratif (pathos), récit + contraste

SI objectif = pousser à la décision / closing
   -> registre dominant : délibératif, antithèse + appel à agir

SI objectif = inspirer une vision / clôture de cycle
   -> registre dominant : épidictique, MAIS toujours adossé à une preuve

SI besoin de simplifier un concept complexe
   -> registre complémentaire : analogique (jamais seul)

SI besoin de marquer un point clé
   -> registre complémentaire : aphoristique (avec parcimonie)
```

**Mixage autorisé** : 1 registre **dominant** + 1 **secondaire** maximum (ex. démonstratif pour prouver + délibératif pour le next step). Au-delà, c'est de la bouillie — interdit.

### 5.3 Modulation par la maturité (Deal Health)

Le registre se module aussi selon le diagnostic :

- **Confiance solution faible/incertaine** -> priorité au démonstratif (preuve, cas concret), bannir l'emphase (elle accroît la méfiance).
- **Urgence absente** -> délibératif léger, faire émerger le coût du statu quo, sans forcer.
- **Douleur ressentie non prouvée** -> narratif modéré + élicitation (faire dire la douleur, ne pas l'affirmer).
- **Acteur process (CFO)** -> démonstratif strict, sur SES critères de décision (le Metric), jamais les pains produit.

### 5.4 Garde-fous (règles dures du guide)

1. **Aucun élément rhétorique nommé en sortie** (pas de « logos », « genus grande », « registre pathétique »). Le registre s'incarne en geste concret.
2. **Aucun conseil sans ancrage** dans un signal/preuve fourni. À défaut de matière -> transformer en question de discovery.
3. **Reformulations parlantes uniquement ancrées** (rendre tangible un chiffre réel : « 10h/sem = un mois/an »). Jamais de métaphore gratuite ou poétique.
4. **Next step = engagement concret et daté**, jamais « je reviens vers vous ».
5. **Basé sur les preuves capturées** ; ne pas prédire, ne pas inventer d'intention.
6. **Ton coach, direct, bref** ; pas de remplissage, pas de banalité (« posez des questions ouvertes » est interdit).

---

## 6. La boucle visé / réalisé (adaptation, pas jugement)

Le Prep Call pose des objectifs structurés. Après le call, le post-call (analyse du transcript) peut **comparer visé vs atteint**. Règle absolue : **ce n'est jamais un jugement**. Le copilote ne dit pas « tu as raté ton objectif ». Il :

- **s'adapte** — le prochain brief tient compte de ce qui s'est passé ;
- **alerte** factuellement si un seuil baisse — « la confiance solution était suggérée, elle est passée à incertaine ; un doute est apparu » ;
- reste dans le ton neutre (pas de reproche au commercial).

La comparaison automatique est **V2** ; en MVP, on structure l'objectif pour la rendre possible plus tard.

---

## 7. Le prompt (structure)

1. **Rôle** : coach commercial senior briefant un AE avant un call. But : un brief tactique actionnable.
2. **Garde-fous** : les 6 règles dures (§5.4).
3. **Input** : le Prep Input Pack (§4).
4. **Raisonnement interne** (chain of thought non exposé) :
   - déterminer l'objectif (étape + gaps + maturité) ;
   - typer l'enjeu (ethos / valeur / objection / conviction) ;
   - choisir registre dominant + secondaire via le guide (§5) ;
   - sélectionner argument + preuve ancrée + reformulation tangible ;
   - prioriser les gaps + décider direct vs élicitation ;
   - formuler le next step engageant.
5. **Guide rhétorique** : injecté depuis le fichier constant (§5).
6. **Format de sortie** : Contexte -> Objectifs (typés + critère) -> Rhétorique -> Gaps (direct/élicitation) -> Next step.

---

## 8. Le pipeline `prep-call`

- **Déclenchement** : manuel, depuis l'onglet Preparation (bouton).
- **Input** : Prep Input Pack assemblé (signaux validés + dernier Deal Health + contexte de l'activité à venir + guide rhétorique).
- **Output** : le brief structuré, stocké dans `Activity.preparation_notes` ; éditable par l'AE.
- **Idempotence** : `input_hash` (pas de re-run identique).
- **Faisabilité** : tous les inputs dérivables de l'existant. Le brief n'invente rien — il distille et incarne.
- Endpoints : `POST module-ai-pipelines/prep-call/run/`, `GET module-ai-pipelines/prep-call/by-activity/{id}/`.

---

## 9. Multi-interlocuteurs (cadrage)

Un call peut réunir plusieurs personnes (ex. Marie + le CFO). **MVP** : le brief cible le `primary_contact` + une mention courte des autres (« le CFO sera là : son critère, c'est le ROI »). La combinaison complète par personne présente = V2.

---

## 10. Périmètre MVP vs V2

**MVP** : onglet Preparation (CTA / brief / édition) ; pipeline prep-call ; Prep Input Pack ; guide rhétorique en fichier constant ; brief 3 blocs + next step ; objectifs structurés ; garde-fous ; focus primary_contact.

**V2** : comparaison automatique visé/réalisé (boucle) ; combinaison par interlocuteur multiple ; ciblage contact fin (dépend de l'attribution contact) ; alertes de seuil enrichies.

---

## 11. Ce qui distingue le Prep Call

- **Copilote incarné** : il dit quoi faire, pas il montre de la donnée.
- **Ancrage absolu** : aucun conseil sans preuve ; à défaut, une question de discovery.
- **Rhétorique invisible** : 6 registres pilotent le prompt, jamais l'UI ; incarnés en gestes.
- **Next step toujours engageant** : jamais « je reviens vers vous ».
- **Boucle d'adaptation, pas de jugement** : s'adapte et alerte, ne reproche jamais.

---

_Fin du rapport. Base de référence pour l'implémentation du Prep Call. Coeur du sprint : le prompt (§7) + le guide rhétorique en fichier constant (§5) + le contrat d'input (§4)._

# Rapport UX/Workflow — Prep Call (Activity Workspace)

**Version** : 1.1 (mai 2026)
**Objectif** : décrire de façon exhaustive le copilote de préparation d'avant-call (« Prep Call », nom de travail) : son but, son UX (volontairement mince), son contrat d'input, et surtout le coeur du sprint — la construction du prompt et du guide rhétorique. Document de référence pour la conversation d'implémentation : comprendre le but, dériver le plan, et concevoir la méthode / le prompt LLM.
**Scope** : l'onglet Preparation de l'Activity Workspace, le pipeline LLM `prep-call`, le contrat d'input (Prep Input Pack), le prompt, et le guide rhétorique en fichier constant.
**Hors scope** : extraction post-call (rapport Activity post-call), Deal Health (rapport DC) — tous deux fournissent la matière consommée ici.

**Ajout v1.1** : le « mode de brief » (Discovery / Conviction / Proof / Decision) en sélecteur amont du guide rhétorique — garantit un brief utile même en matière pauvre.

> **Principe de ce sprint** : le Prep Call est à ~80% de l'ingénierie de prompt + assemblage de données, ~20% d'UX légère. La valeur d'un copilote incarné est dans l'intelligence du brief, pas dans des boutons. Si l'UX devait être riche, ce serait le signe que l'incarnation a échoué.

---

## 1. Ce que c'est

Avant un RDV important, l'AE déclenche le Prep Call. Le copilote lit ce que le deal a accumulé (signaux validés, dernier Deal Health, contexte du call à venir) et produit un **brief tactique incarné** : où on en est, l'objectif du call, comment convaincre, ce qu'il faut creuser, et le next step à obtenir.

Le Prep Call **incarne le copilote**. Il ne montre pas de la donnée — il **dit quoi faire**. C'est un ordre de mission, pas une lecture.

### 1.1 Distinction avec Deal Health (anti-doublon)

- **Deal Health** = la _lecture_ du deal (exhaustive, au niveau deal). Il **montre**.
- **Prep Call** = le _brief tactique_ pour CE call avec CETTE personne (distillé, sélectif, directif). Il **dit quoi faire**.

Deal Health = « voici où on en est ». Prep Call = « voici ta combinaison pour ce match ». L'un nourrit l'autre.

### 1.2 Le copilote vraiment réussi produit

Pas un dashboard. Six sorties concrètes :

- une lecture claire ;
- une priorité ;
- un angle rhétorique ;
- une question à poser ;
- une preuve à utiliser ;
- un next step à obtenir.

---

## 2. L'UX (mince)

- **Emplacement** : onglet **Preparation** de l'Activity Workspace.
- **Sans LLM** : état vide + bouton CTA « Préparer ce call ».
- **Avec LLM** : le brief affiché en texte structuré + contexte. Lisible en 2 minutes.
- **Édition** : l'AE peut ajuster le brief (le copilote propose, l'AE avise).
- **Stockage** : `Activity.preparation_notes`.
- **Déclenchement** : à la demande (bouton), pas auto — on ne crame pas de tokens sur des calls qui n'auront pas lieu.

Composants à créer : `PrepCallTab`, `PrepCallEmptyState` (CTA), `PrepCallBrief` (affichage + édition), hooks `usePrepCall` (dernier brief), `usePrepCallRunner` (lancement + polling). Stack habituelle (JSX, MUI, @ant-design/icons, SWR).

---

## 3. Structure du brief (la sortie)

Précédé du contexte, le brief tient en **3 blocs + next step** :

```
PREP — Démo PoC · Marie Dupont (Champion, Sales Ops) · Solution Validation

CONTEXTE
Marie est ton alliée mais ne porte pas le budget. La douleur est reconnue,
pas encore prouvée comme prioritaire.

1. OBJECTIFS DU CALL
   Principal · armer Marie pour défendre le projet en interne.
   Secondaire · identifier qui tient le budget.
   Nature de l'enjeu · CONVICTION business (pas l'ethos — elle te fait déjà
   confiance ; pas l'objection — rien ne bloque encore).
   Réussite si · Marie repart avec un argument chiffré + un nom de décideur.

2. RHÉTORIQUE (comment convaincre)
   Registre · factuel et posé. Elle te fait confiance — l'emphase la rendrait
   méfiante. Démontre, ne survends pas.
   Argument clé · le ROI temps.
   Pour le rendre tangible · « 10h/semaine, c'est un mois de travail par an
   jeté dans la consolidation. » (ancré sur SON chiffre)
   Preuve · la démo qui ramène ses 10h à 1h.

3. À CREUSER (les gaps)
   Impact business — ÉLICITATION ·
   « Quand vous remontez ces chiffres à votre direction, ça se passe comment ? »
   Budget — DIRECT (Marie est ton alliée) ·
   « Qui valide ce type d'investissement chez vous ? »

NEXT STEP À OBTENIR
   Un créneau avec le décideur budgétaire, fixé PENDANT le call.
   Pas « je vous envoie un récap » — propose deux dates séance tenante.
```

### 3.1 Bloc 1 — Objectifs du call

Le copilote **propose**, l'AE ajuste. Un objectif principal + éventuellement un secondaire. Chaque objectif est **typé par nature** : gagner en ethos (crédibilité) ? montrer la valeur (solution -> objectif) ? lever une objection / un coût ? Plus un **critère de réussite** explicite. Les objectifs sont **stockés de façon structurée** (pas du texte libre) pour permettre la comparaison visé/réalisé ultérieure (§6).

### 3.2 Bloc 2 — Rhétorique

Le coeur incarné. Selon l'objectif + l'interlocuteur, le copilote donne : le **registre** (incarné, jamais nommé), l'**argument clé**, une **reformulation parlante ancrée** (pas une métaphore gratuite), et la **preuve** à ressortir. Le guide rhétorique (§5) pilote ce bloc.

### 3.3 Bloc 3 — Gaps

Les informations manquantes prioritaires, chacune avec une **stratégie de récupération** : **question directe** (info qu'on peut demander frontalement) ou **élicitation** (info à faire émerger indirectement). Distinction de qualif vs procédural héritée du Deal Health.

### 3.4 Next step à obtenir

Toujours un **engagement concret et daté** : quel meeting, avec qui, pourquoi. **Règle dure : jamais « je reviens vers vous »** — le copilote propose une action mobilisatrice à décrocher pendant le call.

---

## 4. Le contrat d'input — Prep Input Pack

Le pipeline `prep-call` consomme le pack défini dans le doc Voyage §3.2 : `prep_context` (+ `step_expectations`), `maturity_snapshot`, `levers`, `stakeholder_focus`, `discovery_gaps` (qualif + procéduraux), `competitive_context`, `evidence_scope`. Tous les champs sont dérivables de ce qu'on capture déjà ; le `stakeholder_focus` au niveau contact arrive en V2 (MVP = département).

Mapping bloc de sortie <- source d'input :

- Contexte / Objectifs <- `prep_context` + `step_expectations` + `maturity_snapshot`
- Rhétorique <- `levers` + `stakeholder_focus` + `competitive_context`
- Gaps <- `discovery_gaps`
- Next step <- `step_expectations` + next steps en attente

---

## 5. Le guide rhétorique (fichier constant)

Le coeur réutilisable du copilote. Un **fichier de constantes** (`prep_call/rhetoric_guide.py` ou équivalent) que le pipeline charge pour, selon le contexte (objectif typé + maturité + interlocuteur), sélectionner un **mode de brief**, un **registre**, un **format de réponse**, et des **garde-fous**. Jamais exposé en UI — c'est de la structure de prompt.

### 5.0 Le mode de brief (sélecteur amont — robustesse en mode dégradé)

Avant de choisir un registre, le copilote détermine le **mode de brief** d'après l'état des preuves (Deal Health + signaux). C'est ce qui garantit que le Prep Call reste utile **même quand la matière est pauvre** — il ne produit jamais un brief vide ou générique, il bascule dans le mode adapté.

| Mode           | Déclencheur (état des preuves)                                                       | Ce que le brief privilégie                                                                            |
| -------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| **Discovery**  | preuves insuffisantes, gaps majeurs (douleur/urgence non prouvées, stakeholder flou) | faire émerger l'info : questions de découverte, identifier qui adresser, pas d'argumentaire prématuré |
| **Conviction** | problème reconnu mais pas encore prioritaire                                         | transformer un intérêt en enjeu : relier au business, faire ressentir le coût du statu quo            |
| **Proof**      | conviction présente mais confiance solution faible/incertaine                        | démontrer : cas concret, ROI chiffré, lever le doute par la preuve                                    |
| **Decision**   | maturité haute, il faut engager                                                      | obtenir l'engagement : next step ferme, antithèse subir/piloter, créneau daté                         |

Le mode conditionne ensuite le registre dominant (§5.2). Règle de robustesse : **un brief produit toujours quelque chose d'actionnable** — à matière pauvre, c'est un brief de Discovery (qui identifie ce qu'il faut aller chercher), jamais un brief creux.

### 5.1 Les 6 registres (bibliothèque interne)

| #   | Registre                       | But                                     | Procédés                                         | Quand l'utiliser                                                 | À éviter si                                                            |
| --- | ------------------------------ | --------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 1   | **Démonstratif (logos)**       | convaincre par la logique et les faits  | raisonnement en 3 temps, causalité, chiffres     | profil analytique (CFO, IT, investisseur) ; démontrer le ROI     | le public veut être inspiré                                            |
| 2   | **Narratif (pathos)**          | faire ressentir, créer l'identification | récit vécu, contraste frustration->soulagement   | audience terrain (users, champion) ; faire ressentir le problème | le public attend du concret                                            |
| 3   | **Épidictique (valorisation)** | magnifier une vision / transformation   | glorification du progrès, de la maîtrise         | clôture de cycle, vision                                         | grandiloquent sans preuves                                             |
| 4   | **Délibératif (action)**       | pousser à la décision                   | appel à l'action, antithèse « subir vs piloter » | closing, fin de call, décideurs                                  | public pas encore convaincu                                            |
| 5   | **Analogique**                 | simplifier le complexe par une image    | analogie courte et frappante                     | amorce, vulgariser un concept                                    | en complément seulement ; jamais seul ; métaphore mal choisie brouille |
| 6   | **Aphoristique**               | frapper par une formule courte          | punchline, sentence                              | climax, phrase finale                                            | en abuser tue la clarté                                                |

### 5.2 Mapping contexte -> registre (heuristique du prompt)

```
SI objectif = démontrer ROI / convaincre profil analytique (CFO, IT)
   -> registre dominant : démonstratif (logos), format factuel/chiffré

SI objectif = faire ressentir le problème / audience terrain
   -> registre dominant : narratif (pathos), récit + contraste

SI objectif = pousser à la décision / closing
   -> registre dominant : délibératif, antithèse + appel à agir

SI objectif = inspirer une vision / clôture de cycle
   -> registre dominant : épidictique, MAIS toujours adossé à une preuve

SI besoin de simplifier un concept complexe
   -> registre complémentaire : analogique (jamais seul)

SI besoin de marquer un point clé
   -> registre complémentaire : aphoristique (avec parcimonie)
```

**Mixage autorisé** : 1 registre **dominant** + 1 **secondaire** maximum (ex. démonstratif pour prouver + délibératif pour le next step). Au-delà, c'est de la bouillie — interdit.

### 5.3 Modulation par la maturité (Deal Health)

Le registre se module aussi selon le diagnostic :

- **Confiance solution faible/incertaine** -> priorité au démonstratif (preuve, cas concret), bannir l'emphase (elle accroît la méfiance).
- **Urgence absente** -> délibératif léger, faire émerger le coût du statu quo, sans forcer.
- **Douleur ressentie non prouvée** -> narratif modéré + élicitation (faire dire la douleur, ne pas l'affirmer).
- **Acteur process (CFO)** -> démonstratif strict, sur SES critères de décision (le Metric), jamais les pains produit.

### 5.4 Garde-fous (règles dures du guide)

1. **Aucun élément rhétorique nommé en sortie** (pas de « logos », « genus grande », « registre pathétique »). Le registre s'incarne en geste concret.
2. **Aucun conseil sans ancrage** dans un signal/preuve fourni. À défaut de matière -> transformer en question de discovery.
3. **Reformulations parlantes uniquement ancrées** (rendre tangible un chiffre réel : « 10h/sem = un mois/an »). Jamais de métaphore gratuite ou poétique.
4. **Next step = engagement concret et daté**, jamais « je reviens vers vous ».
5. **Basé sur les preuves capturées** ; ne pas prédire, ne pas inventer d'intention.
6. **Ton coach, direct, bref** ; pas de remplissage, pas de banalité (« posez des questions ouvertes » est interdit).

---

## 6. La boucle visé / réalisé (adaptation, pas jugement)

Le Prep Call pose des objectifs structurés. Après le call, le post-call (analyse du transcript) peut **comparer visé vs atteint**. Règle absolue : **ce n'est jamais un jugement**. Le copilote ne dit pas « tu as raté ton objectif ». Il :

- **s'adapte** — le prochain brief tient compte de ce qui s'est passé ;
- **alerte** factuellement si un seuil baisse — « la confiance solution était suggérée, elle est passée à incertaine ; un doute est apparu » ;
- reste dans le ton neutre (pas de reproche au commercial).

La comparaison automatique est **V2** ; en MVP, on structure l'objectif pour la rendre possible plus tard.

---

## 7. Le prompt (structure)

1. **Rôle** : coach commercial senior briefant un AE avant un call. But : un brief tactique actionnable.
2. **Garde-fous** : les 6 règles dures (§5.4).
3. **Input** : le Prep Input Pack (§4).
4. **Raisonnement interne** (chain of thought non exposé) :
   - **déterminer le mode de brief** (Discovery / Conviction / Proof / Decision) selon l'état des preuves (§5.0) ;
   - déterminer l'objectif (étape + gaps + maturité) ;
   - typer l'enjeu (ethos / valeur / objection / conviction) ;
   - choisir registre dominant + secondaire via le guide (§5), conditionné par le mode ;
   - sélectionner argument + preuve ancrée + reformulation tangible ;
   - prioriser les gaps + décider direct vs élicitation ;
   - formuler le next step engageant.
5. **Guide rhétorique** : injecté depuis le fichier constant (§5).
6. **Format de sortie** : Contexte -> Objectifs (typés + critère) -> Rhétorique -> Gaps (direct/élicitation) -> Next step.

---

## 8. Le pipeline `prep-call`

- **Déclenchement** : manuel, depuis l'onglet Preparation (bouton).
- **Input** : Prep Input Pack assemblé (signaux validés + dernier Deal Health + contexte de l'activité à venir + guide rhétorique).
- **Output** : le brief structuré, stocké dans `Activity.preparation_notes` ; éditable par l'AE.
- **Idempotence** : `input_hash` (pas de re-run identique).
- **Faisabilité** : tous les inputs dérivables de l'existant. Le brief n'invente rien — il distille et incarne.
- Endpoints : `POST module-ai-pipelines/prep-call/run/`, `GET module-ai-pipelines/prep-call/by-activity/{id}/`.

---

## 9. Multi-interlocuteurs (cadrage)

Un call peut réunir plusieurs personnes (ex. Marie + le CFO). **MVP** : le brief cible le `primary_contact` + une mention courte des autres (« le CFO sera là : son critère, c'est le ROI »). La combinaison complète par personne présente = V2.

---

## 10. Périmètre MVP vs V2

**MVP** : onglet Preparation (CTA / brief / édition) ; pipeline prep-call ; Prep Input Pack ; guide rhétorique en fichier constant ; brief 3 blocs + next step ; objectifs structurés ; garde-fous ; focus primary_contact.

**V2** : comparaison automatique visé/réalisé (boucle) ; combinaison par interlocuteur multiple ; ciblage contact fin (dépend de l'attribution contact) ; alertes de seuil enrichies.

---

## 11. Ce qui distingue le Prep Call

- **Copilote incarné** : il dit quoi faire, pas il montre de la donnée.
- **Ancrage absolu** : aucun conseil sans preuve ; à défaut, une question de discovery.
- **Rhétorique invisible** : 6 registres pilotent le prompt, jamais l'UI ; incarnés en gestes.
- **Next step toujours engageant** : jamais « je reviens vers vous ».
- **Boucle d'adaptation, pas de jugement** : s'adapte et alerte, ne reproche jamais.

---

_Fin du rapport. Base de référence pour l'implémentation du Prep Call. Coeur du sprint : le prompt (§7) + le guide rhétorique en fichier constant (§5) + le contrat d'input (§4)._
