# Rapport UX/Workflow — Decision Cycle Workspace

**Version** : 2 (mai 2026)
**Objectif** : décrire de façon exhaustive le workflow utilisateur et l'UX du Decision Cycle (la vue « opportunité » de SalesCommands). Document de référence pour la conversation d'implémentation : il doit permettre, en début de conversation, de comprendre le but, de disposer de toutes les informations nécessaires pour en dériver un plan d'implémentation et concevoir les méthodes / prompts LLM.
**Scope** : la liste des DC côté Account (DC cards), le DC Workspace (onglets Timeline / People / Products & Financial / Strategic / Signals), le pipeline LLM `deal-health`, et les types de signaux qui alimentent ces vues.
**Hors scope** : Activity Workspace (rapport post-call), Account Overview, Account Qualification, et la conception détaillée du pipeline `prep-call` (le contrat de données Prep Call est néanmoins esquissé).

**Changements v1 → v2** : ajout du modèle mental unificateur ; clarification de la règle Themes <-> People (même matière, deux pivots) ; nouveaux types de signaux (People, Contrainte) ; gestion du concurrent par TechStack ; attribution `target_department` ; règle `human_impact` self-report ; Metric (M de MEDDPICC) logé dans Contrainte ; résistance rattachée à un acteur ; connexion People <-> Timeline ; migration des critères de step.

---

## 1. Contexte et fondations

### 1.1 Ce qu'est un Decision Cycle

Le **Decision Cycle (DC)** est l'unité centrale de SalesCommands : l'équivalent d'une **opportunité** dans un CRM classique — un processus de décision d'achat en cours entre nous et un compte. On y accède depuis le workspace du compte. Un compte peut avoir plusieurs DC ; un seul est actif (`is_active`). Pipeline fixe en 5 étapes (DecisionSteps) : Qualification -> Technical Fit -> Solution Validation -> Business Case -> Closing.

### 1.2 État actuel (audit)

Aujourd'hui le DC se visualise dans l'Account Workspace -> onglet Decision Cycle (`DecisionCycleTab.jsx`) : sélecteur de cycle, timeline pipeline 5 colonnes, état vide, modale create/edit, quick-add d'activité. Les champs riches existent côté backend (`DecisionCycle` : `estimated_value`, `outcome`, `is_active`, `source_campaign`, `estimated_timeline_days`, `validated_steps_count` ; `DecisionStep` : `criterias`, `metrics`, `description`, `goal`, `manager_notes`, `all_contacts`, `effective_start_date`), mais sont peu exploités par l'UI.

### 1.3 Ce qu'on construit

Deux changements majeurs : (1) côté Account, l'accès aux DC devient une **liste de DC cards** avec navigation vers le workspace ; (2) un **DC Workspace à 5 onglets**, dont un onglet **Strategic** alimenté par le pipeline LLM `deal-health`.

### 1.4 Consommateurs

- **AE en préparation** (principal) : war room — comprendre où en est le deal et comment gagner, en quelques minutes.
- **Manager** (secondaire) : supervision — état du deal, risques.

### 1.5 Principe directeur non négociable

> Le Deal Health mesure la maturité du deal **à partir des preuves capturées dans SalesCommands**, pas la vérité absolue du deal.

Il ne conclut jamais sur ce qu'il ne sait pas, et n'humilie jamais l'AE. Toutes les règles QA en découlent (§12).

### 1.6 Le modèle mental (clé de lecture de tout le reste)

Un deal = faire avancer une vente à travers des étapes, en donnant à chaque acteur ce qui le débloque. **Trois questions, trois vues, trois niveaux** :

| Vue             | Question                       | Niveau                            |
| --------------- | ------------------------------ | --------------------------------- |
| **Themes**      | Quel est le problème ?         | le SUJET (problème business)      |
| **People**      | Comment je parle à qui ?       | l'ACTEUR (personne / département) |
| **Deal Health** | Où on en est, comment gagner ? | le DEAL (global)                  |

**Moteur** : le **Prep Call** croise les trois à chaque étape -> donne la combinaison de l'interlocuteur du prochain call + liste ce qu'il faut récupérer.

Frontière à retenir (source de confusion récurrente) :

- **People = par acteur, descriptif** (qui, son rôle, son code).
- **Deal Health = global, interprétatif** (maturité du deal entier + leviers). Ne descend pas à l'acteur.
- **Le Prep Call est le pont** : diagnostic global (Deal Health) + code de l'interlocuteur (People) -> combinaison pour CE call.

### 1.7 La règle Themes <-> People (à graver — c'est ce qui crée la confusion)

Themes et People exploitent **la même matière** (les signaux validés), pivotée sur deux axes différents :

```
              MÊME MATIÈRE (signaux validés)
                        |
        +---------------+----------------+
        v                                v
   pivot par SUJET                 pivot par ACTEUR
   = THEMES                        = PEOPLE
```

Chaque pivot révèle ce que l'autre cache. Themes fait apparaître la corroboration et les sujets prioritaires (cache : qui pense quoi). People fait apparaître le rôle, le code de décision, les résistances (cache : la vue d'ensemble). **People a en plus une matière exclusive** (rôles, critères de décision, résistances) absente de Themes.

**Règle de design anti-doublon** : le **détail** de la qualif (pains / objectifs / impacts en entier) ne se montre **qu'à un seul endroit — Themes**. People montre, par acteur : sa matière **exclusive** (rôle, contraintes/critères, résistances) + un **résumé léger** de ce qu'il a exprimé, avec lien vers Themes pour le détail. **On ne déroule jamais deux fois le détail des pains.**

### 1.8 Note sur le nommage

Les noms internes (DRI, dimensions, etc.) sont des noms de travail. Les libellés UI sont à retravailler — **DRI ne doit jamais apparaître tel quel** (§13).

---

## 2. La liste de DC côté Account (DC cards)

L'onglet Decision Cycle de l'Account passe d'un sélecteur direct à une **liste de DC cards**, sur le modèle de la liste de signaux.

```
+----------------------------------------------------------------+
|  DECISION CYCLES                              + New cycle      |
|  [ Active ] [ All ] [ Won ] [ Lost ]                           |
+----------------------------------------------------------------+
|  +- Module Consolidation v2 ----------- Active -------------+ |
|  | EUR 180 000 - Solution Validation (3/5)  ***oo           | |
|  | Closing vise: 12 sept - Last activity: 10 mai            | |
|  | (!) Economic buyer not identified                        | |
|  |                          [Open] [Run Deal Health] [...]   | |
|  +----------------------------------------------------------+ |
+----------------------------------------------------------------+
```

Contenu d'une card : nom, valeur estimée (sans amplification), étape + progression, statut, closing date + dernière activité, alerte contextuelle la plus critique (ex. rôle clé manquant, inactivité), actions (`Open`, `Run Deal Health`, menu `...`). Filtres par statut. Click -> DC Workspace (onglet **Strategic** si Deal Health a tourné, sinon **Timeline**).

---

## 3. Architecture du DC Workspace

Workspace à **5 onglets**, cohérent avec Account et Activity Workspace. On abandonne le carrousel.

```
DC Workspace
|-- Timeline              (activités par étape + critères de step)
|-- People                (acteurs du cycle : rôles, code, résistances)
|-- Products & Financial  (produits du deal x volume)
|-- Strategic             (Deal Health + Themes)
+-- Signals               (liste à plat du DC)
```

Au-dessus : bandeau d'identité + sélecteur de DC.

---

## 4. Bandeau d'identité du deal

```
+----------------------------------------------------------------------+
| Module Consolidation v2                              [DC selector v] |
| EUR 180 000 - Solution Validation (3/5)  ***oo     Active - 42 days |
| Closing vise: 12 sept - Next: "Demo PoC" (Wed 12 May)               |
|              [Run Deal Health] [Edit] [Close cycle v]                |
+----------------------------------------------------------------------+
```

Nom - valeur estimée - étape + progression - statut + âge - closing date (`estimated_timeline_days`) - prochaine action (ou incitation si vide) - actions - sélecteur de DC.

---

## 5. Onglet Timeline

5 colonnes = 5 étapes. Cartes d'activité par colonne (statut, date, contacts). Vue d'exécution existante.

**Ajout v2 — critères de step.** Le « workspace steps » dédié est destiné à disparaître. Les données du DecisionStep (`criterias`, `metrics`, `goal`, `success_criteria`) migrent ici : un clic sur l'**en-tête d'une colonne d'étape** ouvre ses attentes — « ce qu'il faut accomplir pour valider cette étape ».

(!) Distinction importante : `DecisionStep.criterias` = **critère de passage de l'étape** (ce que **nous** devons accomplir). C'est **différent** du Metric d'un acteur (le M de MEDDPICC = ce sur quoi un acteur **décide**, logé dans la Contrainte — voir §11). Les deux coexistent et ne doivent pas être confondus.

---

## 6. Onglet People

### 6.1 Principe

People rassemble **tous les acteurs du cycle d'achat** — pas seulement ceux qui ont parlé. Organisation **par département** (maille stable). Rôles **MEDDPICC** affichés en chip et **filtrables** transversalement.

### 6.2 Connexion People <-> Timeline (bidirectionnelle)

- Toute personne participant à une activité du DC **apparaît dans People**.
- Tout acteur de People est relié à **ses activités** (passées et planifiées) — lien direct vers la Timeline.
- People se peuple aussi via les **next steps** : un NextStep « le devis doit être validé par le CFO » -> crée une activity (task) impliquant le CFO -> le CFO entre dans People comme acteur du cycle, **même sans avoir participé à un call**.

Cohérence : pas de personne dans People sans lien à une activité (passée ou planifiée) ; pas d'acteur d'activité absent de People.

### 6.3 Affichage conditionnel au rôle

Ce que People montre pour un acteur **dépend de son rôle dans le cycle** :

- **Acteur en lien direct avec le produit** (Champion, End User — il _vit_ le problème) -> **résumé de la qualif qui le concerne** : ce qu'il veut, ce qui le gêne (avec lien vers Themes pour le détail). « Comment le problème le touche. »
- **Acteur de procédure** (Economic Buyer / CFO, Procurement, juridique — pas concerné par le produit) -> **infos de décision** : son rôle, ses **critères / métriques de décision** (la Contrainte, §11), le but de l'étape qu'il gouverne. « Ce qu'il lui faut pour valider. »

Plus les **résistances** de l'acteur (le Frein lui est rattaché — voir §11.5), car une résistance est humaine, jamais « business ».

### 6.4 Layout

```
People               [ All ] [ Decideur ] [ Champion ] [ EB ] [ Influenceur ] [ User ]

+- SALES OPS ---------------------------------------------+
| Marie Dupont        Champion - influence ^ - principal  |
|   Concernee par - visibilite reporting, 10h manuel  ->  |   <- resume, detail dans Themes
|   Resiste       - ne porte pas le budget                |
|   Activites     - Discovery (10 mai), Demo PoC (3 juin) |
+---------------------------------------------------------+

+- FINANCE -----------------------------------------------+
| Economic Buyer - [a identifier (!)]                     |
|   Criteres de decision - ROI > 20% sous 18 mois (ferme) |   <- Contrainte / Metric
|   Gouverne - validation Business Case                   |
+---------------------------------------------------------+

+- NON RATTACHE ------------------------------------------+
| 2 signaux sans departement -> [Requalify]               |
+---------------------------------------------------------+
```

### 6.5 Objectif de la vue

Adapter le pitch à chaque persona : le décideur veut du ROI, l'IT le fit technique, le user la simplicité. People donne, acteur par acteur, **quoi dire à qui** et **à quoi il est réceptif**.

---

## 7. Onglet Products & Financial

Produits du deal x volume = taille du deal. Modèle `DealProduct` -> `ProductCatalog` tenant (à modéliser). Vue simple, pas de forecast.

---

## 8. Onglet Strategic — Deal Health + Themes

Deux vues (sous-navigation interne).

### 8.1 État sans LLM

Si le pipeline Deal Health n'a jamais tourné, les deux vues affichent un **état vide + Readiness score + CTA** :

```
+----------------------------------------------------------------+
|            Aucune analyse strategique disponible              |
|   Lancez une analyse Deal Health pour obtenir un diagnostic.  |
|   Readiness: 70% - assez d'elements pour une analyse utile    |
|                    [ Run Deal Health ]                        |
+----------------------------------------------------------------+
```

Le **Readiness score** est déterministe (signaux validés, stakeholders identifiés, transcripts dispo). La matière brute reste accessible dans l'onglet Signals.

### 8.2 Vue Deal Health (après run)

```
Deal Health                                          [Themes ->]

+- Evidence coverage ------------------------------------------+
| 18 validated signals - 4 transcripts - last analysis May 22  |
| Diagnostic based on captured evidence.   [Run] [Add context] |
+--------------------------------------------------------------+

+- Diagnostic global ------------------------------------------+
| Le client reconnait un probleme operationnel, mais la        |
| douleur ressentie et l'urgence ne sont pas encore prouvees.  |
+--------------------------------------------------------------+

+- Maturite du deal (7 dimensions) ----------------------------+
| Probleme reconnu        Confirme              [detail]       |
| Douleur ressentie       Preuves manquantes    [detail]       |
| Impact compris          Incertain             [detail]       |
| Gain desire             Suggere par preuves   [detail]       |
| Urgence                 Preuves manquantes    [detail]       |
| Volonte d'agir          Incertain             [detail]       |
| Confiance solution      Suggere par preuves   [detail]       |
+--------------------------------------------------------------+

+- Leviers strategiques (nom UI a definir - "DRI" interne) ----+
| Desirs/Objectifs - Contraintes - Valeur(gains) - Cout(freins)|
+--------------------------------------------------------------+

+- Discovery Gaps ---------------------------------------------+
| - Douleur ressentie non qualifiee                            |
| - Urgence non prouvee                                        |
| - Process de validation Finance inconnu (duree, criteres)    |  <- gap procedural
+--------------------------------------------------------------+

[ mini snapshot history : *--*--*--* ]
```

#### 8.2.1 Les 7 dimensions (sales-friendly, evidence-based)

Diagnostic **global**. Formulé en langage sales :

1. **Problème reconnu** — voient-ils vraiment le problème ?
2. **Douleur ressentie** — le problème les dérange-t-il vraiment ?
3. **Impact compris** — ont-ils compris ce que ça leur coûte ?
4. **Gain désiré** — voient-ils ce qu'ils ont à gagner ?
5. **Urgence** — pourquoi maintenant ?
6. **Volonté d'agir** — prêts à changer / investir / mobiliser ?
7. **Confiance solution** — nous voient-ils comme une solution crédible ?

Statut **evidence-based** : `Confirmé - Suggéré par preuves - Incertain - Preuves manquantes - Preuves contradictoires`.

**Règle d'or** : pas de preuve -> « Preuves manquantes », jamais « Faible ». _Faible_ = on sait que c'est faible ; _Preuves manquantes_ = on n'a pas creusé. Chaque ligne cliquable -> drill-down (evidence / non capturé / add context, ton neutre).

#### 8.2.2 Leviers (DRI interne)

Diagnostic dit « où en est-on », leviers disent « sur quoi j'appuie ». Quatre regroupements depuis les signaux validés : **Désirs/Objectifs** (Objective), **Contraintes** (Constraint — ex-« Identité »), **Valeur/gains** (Pain + Impact), **Coût/freins** (Blocker). Priorisés par le LLM selon le diagnostic.

#### 8.2.3 Discovery Gaps

Version actionnable des dimensions en « preuves manquantes ». **Deux familles** :

- gaps de **qualif** (douleur non qualifiée, urgence non prouvée...) ;
- gaps **procéduraux** (étape future dont on ignore durée/critères — ex. « process de validation Finance inconnu »), détectés par le service Gap Analysis.

Ton neutre obligatoire : « non qualifié dans les preuves capturées », jamais « le commercial n'a pas creusé ». (V2 : bouton « Add to next prep ».)

#### 8.2.4 Mini snapshot history

Élément léger : évolution des snapshots dans le temps. Pas une vue à part.

### 8.3 Vue Themes

Réutilise le **cluster thématique cross-type** (Account), scopé au DC. **C'est ICI que vit le détail complet de la qualif** (voir règle §1.7).

```
Themes                                          [<- Deal Health]
[ All ] [ Operations x Time ] [ Budget/Timing ] [ Solution Fit ]

+- Operations x Time ------------------------------------------+
| Pains       - Reporting manuel 10h/semaine                   |
| Objectives  - Reduire le temps de preparation                |
| Impacts     - Visibilite retardee                            |
| Frictions   - Budget owner non identifie                     |
|                                          [View source signals]|
+--------------------------------------------------------------+
```

Par thème (`what x dimension`) : pains, objectifs, impacts, freins + signaux sources. **Pas de mini-diagnostic par thème** (le diagnostic reste global). Même état vide + CTA que Deal Health.

---

## 9. Onglet Signals

Liste à plat de tous les signaux du DC. Partage `SignalDetailCard` avec Activity (flat) et Account. Filtres statut/type/thème. Validation, rejet, archivage, édition. Toujours disponible, même sans Deal Health.

---

## 10. Le pipeline `deal-health`

### 10.1 Déclenchement

Manuel, depuis le bandeau du DC ou la DC card. Pas depuis une Activity (raisonne au niveau deal).

### 10.2 Input — Evidence Pack

Plus que les signaux validés : signaux validés + **transcripts liés** (pour le _comment_ c'est dit) + contexte manuel + activities/next steps + produits/montant/étape + snapshot précédent. C'est ce qui distingue _pain mentionné_ de _pain ressenti_. Conséquence : input large -> tokens + prompt complexes, dépendance aux transcripts dispo et sanitized.

### 10.3 Output — snapshot daté

Diagnostic global - statut des 7 dimensions - evidence + manquant par dimension - Discovery Gaps (qualif + procéduraux) - leviers priorisés - themes - évolution - _(backend V2)_ `internal_follow_up_context` pour le Prep Call. Stockage : `DealHealthSnapshot` (modèle dédié — vote) vs `AIPipelineRun.output`.

### 10.4 Règles de cadrage

Le LLM peut : extraire l'explicite, interpréter la maturité avec evidence, repérer les trous, comparer snapshots. Il ne doit **jamais** : prédire le closing, donner une probabilité, deviner une intention cachée, affirmer une douleur forte sans preuve textuelle.

---

## 11. Les types de signaux (référence consolidée)

### 11.1 Tableau récapitulatif

| Type                         | Rôle                                          | Attribution « concerné »                                              | Où il atterrit                                           |
| ---------------------------- | --------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------- |
| **Pain**                     | diagnostic du problème                        | `target_department` (MVP) + `scope_level`                             | Themes (détail) ; People (résumé, acteur produit)        |
| **Objective**                | objectif business                             | `target_contact`/`target_department` (existant)                       | Themes (détail) ; People (résumé)                        |
| **Impact**                   | conséquence / preuve                          | `target_department` (MVP) ; `human_impact` si **self-report**         | Themes (détail) ; People (résumé, acteur produit)        |
| **TechStack**                | outils / concurrent                           | `usage_department` ; `decision_cycle` null = en place / set = en lice | Themes (cluster tech) ; Deal Health (Confiance solution) |
| **Frein** (Blocker)          | **résistance — humaine**                      | rattaché à un acteur (contact/dept)                                   | People (sous l'acteur qui résiste) ; Deal Health (Coût)  |
| **Contrainte** (Constraint)  | règles + **Metric / critère de décision (M)** | `target_department` ; `rigidity` (ferme/flexible)                     | People (acteur process) ; Strategic (Contraintes)        |
| **People** (StakeholderRole) | **qui joue quel rôle**                        | contact ou département                                                | People (structure les rôles)                             |
| **Next Step**                | action à entreprendre                         | —                                                                     | crée activités / acteurs                                 |

### 11.2 Attribution « concerné » — pas un nouveau concept

`scope_level` (enum existant) dit le **niveau** (BUSINESS / DEPARTMENT / PERSONAL). Le **quel département** précis est un FK : présent sur Objective (`target_department`), **à ajouter sur Pain et Impact** pour qu'au niveau DEPARTMENT on sache lequel. On ne crée aucun concept nouveau — on généralise le mécanisme existant. **Source (qui parle) =/= concerné (le sujet)** : le DSI peut parler d'un pain du Marketing -> le pain remonte sous Marketing, pas IT. La source reste dérivée de `source_activity.contacts`. Contact précis = V2.

### 11.3 Concurrent — pas de modèle séparé

Géré par **TechStackSignal + `TechCatalog.is_competitor`** (le flag existe déjà). La distinction account vs deal passe par **réactiver `decision_cycle`** (shadow-override `= None` à lever) : `decision_cycle` null = outil en place / incumbent (account-level) ; non-null = concurrent en lice sur ce DC. Le catalogue porte aussi `is_integration_target` (obligation d'intégration). Pas de `CompetitorSignal` ni `CompetitorCatalog`.

### 11.4 Metric = Contrainte

Le **M de MEDDPICC** (critère de décision d'un acteur) n'est pas un type ni un champ nouveau : il est **logé dans le ConstraintSignal** (FK département, `rigidity`). Contrainte _ferme_ = critère non-négociable (« ROI > 20% ») ; _flexible_ = préférence (« idéalement avant Q3 »). C'est le « code de décision » d'un acteur process, affiché dans People.

### 11.5 Résistance = humaine

Le Frein porte une attribution **acteur** (contact/département). Un business n'a pas peur ; une personne a peur. Plus de frein « business abstrait ».

### 11.6 human_impact = self-report uniquement

`human_impact` (frustration / overload / stress...) n'est capturé **que si la personne parle d'elle-même**. Sinon, pas de dimension human (élimine le hearsay à la source). Le levier « mobiliser un acteur via son impact perso » -> V2 (dépend du ciblage contact).

### 11.7 Lifecycle (rappel)

PENDING -> VALIDATED / REJECTED (+ ARCHIVED en V2 : vrai mais obsolète, distinct de REJECTED = faux).

---

## 12. Règles QA

1. **Info non capturée =/= fausse** : « Preuves manquantes », jamais « Faible / Absent / Non prioritaire ».
2. **Niveau de preuve différencié selon la source** (V2 : niveaux fins ; MVP : signal validé vs contexte manuel).
3. **La vue Strategic indique toujours son périmètre** : « Basé sur les preuves capturées ».
4. **Discovery Gaps = zones à clarifier, jamais erreurs du commercial.** Ton neutre.
5. **Vue principale = essentiel ; détails en drill-down.**
6. **Aucun terme interne (DRI...) en UI.**
7. **Détail de la qualif montré une seule fois (Themes) ; People résume + ajoute sa couche exclusive.**

---

## 13. Chantier de nommage UI

| Nom interne         | Statut             | Libellé UI                                                   |
| ------------------- | ------------------ | ------------------------------------------------------------ |
| DRI                 | ne jamais afficher | à définir (« Leviers stratégiques » / « Angles d'approche ») |
| Deal Health         | OK interne         | à confirmer (« Diagnostic » / « État du deal »)              |
| Discovery Gaps      | semi-OK            | à confirmer (« À clarifier »)                                |
| 7 dimensions        | sales-friendly     | OK                                                           |
| Contrainte / Metric | OK                 | « Critères de décision » côté acteur process                 |
| Themes              | OK                 | « Thématiques » / « Sujets »                                 |

---

## 14. Composants frontend

### À créer

`DecisionCycleList`, `DecisionCycleCard` (Account) - `DCWorkspace`, `DCWorkspaceHeader`, `DCTabs` - `DCPeopleTab`, `DepartmentStakeholderBlock`, `RoleFilterBar`, `StakeholderActorCard` (rôle + résumé qualif OU critères/contraintes selon rôle + résistances + activités) - `DCProductsTab`, `DealProductRow` - `DCStrategicTab`, `StrategicEmptyState`, `DealHealthView`, `EvidenceCoverageBar`, `DiagnosticGlobalCard`, `MaturityDimensionList`, `MaturityDimensionDrawer`, `StrategicLeversCard`, `DiscoveryGapsCard`, `SnapshotMiniHistory`, `ThemesView` - `DCSignalsTab` - hooks `useDealHealth`, `useDealHealthRunner`, `useDCStakeholders`, `useReadinessScore`.

### À modifier

`DecisionCycleTab.jsx` -> remplacé par `DecisionCycleList` ; timeline migre dans l'onglet Timeline + critères de step accessibles par en-tête de colonne. `SignalDetailCard` partagé. Cluster thématique rendu réutilisable scopé DC.

### Stack

Next.js App Router, JSX, MUI + `@ant-design/icons`, Formik+Yup, SWR+axios, PropTypes. Références : `views/businessData/accounts/`, `sections/businessData/accounts/`.

---

## 15. Endpoints API

### Réutiliser

`GET decision_cycles/by-account/{id}/` - `GET decision_cycles/{id}/` - `POST decision_cycles/{id}/close/` - `GET module-signals/...?decision_cycle={id}`.

### Créer

`POST module-ai-pipelines/deal-health/run/` - `GET module-ai-pipelines/deal-health/by-cycle/{id}/` - `GET decision_cycles/{id}/readiness/` - `GET decision_cycles/{id}/stakeholders/` (acteurs par département + rôles + résumé/critères/résistances) - `POST decision_cycles/{id}/stakeholders/` (assignation rôle) - `GET decision_cycles/{id}/products/` + CRUD - `GET decision_cycles/{id}/themes/` - `POST decision_cycles/{id}/context/` (V2).

### Cache

Tags `SIGNALS_CACHE_TAG`, `SIGNAL_CLUSTERS_CACHE_TAG`. Ajouter : cache du dernier snapshot par DC, invalidé sur run ou changement de signal validé du DC.

---

## 16. Modélisation backend à prévoir

| Objet                                        | Nature         | Décision                                            |
| -------------------------------------------- | -------------- | --------------------------------------------------- |
| `DealHealthSnapshot`                         | nouveau        | snapshot daté. Vote : modèle dédié.                 |
| `DealStakeholder`                            | nouveau        | `(dc, contact_ou_department, role, influence)`.     |
| `PeopleSignal` (StakeholderRole)             | nouveau type   | rôle MEDDPICC + influence + attribution.            |
| `ConstraintSignal`                           | nouveau type   | règles + Metric ; `target_department` + `rigidity`. |
| `DealProduct` + `ProductCatalog`             | nouveaux       | produits x volume.                                  |
| Pain / Impact — `target_department`          | extension      | FK département (comme Objective).                   |
| TechStack — réactiver `decision_cycle`       | modif          | lever le shadow-override `= None`.                  |
| Signal — `evidence_strength` / `source_type` | extension (V2) | contexte manuel.                                    |
| `SignalStatus` — `ARCHIVED`                  | extension      | vrai mais obsolète.                                 |
| Frein — attribution acteur                   | extension      | rattacher à contact/département.                    |

---

## 17. Périmètre MVP vs V2

**MVP** : liste DC cards + nav ; DC Workspace 5 onglets ; bandeau ; Timeline (+ critères de step) ; People (par département, rôles MEDDPICC filtrables, affichage conditionnel, résumé qualif + critères/contraintes + résistances, connexion activités) ; Products & Financial ; Strategic (Deal Health + Themes, état vide + CTA) ; Signals ; pipeline deal-health (Evidence Pack) ; readiness score ; nouveaux signaux People + Contrainte ; `target_department` sur Pain/Impact ; concurrent via TechStack ; règles QA.

**V2** : `DealContextNote` + module Add context riche ; niveaux de preuve fins en UI ; `internal_follow_up_context` exploité par Prep Call ; bouton « Add to next prep » ; attribution **contact** précis (ciblage personne) ; diagnostic par stakeholder ; levier impact perso ciblé ; `ARCHIVED`.

---

## 18. Ce qui distingue notre approche

- **Trois vues, trois niveaux, une matière** : Themes (problème), People (gens), Deal Health (deal). Le détail n'est montré qu'une fois.
- **Diagnostic PUIS leviers** — les analyses de maturité classiques s'arrêtent au diagnostic.
- **Honnêteté épistémique** — _Preuves manquantes =/= Faible_ ; basé sur les preuves capturées.
- **Sales-friendly** — dimensions formulées comme un AE pense ; aucun terme interne en UI.
- **People = combinaison par acteur** — chaque persona a son code ; le Prep Call le restitue à chaque étape.
- **Pas un forecast.**

---

## 19. Diagramme de flux

```
   Liste DC (Account) -- click --> DC WORKSPACE (bandeau d'identite)
                                          |
   +----------+---------------+-----------+-----------+--------------+
   v          v               v           v           v              v
Timeline    People        Products    Strategic     Signals      (Prep Call,
(activites  (acteurs:    &Financial   (Deal Health  (a plat)       moteur futur
+ criteres  role, code,               + Themes)                   croise les 3)
 de step)   resistances)                  |
                                +---------+----------+
                                v                    v
                      sans run: vide+CTA      apres run: diagnostic
                      + Readiness             7 dims + leviers + gaps
                                                       |
                                          pipeline deal-health
                                          (signaux valides + transcripts
                                           + contexte + snapshot precedent)
                                                       |
                                              snapshot date + historique

   MEME MATIERE (signaux) --+-- pivot SUJET  -> Themes (detail)
                            +-- pivot ACTEUR -> People (resume + couche exclusive)
```

---

_Fin du rapport v2. Base de référence pour l'implémentation du Decision Cycle Workspace._
