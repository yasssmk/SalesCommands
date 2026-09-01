# SalesCommands — Roadmap

## Vision produit
SalesCommands est une plateforme SaaS B2B multi-tenant d'ORGANISATION
commerciale (pas un remplacement de CRM). Elle aide SDR, AE et Managers à
voir et organiser tout le nécessaire pour atteindre leurs objectifs.

Stratégie en trois temps :
1. **Aujourd'hui — outil dirigé par l'utilisateur.** Ressemble aux CRM/
   outils classiques que les utilisateurs connaissent : ils dirigent
   l'interface, saisissent la donnée. Pas d'IA pure. Objectif : adoption.
2. **Moyen terme — corpus.** Pendant l'usage, on accumule une base propre
   de tous les cycles de vente, campagnes, résultats, décisions.
3. **Terme — agents.** Des agents entraînés sur ce corpus : agent de
   campagne (séquence, email, appel), agent de cycle de vente
   (accompagnement de A à Z, provoquer une démo).

**Conséquence directe (réflexe permanent) :** la donnée saisie aujourd'hui
est le carburant des agents de demain. À chaque feature touchant de la
donnée commerciale, se poser la question "training-readiness" : cette
donnée, telle que structurée, permettra-t-elle à un agent d'apprendre le
bon comportement plus tard ? Ne pas perdre de donnée exploitable (capturer
résultats et causalité), sans sur-structurer pour un usage hypothétique.

## Principes transverses (appliqués à chaque sprint)
- **Audit d'abord** : avant tout code, auditer l'existant. Ne rien
  supposer ("NE SUPPOSE RIEN").
- **Citer l'existant avant de coder** : ouvrir le fichier de référence, le
  citer, mesurer l'écart, PUIS coder. Ne pas réinventer un pattern qui
  existe.
- **Ne rien extrapoler** : la référence (existant, capture, instruction PO)
  prime sur le raisonnement de cohérence. Pas de mécanique non demandée.
- **Un défaut / une feature = un commit**, validé (tests + smoke à l'écran)
  avant d'avancer.
- **Repro rouge d'abord** pour les corrections de bug.
- **Q6** : jamais d'écriture dans un GET.
- **UI psychologique** : s'assurer que la solution EXHORTE l'utilisateur à
  agir. Cadrer pour l'action ("X to go", proximité du but), célébrer
  l'over-achievement, éviter le décourageant ("0% done", totaux froids).
  Principe issu de la Home (framing 'queue'), à appliquer partout.

---

## Sprints livrés

### S0 → S5 ✅ — Fondations jusqu'à la Home BI
Fondations, architecture modulaire, permissions, module BI, Home rep +
manager (fenêtres glissantes overdue/today/7j/4s), API BI scope-bornée.

### S6 ✅ — Régression campagne (TD-89) + mécanique callback
- **Objectif** : réparer TD-89 (activités de séquence campagne ne
  remontant plus dans le todo).
- **Problématique** : régression révélant une mécanique callback entière
  jamais testée (4 défauts empilés).
- **Solution** : clamp date campagne en lecture (jamais overdue),
  résolution du statut au log du callback, chip + teinte visuels, cards
  completed correctes, date locale, renumérotation de position, séquences
  réelles activées, titres structurés, date callback éditable.
- **Validation** : boucle callback complète sur données réelles (création
  → chip → résolution → reprise chaîne), 230 tests backend + 486 frontend
  verts.

### S7a ✅ — Vues de travail (partie 1)
- **Objectif** : deux vues neuves en Business Data + nettoyage menu.
- **Problématique** : pas de vue liste des Decision Cycles ; Product absent ;
  menu encombré (Dashboard, Action Center vide, Contact).
- **Solution** : vue Product (CRUD, patron Tech Catalogue), vue Decision
  Cycles (lecture seule, colonnes riches via KPI dc_cycle_state, filtres
  drawer), suppression Dashboard/Action Center/Contact-list (entité Contact
  partagée préservée), retrait import mort Tech Catalogue.
- **Validation** : les deux vues à l'écran (CRUD Product, filtres/navigation
  DC), non-régression onglet Contacts du workspace compte, vitest vert.

### S7d ✅ — Navigation du bloc progression de la Home
- **Objectif** : rendre le bloc « My Progress » de la Home lisible et
  navigable. Séparé de S7c (décision PO) : ici la NAVIGATION du bloc
  progression, pas les filtres de la liste DC.
- **Livré** (PR #86, #87, #88) :
  - Gate de chargement couvrant toute la phase : le squelette ne laisse plus
    passer un flash d'état vide.
  - Hauteur de ligne constante sur `GoalProgressRow` (barre en
    `visibility:hidden` en mode `empty`).
  - Tri des campagnes : échéance la plus proche d'abord, puis progression
    croissante à date égale ; tri territoires (moins couvert d'abord)
    inchangé.
  - Cap de 5 lignes et hauteur réservée de 5 lignes sur les 4 cartes (rep et
    manager), la ligne globale « All teams » comptant dans les 5 côté
    manager.
  - « See all » permanent et symétrique sur les 4 cartes →
    `/campaigns?status=ACTIVE` et `/territories` ; libellé « See all (N) » qui
    retombe sur « See all » nu quand le total est inconnu (chargement, 0
    entité) plutôt qu'un « (0) » trompeur.
  - Noms de ligne cliquables côté REP uniquement (campagne →
    `/campaigns/{id}`, territoire → `/territories/{id}`) ; les lignes manager
    restent non cliquables, une ligne étant une équipe agrégée et non un
    objet.
  - `/campaigns` lit `?status=<VALEUR>` validée contre `CAMPAIGN_STATUSES` ;
    l'URL amorce, l'état local prime ensuite.
  - Primitives partagées (`PROGRESS_TOP_N`, `RowsZone`, `SeeAll`) exportées
    par `ProgressBlock` et consommées par `TeamAggregateBlock` — une seule
    implémentation de la règle.

### S8a ✅ — Branchement du suivi des objectifs de campagne (partiel)
- **Objectif** : brancher l'AVANCEMENT réel des objectifs de campagne. Partie
  du sprint S8 ; le reste (UI de DÉFINITION des quotas/objectifs +
  over-achievement) reste planifié en S8.
- **Livré** (PR #96) :
  - **Avancement sur la carte** : `current_value` + `progress_percentage`
    exposés sur le serializer de LISTE (carte campagne), plus seulement sur le
    détail — la barre de la carte reflète l'avancement RÉEL.
  - **Attribution unifiée par ORIGINE campagne** :
    - `DECISION_CYCLES` / `PIPELINE_VALUE` / `REVENUE_WON` attribués via
      `DecisionCycle.source_campaign` (au lieu de `Activity.campaign`, jamais
      posé par la modale).
    - `MEETINGS` attribué par UNION de trois origines :
      `cycle.source_campaign` OU `Activity.campaign` OU
      `source_activity.campaign` (ce dernier capte les meetings créés sur un DC
      PRÉEXISTANT depuis une séquence de campagne).
  - **Règle produit actée** : les métriques d'ACTIVITÉ (`MEETINGS`) comptent
    une activité issue de la campagne peu importe que son DC soit nouveau ou
    existant ; les métriques de CYCLE (`DECISION_CYCLES`) ne comptent un DC que
    s'il est NOUVEAU et attribué par son propre `source_campaign`. Un DC
    préexistant ne compte JAMAIS comme nouveau.
  - **Définition `MEETINGS`** : « tenu » (status `COMPLETED`), pas « booké ».
    Vaut aussi pour le quota personnel `MEETINGS` — une seule définition
    partout.
  - **`CONTACTS_REACHED`** : retiré des objectifs de campagne (décision
    produit) ; son calcul reste utilisé pour l'avancement PROPRE de la
    campagne, pas comme objectif assignable.
- **Reporté à Sprint C** : `PIPELINE_VALUE` et `REVENUE_WON` (objectifs de
  campagne ET quotas personnels) restent à 0 tant que le montant n'est pas
  réconcilié — voir Sprint C et TD-75.

### Sprint build-health frontend ✅ — TD-18 résolu (PR #102)
- **Objectif** : rétablir `next build` (garde build cassée depuis F1,
  ré-escaladée BLOQUANT au sprint campagne).
- **Trouvé** : le build échouait sur LES DEUX environnements, pour deux causes
  qui se masquaient — Linux (CC) : `react-csv` / `@dnd-kit/core` non résolus,
  arrêt AVANT ESLint ; macOS (PO) : 5 erreurs `react-hooks/rules-of-hooks`.
  Cause aggravante : un `node_modules` PARASITE à la racine du repo résolvait
  des paquets fantômes (dont `@mui/x-tree-view` v8) — le diagnostic initial
  « divergence d'environnement » était donc FAUX.
- **Corrigé** (4 commits) : deps déclarées (`react-csv`, `@dnd-kit/core`,
  `prop-types`), `@mui/x-tree-view` `^6`→`^8` (API `RichTreeView`), 4 casses
  d'import (`businessData`, `UserCSVValidation`), `useGetTeam` re-source
  (`api/admin/teams`), 5 faux-hooks renommés — AUCUNE règle ESLint désactivée,
  aucun fichier renommé, `node_modules` parasite sorti du projet.
- **Validation** : `next build` exit 0 (23 routes) ; 728 tests vitest
  (= baseline) ; pytest inchangé ; build + smoke validés en local par le PO.
- **Part en dette** : neuf constats frontend cartographiés — TD-132 (hook
  `useGetOrganization` manquant), TD-133 (paquets non déclarés à consommateurs
  orphelins), TD-134 (imports morts en code non atteignable), TD-135
  (`DecisionStepDetail` orphelin — à élucider avant Sprint B), TD-136
  (`UserCSVImportModalOLD` mort), TD-137 (nommage `UserCSVValidation`), TD-138
  (reproductibilité d'env → G2), TD-139 (garde build faible → CI à G2), TD-140
  (backlog ESLint).
- **Enseignement de méthode** : trois audits read-only successifs ont été
  nécessaires — chaque passe révélait que le diagnostic précédent était
  incomplet — et c'est le test du PO sur SA machine qui a révélé la moitié
  manquante du problème (les 5 erreurs ESLint masquées côté Linux). Le build
  seul est une garde faible : sur 12 défauts cartographiés, `next build` n'en a
  surfacé que 2 (voir TD-139).

### Sprint ✅ — Ne plus jamais effacer d'activités (PR #104, 2026-08-03)
- **Objectif** : une règle UNIQUE sur les trois chemins de fin de vie
  campagne/territoire — on ne supprime plus jamais une activité, on la préserve.
- **Livré** : filtre IDENTIQUE partout — `status__in=[PLANNED, ON_HOLD]` +
  `decision_cycle__isnull=True` → `.update(status=CANCELLED)`, JAMAIS un
  `.delete()` d'activité. Une activité liée à un DecisionCycle n'est jamais
  touchée ; les terminées (COMPLETED/CANCELLED) sont gardées ; toutes sont
  détachées automatiquement (SET_NULL sur `campaign` / `campaign_account` /
  `campaign_contact`) quand la campagne est supprimée. Trois chemins :
  annulation de campagne (`campaign_lifecycle_service._cancel_planned_activities`,
  campagne vivante), suppression de campagne (`campaign_views.destroy` +
  `campaign_bulk_views.bulk_delete`), cascade territoire
  (`territories/views.views._cascade_delete_outbound_campaign`). 4 fichiers de
  prod modifiés.
- **Précision de règle** : sur les TROIS chemins l'activité prévue non-deal est
  ANNULÉE (jamais supprimée) ; la seule différence est que la campagne, elle,
  est détruite (suppression/cascade) ou reste vivante (annulation). La lecture
  « prévues non-deal supprimées sur suppression/cascade » serait donc inexacte.
- **Validation** : 3 fichiers de tests neufs — `test_cancel_keeps_activities.py`,
  `test_delete_keeps_activities.py`, `test_cascade_keeps_activities.py`.
- **Part en dette** : `delete_activities_for_contact` (retrait manuel d'un
  contact d'une campagne) N'A PAS été aligné — il supprime encore les activités
  PLANNED. Nouvelle dette **TD-141**.

### Sprint ✅ — Owner obligatoire sur les deals (PR #106, 2026-08-04)
- **Objectif** : garantir un `owner` sur tout DecisionCycle, quel que soit le
  chemin de création.
- **Livré** : `owner = créateur` posé aux TROIS endroits —
  fabrication du DC (`activity_creation_service.py`), garde du serializer
  (`decision_cycles/serializers.py`, refuse l'anonyme + force `owner=user` en
  `create()`), et filet au `save()` (`decision_cycles/models.py`, fallback
  actor puis `created_by`). PAS de migration (le champ `owner` est déjà nullable,
  préexistant).
- **Rectification de prémisse** : « owner posé sur AUCUN chemin avant » est
  FAUX — le serializer `create()` posait DÉJÀ owner. Le vrai trou fermé par #106
  est le chemin de FABRICATION (`activity_creation_service`), qui créait le
  cycle sans owner. Par ailleurs un backfill EXISTE déjà (migration préexistante
  `0010_decisioncycle_owner`, `RunPython` `owner = created_by` là où
  `created_by` est non-null) : le résiduel non couvert est le DC ayant à la fois
  `owner` ET `created_by` null (données de test) — dette **TD-142**.
- **Validation** : `tests/decision_cycles/test_dc_owner_is_creator.py`.

### Sprint ✅ — Cycle de vie utilisateur (PR #105 + #107, 2026-08-04)
- **Objectif** : la suppression d'un utilisateur devient impossible ; la
  désactivation transfère son travail à un successeur.
- **Livré (composé, tout vérifié dans le code)** :
  - **Suppression user INTERDITE inconditionnellement** — refus au `destroy`
    individuel (`_validate_user_deletion`), filet `ProtectedError` capturé, ET
    refus sur le `bulk_delete` ; le message oriente vers la désactivation.
  - **Désactivation → transfert atomique à un SUCCESSEUR** (actif, même tenant,
    ≠ la personne), dans UNE `transaction.atomic` (`partial_update`) : deals
    non terminaux, comptes de TOUT type, activités non terminées liées à un deal.
  - **Campagnes** : OUTBOUND annulées ; TARGETED vidée ; activités libres non
    terminées annulées.
  - **Annulation de campagne (manuelle OU via désactivation)** → contacts non
    terminaux (PENDING, IN_PROGRESS, ON_HOLD, CALLBACK_PENDING) → STOPPED ;
    terminaux (COMPLETED, STOPPED) épargnés (chemin partagé
    `CampaignLifecycleService.cancel` → `_stop_remaining_contacts`).
  - **Team d'un compte dérivée de l'owner** (property, non stockée) → suit
    automatiquement au transfert.
  - **Fenêtre de désactivation** front (`DeactivateUserDialog.jsx` +
    `SuccessorPicker.jsx`) avec sélecteur de successeur + récap des compteurs.
  - **Manager d'équipe NON modifié** (choix produit : une équipe peut rester
    sans manager).
  - **Réactivation ne restaure rien** (simple `partial_update`, la garde ne se
    déclenche qu'à la bascule actif→inactif).
- **Attribution** : #105 = la feature (backend + frontend, aucune migration) ;
  #107 = deux correctifs backend (transfert des comptes de TOUS types au lieu de
  PROSPECT-only ; l'annulation de campagne stoppe désormais les contacts).
- **Validation** : `tests/integration/end_users/test_perm.py`
  (`test_delete_refused_*`, `test_bulk_delete_refused`, transferts).
- **Ferme une dette** : **TD-35** (suppression user vs `Campaign.owner` PROTECT
  → 500) — la suppression étant désormais interdite et le `ProtectedError`
  capturé, le crash 500 disparaît ; les anciens tests `test_delete_only_admin_`
  `allowed` / `test_delete_superuser_allowed` sont remplacés par les tests
  « refused » (voir TD-35 / TD-77 mis à jour).

### Sprint ✅ — Alignement des tests d'activité (PR #108, 2026-08-04)
- **Objectif** : aligner les 3 tests portant l'ancienne règle « on supprime les
  activités » sur la règle actuelle (préservation).
- **Livré** : 2 fichiers de tests, 3 méthodes — 1 doublon retiré
  (`test_campaign_bulk_delete.py::test_linked_activities_are_deleted_not_`
  `orphaned`), 2 assertions corrigées dans
  `test_delete_conditional.py`. AUCUN code de prod touché (git `--stat` = 2
  fichiers sous `backend/tests/`).
- **Validation** : fichiers ciblés verts ; coexistence avec les tests récents de
  préservation confirmée.

### Sprint ✅ — Socle d'enrôlement : joignabilité source unique (PR #110, #112, #113)
- **Objectif** : une SEULE source de vérité pour la joignabilité d'un contact
  (email / téléphone / LinkedIn) à l'enrôlement, avec un feedback honnête.
- **Livré** : joignabilité calculée en un point unique (#110) ; opt-out VISIBLE
  (#112) ; compteurs de CAUSE (injoignable, déjà actif, opt-out) + messages
  d'enrôlement précis (#113) ; feedback ORANGE (warning) pour une règle métier —
  jamais du rouge d'erreur. Skip-and-enroll-rest : les injoignables sont comptés
  et remontés, les joignables enrôlés (cf. TD-144, qui écarte le mythe d'un
  « échec en bloc »).
- **Validation** : smoke PO sur les deux modales.

### Sprint ✅ — Séquences LinkedIn (PR #111, #114)
- **Objectif** : débloquer les contacts LinkedIn-only et offrir une séquence
  100 % LinkedIn.
- **Livré** : canal LinkedIn à l'enrôlement (#111) ; fix `has_linkedin` — les
  contacts `WITHOUT_EMAIL` mais avec LinkedIn ne sont plus écartés — et variante
  de séquence `LINKEDIN_ONLY` (#114).
- **Validation** : enrôlement d'un contact LinkedIn-only → séquence LinkedIn.

### Sprint ✅ — Mode « No calls » (campagne + par contact) (PR #115, #117)
- **Objectif** : mener une campagne sans appels (email OU LinkedIn).
- **Livré** : au niveau CAMPAGNE, renommage `EMAIL_ONLY` → `NO_CALLS` (le canal
  couvre désormais email OU LinkedIn, plus seulement email) — le chip carte
  « Email only » (S8a) devient « No calls » (#115) ; au niveau CONTACT, override
  `CampaignContact.channel_override` avec toggle « Add to Target » (#117).
- **Validation** : campagne NO_CALLS + override par contact vérifiés à l'écran.

### Sprint ✅ — Fix collisions d'unicité email/téléphone vides (PR #116)
- **Objectif** : empêcher les collisions d'unicité sur email/téléphone VIDES.
- **Livré** : normalisation `'' → NULL` dans `Contact.save()` (+ migration) →
  plusieurs contacts sans email ne se heurtent plus sur la chaîne vide ; les
  `IntegrityError` restantes sont gérées proprement par le handler d'erreur
  standard. LinkedIn n'a PAS de contrainte d'unicité → non concerné (voir
  TD-149).
- **Validation** : création de contacts sans email/téléphone sans collision.

### Sprint ✅ — Campagne inactive (PR #118)
- **Objectif** : signaler visuellement une campagne devenue inactive.
- **Livré** : `Campaign.is_inactive` calculé au READ-TIME (annotation queryset,
  anti-N+1), seuil `N_INACTIVE_DAYS` dans `campaigns/constants.py`, chip
  « Inactive » + surbrillance sur la carte de liste, bannière sur l'onglet
  playlist. S'applique à TOUS les types, y compris Targeted. NB : l'annotation
  sur l'endpoint de DÉTAIL a nécessité un override `get_object` (voir TD-146).
- **Validation** : test page-level (#118) + smoke PO.

> **Module Campagne : CLOS** — enrôlement, canaux (email/téléphone/LinkedIn),
> mode No calls, intégrité contacts et signal d'inactivité livrés et mergés.

---

### Sprint S13 ✅ — Intention & Prep Call (branche `feat/s13-activity-objective`)
- **Objectif** : attacher un OBJECTIF à chaque activité (source d'intention pour
  les futures fonctions IA) et absorber le ciblage/sélection des contacts.
- **Livré** :
  - **Objectif unifié** porté par `Activity.call_to_action`, affiché « Activity
    Objective ». Sources : **OUTBOUND** ← nouveau champ `Campaign.activity_objective`
    (optionnel), propagé à la génération des activités ; **TARGETED** ← nouveau
    champ `CampaignContact.objective` saisi à l'enrôlement, **JETABLE par run**
    (réinitialisé par `reactivate()`) ; **DC** ← natif (saisie manuelle +
    `NextStepSignal.suggested_objective` mappé à la matérialisation Signal→Activity,
    l'objectif explicite du payload primant ; le prompt qui remplira
    `suggested_objective` reste HORS SCOPE, sprint signaux).
  - **Ciblage OUTBOUND par départements au niveau CAMPAGNE** (nouveau M2M
    `Campaign.target_departments` → `StandardDepartment`) ; filtre appliqué à la
    **CRÉATION** (`_enroll_from_territories`) **ET** à la **GÉNÉRATION**
    (`_extract_contacts`) — les DEUX points, sinon la génération ré-enrôle les
    contacts filtrés (no-op pour TARGETED).
  - **TARGETED = enrôlement contact par contact uniquement** ; mode **ACCOUNT
    retiré** (front `AddToCampaignModal` + branche backend `enroll_target`, rejet
    4xx propre) ; mode **DEPARTMENT conservé** comme FILTRE client-side (jamais un
    mode backend).
  - **Ferme TD-145** : le CTA ne lit plus `campaign_account.notes` → le texte de
    journal de statut (« Account stopped… ») ne peut plus fuiter dans une activité
    active.
  - **Placeholders** objectif/description orientés « AI recommendations », deux
    variantes (activité : « …of this activity… » ; campagne : sans « this
    activity »).
- **Migrations** (schema-only, nullable, sans backfill) : `Campaign.activity_objective`
  (0018), `CampaignContact.objective` (0019), `Campaign.target_departments` M2M
  (0020), `NextStepSignal.suggested_objective` (0022).
- **Validation** : backend `tests/campaigns` + `tests/activities` + `tests/signals`
  verts (Postgres) ; frontend vitest 788 tests verts ; smoke PO à venir.
- **Dette ajoutée** : TD-163 (multi-select départements `FormTerritoryEdit` cassé),
  TD-164 (label/placeholder hard-codés, pas d'i18n), TD-165 (`MultiSelectFilter`
  propTypes).

---

### Sprint S10 ✅ — Suppression du catalogue tech + signal tech autoporté (branche `feat/s10-techstack-signal`)
- **Objectif** : RETIRER le modèle de catalogue tech et accepter tout signal tech
  TEL QUEL, avec le mécanisme anti-doublon LE PLUS SIMPLE POSSIBLE + un filtrage
  par technologie.
- **Livré** :
  - **Catalogue tech SUPPRIMÉ** : modèle `TechCatalog` + table + données, CRUD
    back (viewset / serializers / urls / registry permissions / feature flag) et
    front (route, vue liste, modale, formulaires add/edit/delete, API layer,
    `AsyncTechCatalogSelect`), et le **workflow admin de validation** (émetteur
    E4 « tech inconnue », endpoint `/tech-stack/detected/`, catégorie
    `UNKNOWN_TECH_DETECTED`).
  - **Le signal tech porte désormais son identité** : `tech_name` (brut, tel
    qu'écrit — affichage) + `tech_name_normalized` (INDEXÉ, clé de
    regroupement / filtre / dédup, DÉRIVÉE au `save()` par lower + trim +
    collapse des espaces internes). `tech_name` est la source de vérité unique :
    la colonne normalisée est recalculée à chaque écriture, les deux ne peuvent
    pas désynchroniser. `save()` est le point de normalisation UNIQUE (pipeline,
    API REST, shell, commande de management passent tous par là).
  - **3 booléens INDÉPENDANTS** : `is_competitor` / `is_integration` /
    `is_to_replace`. Toutes les combinaisons sont valides ;
    **false/false/false = techno simplement utilisée** (cas courant, pas une
    anomalie). Les métadonnées par compte sont CONSERVÉES intactes (usage_scope,
    département, année de début, renouvellement, coût, discontinuation, notes).
  - **Extraction transcript REFONDUE** : le LLM sort `tech_name` + les 3
    booléens ; le XOR `tech_catalog_entry_id` / `tech_name_raw` (match catalogue
    par UUID) est supprimé, ainsi que l'injection du catalogue tenant dans le
    prompt. Dédup de batch repointée sur le NOM NORMALISÉ (via le helper du
    modèle, réutilisé — pas ré-implémenté). Effet de bord : la surface
    d'attaque cross-tenant disparaît avec l'UUID (plus aucun identifiant tenant
    envoyé au modèle ni relu de lui sur ce chemin).
  - **Packs IA repointés** (deal-health + prep-call) sur `tech_name` + booléens ;
    ils lisaient la FK catalogue et sortaient `None` / `False` depuis la refonte
    d'extraction. Bucket **`to_replace`** ajouté au contexte concurrentiel prep-call,
    **chevauchant et non partitionnant** : un outil que le compte veut quitter est
    une porte ouverte, qu'on le concurrence ou non.
  - **Filtre `has_tech_stack` repointé** sur `tech_name_normalized` (match exact
    sur la forme normalisée, entrée normalisée par le même helper, sémantique
    liste/OR conservée, entrée blanche = PAS de filtre). Ferme TD-61 — et la
    dette était sous-évaluée : le filtre ne « ne matchait rien », il **levait**
    (`bigint = uuid`), donc renvoyait un 500.
  - **`PainSignal.related_techstack` (FK) supprimée** ; `related_techstack_mention`
    (texte libre) CONSERVÉE — le lien Pain↔outil survit comme la trace textuelle
    qu'il a toujours été.
- **Migrations** : `module_signals/0024` (retrait des 2 FK + 3 index, dont
  l'index inert `tssig_account_canon_idx`), `tech_catalog/0002`
  (`DeleteModel`, dépendant de `0024` pour que les FK `PROTECT` tombent AVANT
  la table), `notifications/0004` (retrait de la catégorie E4).
- **Validation** : suites backend vertes (531 au dernier run PO) ; front vitest
  796 tests verts ; `next build` sans import non résolu.
- **Dette fermée** : TD-61, TD-62, TD-63, TD-67. **TD-60 reste OPEN** —
  l'endpoint mort `/company-accounts/<id>/tech-stacks/` n'a PAS été touché par
  S10 (vérifié sur la branche : route, action et appel `get_tech_stacks_data`
  toujours présents). **Dette ajoutée** : TD-166 (`tech_catalog` gardé en app
  migrations-only), TD-167 (commentaires front de filiation obsolètes).
- **⏸️ REPORTÉ — à NE PAS considérer comme livré** :
  - **Wording de qualification par booléen dans les prompts** — délibérément
    hors périmètre S10 (le sprint a posé le SCHÉMA de sortie, pas la pédagogie).
    Ancres `TODO(S10→AI-sprint)` laissées dans
    `prompts/transcript_signals/techstack_v1.py` (définitions par booléen,
    distinction PASSÉ/FUTUR pour `is_to_replace`, few-shots) et
    `prompts/transcript_signals/context.py` (données de grounding éventuelles).
    **Jusque-là le LLM SOUS-REMPLIRA les booléens** — mode d'échec choisi :
    un rep coche une case, alors qu'un faux « concurrent » oriente mal le deal.
    → **Bloc « Commandes IA » (#4)**.
  - **Affichage** : liste des technologies au niveau COMPTE + concurrents /
    intégrations au niveau DC. → **Sprints UI signaux / DC**.
  - **UI du filtre par technologie** (le backend filtre, rien ne le pilote
    depuis l'interface). → **Sprint Filtres & recherche transverses**.
  - **Regroupement / UI de cluster pour l'affichage des signaux tech** — écarté
    par le PO au cadrage S10. Le mécanisme anti-doublon tech est INDÉPENDANT des
    clusters pain / impact / objectif : TechStack n'a PAS de `canonical_key` et
    n'est pas servi par `SignalClusterService`. → **Sprint UI signaux**.
  - **SMOKE TRANSVERSE de la chaîne tech** (extraction → qualification →
    affichage compte/DC → filtre), à exécuter une fois Commandes IA + DC +
    Filtres livrés. **S10 n'est pas smoquable seul** : ses débouchés visibles
    vivent dans ces sprints.
- **Prochain jalon** (ordre cible) : **Bloc « Modèle Decision Cycle » (#3)**.

---

### Sprint C ✅ — Produit & Finance de bout en bout (branche `feat/sprint-c-product-finance`)
- **Objectif** : rendre le MONTANT d'un deal FIABLE et UNIQUE. Avant ce sprint,
  les quatre KPI monétaires sommaient `DecisionCycle.estimated_value`, un champ
  MANUEL qu'aucun chemin runtime ne remplit (TD-75) → pipeline et résultat
  affichaient **0**, et la colonne « Amount » de la liste DC affichait un tiret
  sur chaque ligne. Le montant devait devenir **dérivé** des lignes produit,
  calculé en base, et lu par TOUS les consommateurs sans qu'aucun ne redéclare
  la formule.
- **Livré** :
  - **Source unique du montant dérivé** — `backend/app_modules/decision_cycles/services/deal_value_sql.py`
    déclare la formule UNE fois (`quantité × prix unitaire × (1 − remise/100)`)
    et l'expose sous **deux liaisons** de la même expression : `DEAL_VALUE_SUM`
    (forme jointe, pour `.aggregate()`) et `annotate_deal_value()` / `deal_value_subquery()`
    (sous-requête corrélée isolée, pour l'annotation par ligne, alias
    `_deal_value`) — la seconde évite le fan-out qu'une jointure to-many
    provoquerait sur une liste. `DecisionCycle.total_deal_value` lit l'annotation
    si elle est là, sinon fait UNE requête (`fb105d1`, `f6cb869d`).
    `line_total` reste une **property** calculée à la lecture : elle n'a jamais
    été une colonne stockée dans `app_modules` (aucune migration ne la déclare)
    — il n'y avait donc pas de dé-normalisation à faire, seulement à ne pas en
    introduire, ce que les tests de schéma épinglent.
  - **TD-74 — remise bornée [0, 100] aux DEUX niveaux** : `CheckConstraint`
    `deal_product_discount_percent_bounds` (intégrité, avec un `RunPython` de
    clamp ordonné AVANT l'`AddConstraint` pour les lignes existantes) +
    `validate_discount_percent_range` côté DRF, pour un **400 métier lisible**
    plutôt qu'une `IntegrityError` brute. Effet de bord découvert au passage :
    `discount_percent` était en lecture seule dans le serializer — il est
    désormais **écrivable**, donc la remise est enfin saisissable (`1327fe7`).
  - **TD-75 — repointage de TOUTES les agrégations montant** sur la valeur
    dérivée : `bi/metrics/sales_metrics.py` (`pipeline_value`, `revenue_won`),
    `bi/definitions/decision_cycles.py` (`dc_pipeline_value`, `dc_won_value`),
    `bi/quota.py`, `campaigns/services/campaign_analytics_service.py`,
    `campaigns/services/campaign_objective_progress.py`. Balayage de
    cross-couverture (TD-125) préalable : **zéro** `Sum('estimated_value')`
    subsiste dans `app_modules/` et `end_users/`. `estimated_value` n'est PAS
    supprimé — il reste dans le payload comme champ manuel legacy, simplement
    plus personne ne l'affiche ni ne le somme (`1ca74aa`, `9027342`).
  - **Convergence de la date de clôture sur `outcome_date`** : `closed_at`
    avait été ajouté (`6b9d8ad`, migration `0021`) pour fenêtrer les montants
    gagnés, puis un audit a montré qu'`outcome_date` portait DÉJÀ cette
    sémantique — le champ a été retiré par `RenameField`/`RemoveField` en avant
    seulement (`0101dd3`, migration `0022`), sans réécrire la migration déjà
    appliquée. Un seul champ de date de clôture, épinglé par
    `tests/decision_cycles/test_outcome_date_invariant.py`. **Anomalie relevée,
    non corrigée** : `ON_HOLD` pose une date de clôture alors que l'état n'est
    pas terminal.
  - **Attainment de quota personnel** (pipeline + gagné), typé, borné par la
    période et scopé par rôle, couvert de bout en bout — dont la preuve que les
    chemins PERSONNELS renvoient bien le montant attendu (`a420a26`).
  - **Devise au niveau du TENANT** : `ClientAccount.default_quota_currency` →
    `ClientAccount.currency` (la devise appartient au tenant, pas au quota qui
    l'a lue en premier), résolue en UN endroit (`backend/core/currency.py`) et
    attachée aux payloads : `unit='currency'` sur les KPI monétaires →
    `serialize_result` ajoute la devise, et `TenantCurrencySerializerMixin`
    la sert sur les listes DC / lignes produit en **mémoïsant par passe de
    sérialisation** (un N+1 introduit puis rattrapé par le garde de nombre de
    requêtes de la liste). Aucune conversion, aucun taux (`ad58aa6`).
  - **TD-127 — « Won Value » + colonne Amount vivante** : le libellé du KPI
    monétaire gagné devient explicitement une VALEUR (et non un compte), et la
    colonne Amount de la liste DC lit `total_deal_value` + la devise du tenant,
    triable sur l'alias d'annotation `_deal_value` au lieu du champ mort
    (`4cca223`). Affichage seulement — aucun filtre montant (c'est TD-124,
    sprint Filtres).
- **Migrations** : `decision_cycles/0020` (clamp + `CheckConstraint` remise),
  `decision_cycles/0021` (ajout `closed_at`) et `0022` (retrait `closed_at`,
  en avant seulement), `end_users/0013` (`default_quota_currency` → `currency`),
  `campaigns/0021`, `quotas/0002`.
- **Validation** : suites backend vertes hors échecs PRÉ-EXISTANTS prouvés tels
  en re-jouant les tests sur les commits parents dans des worktrees jetables
  (7 tests BI dépendants de Redis, 5 échecs + 10 erreurs dans
  `tests/integration/`). Front vitest vert. Chaque sous-étape a été validée par
  une reproduction ROUGE d'abord puis une sonde de NON-VACUITÉ (mutation du
  code de production → le test re-échoue → restauration par édition ciblée).
- **Dette fermée** : **TD-74** (remise bornée), **TD-75** (agrégations montant
  repointées), **TD-127** (« Won Value » + colonne Amount).
  **TD-124 reste OPEN mais DÉBLOQUÉ et REDIRIGÉ** vers le **sprint « Filtres &
  recherche transverses »** : le filtre par montant attendait un montant fiable,
  il l'a maintenant — il n'est délibérément PAS construit ici, et un test garde
  vérifie qu'aucune facette montant n'est apparue dans le filterset.
  **Dette ajoutée** : **TD-168** (défaut de devise EUR à passer en USD + sélecteur
  de devise à la création du tenant), **TD-169** (branche `pipeline` du quota
  legacy `SalesQuota` non fenêtrée, épinglée par un test), **TD-170** (plan de
  vente / milestones toujours sur les tables `opportunities_*`, avec un
  `FieldError` sur `User.client_id` en amont).
- **⏸️ REPORTÉ — à NE PAS considérer comme livré** :
  - **Filtre / recherche par montant** (TD-124) → **Sprint Filtres & recherche
    transverses**.
  - **Sélecteur de devise à la création du tenant** + bascule du défaut sur USD
    (TD-168) → **Sprint Admin Client**. `DCWorkspaceHeader.jsx:60-61` code encore
    `currency: "USD"` en dur et n'a pas été repointé sur la devise du tenant.
  - **Stockage de la durée d'abonnement et du volume d'usage** — la formule
    dérivée ne connaît aujourd'hui que quantité / prix / remise ; toute
    récurrence ou consommation reste hors modèle.
  - **Sémantique `ON_HOLD` vs date de clôture** — relevée pendant l'audit de
    convergence, non tranchée.
  - **Surfaces legacy** (`SalesQuota`, plan de vente / milestones sur
    `opportunities_*`) → nettoyage avant déploiement, TD-169 / TD-170.
- **Prochain jalon** (ordre cible) : **Bloc « Modèle Decision Cycle » (#3)**.

---

### Sprint C ✅ — Wiring / UI / métriques (branche `feat/sprint-c-wiring`)
- **Objectif** : aligner TOUTES les métriques BI — personnelles ET campagne —
  sur la table de vérité, en déclarant CHAQUE règle UNE fois. Avant ce sprint
  chaque surface répondait à une question légèrement différente sans le dire :
  le périmètre personnel variait d'un KPI à l'autre, l'attribution campagne
  existait en plusieurs implémentations divergentes, `LEADS` restait servi alors
  que le produit ne le revendiquait plus, et les cartes campagne pouvaient
  afficher un chiffre périmé pendant tout un TTL après l'action qui l'avait
  changé.
- **Livré** :
  - **Périmètre personnel unifié, déclaré une fois** —
    `backend/app_modules/bi/metrics/attribution_scope.py` répond à « de QUI est
    ce chiffre » pour toutes les métriques : union
    `owner ∪ created_by ∪ account.account_owner` (`cycle_scope_q`), sa
    transposition équipe (`…_for_teams`), et la règle CRÉATEUR
    (`creator_scope_q`) pour les métriques qui comptent un ACTE plutôt qu'une
    possession. Le périmètre COMPTE ajoute les comptes gagnés par la personne
    (`account_scope_q`). Les `Q` unions sur des FK to-one ne provoquent pas de
    fan-out ; les corrélations to-many passent par `Exists()` (`ce6193f`).
  - **`DECISION_CYCLES` = ce qu'un rep a OUVERT** — bascule sur `created_by`
    (un cycle créé, pas un cycle possédé), fenêtré sur `created_at` en
    DATETIME. **`MEETINGS`** ne compte que les rendez-vous `COMPLETED` à
    l'issue réussie, attribués au créateur, fenêtrés sur `completed_at`
    (`ce6193f`, `6d4e4eb`).
  - **`LEADS` retiré du produit** — métrique supprimée du moteur, purge des
    objectifs stockés (`quotas/0004_purge_leads_quotas`), et garde de source
    côté front vérifiant qu'aucun `LEADS` ne subsiste dans le vocabulaire
    d'objectifs (`6d4e4eb`, `83963e1`).
  - **`CONTACTS_REACHED` = une conversation a EU LIEU** — défini sur
    `REACHED_OUTCOMES` (déclaré UNE fois à côté de `SUCCESSFUL`/`TERMINAL` dans
    `campaign_execution_service.py`), la personne étant identifiée par le pivot
    to-one `Activity.campaign_contact` et comptée `distinct=True` — un contact
    relancé cinq fois reste UN contact atteint
    (`campaigns/services/campaign_contact_reach.py`, `83963e1`).
  - **Attribution campagne unifiée : born-from ∪ touched-by** — une campagne
    revendique un deal s'il est NÉ d'elle (`source_campaign`, inconditionnel)
    OU si elle l'a TRAVAILLÉ (activité aboutie). Une seule fonction,
    `attributed_cycles` (`campaigns/services/campaign_dc_attribution.py`),
    sert `PIPELINE`, `WON` et `NEW_LOGOS` — plus d'implémentation par surface
    (`f979caf`, `18107b1`, `14193fd`, `81fd6e1`).
  - **`NEW_LOGOS` campagne = la TRANSITION, pas le compte** — le deal gagné qui
    a fait passer un compte de prospect à client : plus ancienne victoire du
    compte (`Subquery` corrélée sur `outcome_date`), compte effectivement
    converti (`became_client_at`), puis filtré par l'attribution ci-dessus
    (`81fd6e1`).
  - **Origine campagne estampillée à la NAISSANCE** — `source_campaign` est posé
    à la création du cycle et jamais rétro-appliqué : un backfill avait
    re-parenté des DC préexistants, ce qui faussait le born-from (`f1436f4`).
  - **F1 — `NEW_LOGOS` perdait toute conversion après minuit du dernier jour** :
    `became_client_at` est un DateTimeField fenêtré sans le drapeau, donc
    `_between` comparait `<= <dernier jour> 00:00:00` et jetait 23 h 59 de
    conversions. Démontré en vidant le SQL généré (avec le `RuntimeWarning`
    naive-datetime de Django à l'appui) avant correction (`8047345`).
  - **Fraîcheur des cartes campagne — les DEUX couches** : côté SERVEUR,
    `build_drf_cache_key(tag_namespace=…)` ne pliait qu'UN tag (`campaigns`)
    alors que les chiffres viennent des cycles, des lignes produit, des
    activités et des conversions de compte ; `CAMPAIGN_CACHE_TAGS` +
    `build_tag_signature` (ajouté dans `core/cache_utils.py`, réutilisé par les
    deux couches) plient désormais les quatre tags dans la clé des trois
    surfaces cachées (liste, détail, dashboard). Côté CLIENT, les 21 helpers
    d'écriture ne revalidaient que leurs propres clés :
    `revalidateMetricSurfaces` / `METRIC_SURFACE_PREFIXES` (`api/_swr.js`)
    rafraîchissent aussi `/campaigns/`, `/quotas/quotas/` et `/bi/kpi/`.
    Corriger une seule couche laissait Redis resservir le même corps périmé
    (`b05c6de`).
  - **Saisie de la remise sur les lignes produit** — le champ
    `discount_percent` avait une colonne, une `CheckConstraint`, un validateur
    et un terme dans la formule du total, mais AUCUNE entrée : chaque ligne
    naissait à 0 %. Le dialogue gagne un champ Discount % (garde 0-100 côté
    front, backend inchangé et toujours le vrai filet), et le tableau une
    colonne Discount entre Prix unitaire et Total ligne — sans quoi le total
    d'une ligne remisée ne s'explique pas à l'écran (`d852ccf`).
  - **Puce de date de clôture repointée sur `effective_close_date`** — l'en-tête
    du workspace dérivait sa date de `created_at + estimated_timeline_days`,
    c'est-à-dire une DURÉE estimée et non une date convenue : éditer la date de
    clôture ne déplaçait rien. Elle lit désormais la règle unique du backend
    (`close_date_sql.py`), avec un état vide neutre « No close date » quand il
    n'y a ni date manuelle ni activité de clôture datée
    (`e59c7b8`, `d852ccf`).
  - **Retrait du chemin quota LEGACY des deux Home** — `QuotaBlock`,
    `TeamQuotaGroup`, `utils/quotaFormat.js` et `api/quotas/quotas.js` supprimés
    fichier par fichier (preuve grep par fichier, jamais de balayage global :
    `CampaignAccount` est mort dans un fichier et vivant dans un autre)
    (`41bd456`, `ec81155`).
- **Migrations** : `decision_cycles/0023` (`expected_close_date`),
  `quotas/0003` (valeurs de `Quota.metric`), `quotas/0004` (purge des objectifs
  `LEADS` stockés).
- **Validation** : chaque sous-étape validée par une reproduction ROUGE d'abord
  puis une sonde de NON-VACUITÉ (mutation du code de production → le test
  re-échoue → restauration par édition ciblée). Front vitest : **832 tests, 116
  fichiers, vert**. Backend : suites vertes hors les 7 échecs PRÉ-EXISTANTS
  dépendants de Redis (`tests/bi/test_cache.py`, `test_invalidation.py`,
  `test_end_to_end.py`), identiques sur `origin/main`. **Écart signalé** : les
  tests de la table de vérité assertent sur la CLÉ de cache et non sur une
  péremption observée — les deux couches de cache se court-circuitent sans
  Redis, donc un test comparatif passerait à VIDE dans cet environnement.
  **Épisode de régression** : trois commits campagne ont laissé 12 tests rouges
  dans `tests/bi` (seules `tests/campaigns` et `tests/decision_cycles` avaient
  été jouées) ; détecté en rejouant la baseline dans des worktrees jetables,
  corrigé en `0a24ab0`.
- **Dette fermée** : aucune entrée TECH_DEBT existante n'était ouverte sur ces
  sujets — l'attribution campagne, `LEADS` vivant et le « brouillon » monétaire
  campagne n'étaient tracés nulle part (vérifié par recherche sur les 169
  entrées). **Dette ajoutée** : **TD-171** (moteur quota/personnel legacy à
  retirer), **TD-172** (`apps/campaign/*` legacy), **TD-173** (décalage d'un
  jour sur `outcome_date`), **TD-174** (`estimated_timeline_days` conservé mais
  débranché), **TD-175** (renommage `quotas` → `objectives`), **TD-176**
  (migration corrective `source_campaign`), **TD-177** (branche `new_logos`
  campagne possiblement morte), **TD-178** (agrégation par campagne non
  mutualisée).
- **⏸️ REPORTÉ — à NE PAS considérer comme livré** :
  - **Smoke PO « éditer `expected_close_date` → la puce d'en-tête bouge »** :
    l'INPUT existe (modale DC, Formik) et le backend est PRÊT, mais l'accès
    éditable final vit dans le workspace DC. **Backend prêt, smoke reporté au
    sprint Workspace / DC** (3bis) puis à la période de test finale. **Ne PAS
    marquer fait.**
  - **Vue Objectifs** (permissions + filtres de périmètre) → sprint
    **« Objectifs — Vue » (3ter)**.
  - **Smoke de bout en bout sur environnement Redis** → **Sprint test**
    (pré-déploiement) : sans Redis, la moitié des gardes de fraîcheur ne
    s'exécute pas.
  - **Surfaces legacy** (`bi/quota.py`, `SalesQuota`, `apps/campaign/*`) →
    nettoyage avant déploiement, TD-171 / TD-172.
- **Prochain jalon** (ordre cible) : **Sprint Workspace / DC (3bis)**.

### Sprint DC-step élagage ✅ — Retrait de la page per-step workspace (front, branche `feat/dc-step-elagage`)
- **Objectif** : élaguer l'UI du Decision Cycle en SUPPRIMANT la PAGE per-step
  workspace et en reroutant ses accès vers le DC workspace, SANS toucher à la
  couche données/linkage (modèle step + FK activité + services).
- **Livré** :
  - **Suppression de la page per-step** (S3) : route
    `/accounts/[id]/decisionSteps/[stepId]`, sa vue, ses 5 onglets + header
    (dossier `Decision-steps/`), et le builder `buildStepBreadcrumbs`.
  - **Reroutes vers le DC workspace, onglet timeline**
    (`/accounts/{id}/dc/{cycleId}?tab=timeline`) : crumb « étape » du breadcrumb
    d'activité (S1) + clic sur le nom du cycle dans le header d'activité (S2.1).
    Fallback `?tab=decision-cycle` si le cycleId est absent.
  - **Retrait des 3 accès restants à la page** (S2.2) : bouton « Open Step
    Workspace » du `StepDetailDrawer`, fallback dormant de
    `DecisionCycleTimeline`, lien cassé `/decision-steps/` d'`ActivityOverviewTab`.
- **Conservé (couche données/linkage, HORS périmètre UI)** : modèle
  `DecisionStep`, FK `Activity.decision_step`, services derivation/BI/AI, endpoint
  `/decision_cycles/steps/` + ses serializers (pickers d'étape), `StepDetailDrawer`
  (panneau info, reste dans le DC workspace), `DecisionStepTimelineSerializer`.
- **Constat clé — question « mort ou vivant » TRANCHÉE** : `/decision_cycles/steps/`
  N'EST PAS mort — consommé par les pickers d'étape (`ActivityModal`,
  `ActivityOverviewTab`) via `?cycle_id=`. Verdict : **VIVANT, conservé.** AUCUNE
  optimisation faite : l'élagage était UI (page per-step), PAS perf — la lenteur
  3,3s reste ouverte et distincte (**TD-154** RESOLVED mort/vivant + **TD-179** perf).
- **Validation** : suite vitest verte (834 tests) ; `next build` OK (route per-step
  disparue de la table, aucun import non résolu). Dettes tracées : **TD-154**
  (RESOLVED) + **TD-179 → TD-185**.
- **Prochain jalon** (ordre cible) : **Sprint Workspace / DC (3bis)**.

---

### Sprint Bloc IA / Qualification ✅ — Signaux agrégés, qualification groupée & garde COST (branche `feat/signals-qualif-scope`)
- **Objectif** : faire de la **Qualification** une lecture UNIQUE et cohérente à
  travers les trois surfaces (Compte / Decision Cycle / Activité) — un scope et
  un département de rattachement portés par le signal, un endpoint agrégé qui
  fusionne les 8 types en une liste, des vues groupées/plates réunies dans un
  seul onglet, un jeu de filtres identique partout — et **fermer la fuite de
  qualité** sur la classification IA (domaine `what` / dimension `dimension`).
- **Livré** :
  - **Scope & ciblage portés par le signal (A1, A1.4, B0)** : `scope_level`
    (BUSINESS / DEPARTMENT) + `target_department` (FK `StandardDepartment`)
    résolus à l'extraction avec gardes, exposés sur les serializers de
    qualification en restant **N+1-safe** (annotation / prefetch, pas de requête
    par ligne) ; `department` propagé sur les contacts de `source_context`. Le
    signal sait désormais DE QUI et DE QUEL PÉRIMÈTRE il parle.
  - **Fusion pain / impact (A2)** : `pain` et `impact` fondus en un signal unique
    `pain_impact_v1` — une seule extraction, une seule ligne de vérité, plus de
    double comptage.
  - **Endpoint agrégé `GET /module-signals/all/` (B1)** : fusionne en Python les
    **8 types de signaux** (modèles abstraits) en une liste unique, dispatch
    polymorphe du serializer par type, **400 métier** lisibles sur paramètre
    invalide, et **nombre de requêtes borné** (pas de N+1 par type). Une seule
    porte pour toute lecture de signaux mixtes.
  - **Vues signaux refondues (B1, B1.2, B2)** : `SignalLine` (ligne
    informationnelle status + message + méta) + `SignalQuickDrawer` (le drawer où
    vivent les actions) + blocs de détail partagés PAR TYPE ; les vues PLATES
    rebranchées sur l'endpoint agrégé.
  - **Nettoyages (B3, B4)** : retrait du **linkage manuel pain↔impact** devenu
    mort (TD-112) ; retrait de **l'ancien onglet Qualification** legacy.
  - **Pertinence temporelle factuelle sur les clusters (C1)** : `signal_count` +
    `period_start` / `period_end` + `span_days` — des FAITS datés, pas un score
    interprété.
  - **Actions déplacées dans les drawers (C2)** ; **Qualification Activité = listes
    plates par type, sans clusters (C3)** (une activité est un point de
    provenance unique — clusteriser n'y a pas de sens).
  - **Vue riche DC / Compte (C4, C4-fix)** : 3 sections narratives → domaine →
    dimension → lignes de cluster, disposition **deux colonnes** (Tech / Objections
    en second), accordéons MUI thémés.
  - **Drawer unique (C5)** : navigation cluster↔signal avec un **Back** qui ne
    s'empile pas (pas de pile de drawers).
  - **Onglet Signals unifié (C6)** : bascule **Grouped / Flat** dans un onglet
    unique.
  - **Garde COST — classification IA (deux volets)** :
    - **Volet 1 (prompt)** : cadrage du prompt domaine-vs-dimension + few-shots
      pour cesser de confondre l'axe COST (dimension) avec un domaine.
    - **Volet 2 (persistance)** : `what` **validé à l'écriture** contre
      `SignalWhat` ; une valeur hors liste est **journalisée**, marquée
      `is_domain_valid=False` et **exclue de TOUTES les surfaces utilisateur**
      (jamais affichée, jamais comptée) — champ ajouté par la **migration
      `0025_signals_is_domain_valid`**.
  - **Filtres Qualification groupés (identiques sur les trois surfaces groupées)** :
    **Périmètre** unifié en OR (`scope_level=BUSINESS` OU `target_department ∈
    liste` ; « Business » = `scope=BUSINESS`), **domaine** (`what`), **dimension**,
    **multi-contact**, **statut** (défaut PENDING+VALIDATED, REJECTED seulement si
    demandé). AND entre familles, OR dans le périmètre. Appliqués **côté serveur**
    sur Compte/DC (endpoint cluster `_apply_member_filters` /
    `_parse_member_filters`) et **côté client** sur Activité (`applyGroupedFilters`,
    sémantique miroir exacte du backend). Panneau de filtres en **accordéon par
    famille** (`SignalsGroupedFilterPanel`) : Qualification REMPLIE ; **Tech Stack +
    Objection en placeholders** (à remplir avec leur partie de bloc).
- **Migration** : `module_signals/0025_signals_is_domain_valid` (ajout du booléen
  `is_domain_valid`, schema-only). **À APPLIQUER au déploiement.**
- **Validation** : suites backend signaux/clusters vertes ; front vitest vert
  (dont `ActivitySignalsTab.flat`, `ActivityGroupedFilters` — filtres client-side
  Activité, périmètre OR / what / dimension / contact / statut). Chaque garde
  N+1-safe épinglée par un test de nombre de requêtes.
- **Dette ajoutée** : **TD-186 → TD-192** (voir TECH_DEBT.md) — architecture
  onglet Flat/Grouped à reconsidérer, nettoyage `ScopeLevel.PERSONAL`, passe UI de
  fin de bloc, filtres Tech Stack / Objection, clustering tech à construire,
  symétrie de validation `dimension`, narratif IA logé en Overview. **Dette
  fermée** : **TD-112** (linkage manuel pain↔impact, devenu mort et retiré).
- **⏸️ REPORTÉ — à NE PAS considérer comme livré** :
  - **Familles Tech Stack & Objection** des filtres groupés — sections présentes
    mais VIDES (placeholders), livrées avec leur partie de bloc (TD-189).
  - **Clustering des signaux tech** — les signaux tech ne clusterisent pas (dédup
    par `tech_name_normalized` uniquement) ; à construire quand l'étape Tech sera
    traitée (TD-190).
  - **Passe UI esthétique de fin de bloc** (bordures de section, polish des cartes,
    multi-select département, drawer) — reportée au Sprint UI (TD-188).
  - **Narratif IA en Overview** — fonctionnalité IA codée dans le bloc mais logée
    dans la surface Overview, en fin de bloc (TD-192).
- **Prochain jalon** (ordre cible) : suite du **Bloc « Commandes IA » (#4)** —
  Tech Stack (prompt + affichage) et Objection.

---

### Sprint Bloc IA / Tech Stack ✅ — Cluster tech (stack actuelle) : prompt canonique, agrégation read-time & UI (branche `feat/techstack-cluster`)
- **Objectif** : traiter l'étape **Tech Stack** du Bloc « Commandes IA » — faire
  d'une techno mentionnée plusieurs fois **UNE ligne agrégée** (Compte + DC),
  lisible et cliquable, **sans rien stocker de l'appartenance**.
- **Livré** (sous-étapes 1→4, chacune validée reproduction ROUGE d'abord puis
  sonde de NON-VACUITÉ) :
  - **Prompt d'extraction canonique (sous-étape 1)** : le prompt tech
    (`prompts/transcript_signals/techstack_v1.py`) durcit la sortie `tech_name`
    vers une graphie **canonique et stable** — fusion des variantes lexicales
    (« HubSpot » / « Hubspot CRM » → « HubSpot ») et résolution des acronymes
    non ambigus (« SFDC » → « Salesforce »), avec **repli verbatim** si l'outil
    est inconnu/ambigu (pas de mapping inventé). **Les 3 booléens
    `is_competitor` / `is_integration` / `is_to_replace` NE sont PAS touchés** —
    leur sous-remplissage reste le mode d'échec ASSUMÉ (ancres
    `TODO(S10→AI-sprint)` conservées) ; leur ROUTAGE est reporté aux
    sous-sprints Objection / Competitors.
  - **Clustering tech READ-TIME (sous-étape 2)** : `SignalClusterService`
    agrège les `TechStackSignal` en clusters **par `tech_name_normalized`** —
    une techno = **une ligne unique** (Compte + DC). **100 % dérivé à la
    lecture** : **aucune appartenance stockée** (ni champ, ni table de liaison,
    ni `canonical_key` persisté) ; éditer un `tech_name` (qui recalcule
    `tech_name_normalized` au `save()`) **recolle** les doublons au refetch
    suivant, sans autre action. Chemin d'agrégation **parallèle** (le tech n'a
    ni `canonical_key` ni `what`/`dimension`) : `_fetch_tech_signals` +
    groupement par nom normalisé + `_build_tech_cluster`, **au format cluster
    unifié** (clés `what`/`dimension` **neutres** = null, valeurs neutres sur
    les axes absents). Membre = `TechStackSignalListSerializer` **réutilisé**
    (pas de nouveau serializer).
  - **Drawer & ligne cluster tech (sous-étape 3)** : le drawer cluster tech
    affiche **d'abord** les champs de la techno représentative (`TechDetailBlock`
    **réutilisé**) **puis** la liste des signaux sources, avec la navigation
    **cluster↔signal existante** (Back sans pile). Ligne de cluster tech
    **épurée** : nom + N signaux + dernière confirmation ; **BADGE PRIORITÉ
    MASQUÉ pour le tech** (décision produit : le tech n'a **pas** de priorité —
    `priority_bucket` neutre `LOW`), le masquage restant **conditionnel par
    type** (pain / impact / objectif gardent leur badge).
  - **Colonne droite branchée sur le PIPELINE CLUSTER (sous-étape 4)** : la
    colonne droite Qualification (**Compte ET DC**) rend le tech via le **même
    pipeline cluster** que la colonne gauche (`useGetClustersByAccount` + bucket
    par `signal_type` + `ClusterRow` + drawer), **PAS** le chemin flat. Le
    vocabulaire cluster (`tech_stack`) reste **interne au pipeline** ; un cluster
    tech ne traverse jamais un composant du vocabulaire flat (traduction locale
    au seul drawer — voir TD-197).
  - **Fix bug 500 (sentinel de tri)** : `signal_cluster_service.py:307`, le
    sentinel du tri secondaire (`last_confirmed_at or timezone.datetime.min`)
    était **timezone-NAÏF** sous `USE_TZ=True` → `TypeError: can't compare
    offset-naive and offset-aware datetimes` dès que le tri secondaire
    s'exécute. **Bug LATENT (tous types)** **révélé par le tech**
    (`priority_score=0` en dur → égalités de score systématiques → comparaison
    aware/naïf forcée). Corrigé au **point central unique** : sentinel rendu
    **aware** (`datetime.min` en UTC, idiome projet `core/idempotency.py`).
- **Migrations** : **AUCUNE** — tout le clustering tech est **dérivé à la
  lecture** ; aucune colonne, aucune table.
- **Validation** : suites backend signaux/clusters **vertes** ; front **vitest
  vert** ; **`next build` clean** (aucun import non résolu). Chaque sous-étape
  validée par une **reproduction ROUGE d'abord** puis une **sonde de
  NON-VACUITÉ** (mutation ciblée du code → le test re-échoue → restauration par
  édition ciblée, **jamais `git checkout`**). **Smoke PO de bout en bout
  validé** : agrégation (une techno = une ligne), drawer (champs techno puis
  signaux sources), **édition read-time** (renommer recolle les doublons),
  **Compte ET DC**.
- **Dette fermée** : **TD-190** (clustering tech à construire → **livré,
  read-time**).
- **Dette ajoutée** : **TD-196 → TD-200** (voir TECH_DEBT.md) — filtre tech
  fantôme, double vocabulaire de slug `tech_stack`/`tech-stack`, docs backend
  périmées, passe cluster « infos par cluster » (fin bloc Signaux), filtres DC
  « inclure les signaux du compte ». **TD-189** reste OPEN (filtres
  Tech/Objection en placeholders) — se ferme en **deux temps** (Objection au
  sprint Objection, Tech au sprint Competitors).
- **⏸️ REPORTÉ — à NE PAS considérer comme livré** :
  - **Routage des 3 booléens de rôle** — `is_integration` → signal `constraint`
    (**l'extraction `constraint` N'EXISTE PAS aujourd'hui — à CONSTRUIRE**, pas
    un simple routage) au **sprint Objection** ; `is_competitor` (routage au
    point central `SignalManager.create`) + **SUPPRESSION du champ
    `is_to_replace`** au **sprint Competitors**. Les booléens restent
    sous-remplis et non routés à ce stade.
  - **Filtres de la famille Tech** (UI + backend) — arrivent avec le **sprint
    Competitors** (TD-189 partie Tech, TD-196).
  - **Info cluster « remplacement envisagé »** (l'account utilise une techno
    mais songe à en changer — info de **NIVEAU CLUSTER dérivée des signaux, non
    actée**, remplaçant l'ancien booléen `is_to_replace`) — à la **passe
    cluster** de fin de bloc Signaux (TD-199).
- **Prochain jalon** (ordre cible) : suite du **Bloc « Commandes IA » (#4)** —
  **Objection** (inclut `is_integration` → signal `constraint` « must
  integrate » — extraction constraint à CONSTRUIRE).

---

### Sprint Bloc IA / Contrainte ✅ — Signal Constraint (Decision Criteria) : extraction dédiée, scope durci, cluster par nature & filtre (branches `feat/constraint-signal` + `feat/constraint-scope-guard`)
- **Objectif** : traiter l'étape **Contrainte** du Bloc « Commandes IA » — capter
  les **exigences imposées à la solution** (les *Decision Criteria* du deal), les
  classer par **nature**, les scoper par **département**, les agréger et les
  afficher. ⚠️ **C'est la CONTRAINTE qui est livrée, PAS l'Objection (blocker)** —
  l'Objection reste à faire (voir la séquence PO plus bas).
- **Livré** (chaque sous-étape validée reproduction ROUGE d'abord puis sonde de
  NON-VACUITÉ) :
  - **Signal `Constraint` = Decision Criteria du deal** : nouveau signal
    **détaché**, enum **`ConstraintNature`** (`FUNCTIONAL` / `TECHNICAL` /
    `FINANCIAL` / `CONTRACTUAL` / `OPERATIONAL` / `SECURITY` ; **libellé
    d'affichage « Contractual & Legal » pour `CONTRACTUAL`**) + `rigidity`
    (FIRM / FLEXIBLE).
  - **Extraction dédiée (stage `constraint`)** : le LLM **repère les exigences
    imposées à la solution** et émet **`nature` + scope département + `rigidity`**.
  - **Scope par DÉPARTEMENT (BUSINESS par défaut), garde DURCI** : un département
    n'est attribué **que s'il est EXPLICITEMENT DÉSIGNÉ** comme concerné —
    **jamais** par le **locuteur**, **jamais** par un **mot technique** (SSO /
    ERP / chiffrement) ; sinon **BUSINESS**. Durcissement appliqué au **bloc
    scope PARTAGÉ** (`constraint` + `pain` + `objective` + `impact`), avec garde
    **anti-sur-correction** (un département réellement désigné reste ce
    département).
  - **Frontière objective / impact / pain ↔ constraint resserrée** : une
    exigence sur la solution n'est plus captée comme objectif/impact —
    `objective` = **métrique / but du client** ; `constraint` = **obligation du
    cahier des charges**.
  - **Détachement du `what` × `dimension`** (axes inadaptés aux contraintes) :
    `what` / `dimension` **nullable**, `canonical_key` **non calculé**,
    `is_domain_valid` **non déclenché** — `nature` est le **champ dédié** (jamais
    logé dans `what`).
  - **`is_integration` du signal tech RE-ROUTÉ en contrainte de nature
    `TECHNICAL`** : la **colonne `is_integration` est NEUTRALISÉE** (le rôle est
    désormais porté par une contrainte) ; **drop de la colonne reporté au sprint
    Competitors**.
  - **Cluster par NATURE au read-time dans le DC** (doublons collapsés) ;
    affichage : **section Contraintes en Activity (liste plate) ET DC (cluster
    par nature)**, **ABSENTE en Account** (la contrainte est **deal-scoped**).
  - **Filtre des contraintes par nature** dans le panneau groupé (multi-select
    Nature, **DC seulement**) — **NON exhaustif**, repris au **sprint Filtres
    transverse**.
- **Migration** : **0026** (`nature` + `what` / `dimension` nullable).
- **Validation** : suites **backend / front vertes** ; chaque sous-étape validée
  par une **reproduction ROUGE d'abord** puis une **sonde de NON-VACUITÉ**
  (mutation ciblée → le test re-échoue → restauration par **édition ciblée,
  jamais `git checkout`**). **Smoke PO de bout en bout validé** : extraction,
  **natures correctes**, **scope BUSINESS** pour un sujet **non désigné**,
  **cluster par nature**, **affichage sur les 3 surfaces**, **filtre par nature**.
- **Dette fermée** : la partie **clustering / affichage contrainte** (livrée) ;
  **TD-189** **avance** — partie **constraint** (filtre par nature) livrée
  **partielle** ; le **reste des filtres** reste **OPEN** (→ sprint Filtres
  transverse, cf. TD-202).
- **Dette ajoutée** : **TD-201 → TD-206** (voir TECH_DEBT.md) — scope tech
  (usage) faux, filtres non exhaustifs, badge « X signals » incohérent,
  homogénéisation UI Activity/DC, modaux Edit des signaux, nettoyage code mort
  AI/Signals.
- **Prochain jalon** (ordre cible) : suite du **Bloc « Commandes IA » (#4)** —
  **Tech scope (usage)** puis **Blocker (Objection)** (voir la **séquence PO
  réordonnée 2026-08-28** ci-dessous).

---

### Sprint Bloc IA / Tech scope ✅ — Département d'usage MULTI (M2M), résolution de nom robuste & bascule mono→multi complète (branche `feat/techstack-usage-scope`)
- **Objectif** : traiter l'étape **Tech scope (usage)** du Bloc « Commandes IA »
  — capter **QUI utilise l'outil** (le **département d'usage**), en
  **MULTI-DÉPARTEMENT** (« Sales + Marketing sur HubSpot » est légitime), et
  faire une bascule **complète** de l'ancien FK unique vers un M2M.
- **Livré** (chaque sous-étape validée reproduction ROUGE d'abord puis sonde de
  NON-VACUITÉ — mutation ciblée → le test re-échoue → restauration par **édition
  ciblée, jamais `git checkout`**) :
  - **Le signal tech capte QUI utilise l'outil, en MULTI-DÉPARTEMENT** : nouveau
    **M2M `usage_departments` → `StandardDepartment`** (plusieurs départements
    par techno), qui **REMPLACE** l'ancien **FK singulier `usage_department`**
    (retiré). Attribut de l'observation, affiché et filtrable.
  - **Extraction — désignation EXPLICITE** : le LLM identifie le(s)
    département(s) **utilisateur(s)**, **même règle de DÉSIGNATION EXPLICITE que
    le scope contrainte** — un département n'est capté **que s'il est nommé**
    comme utilisateur (« l'équipe marketing est sur HubSpot » → Marketing ;
    « Sales et Marketing » → les deux) ; **aucun désigné → LISTE VIDE** (jamais
    d'invention) ; **ni le locuteur ni un mot technique** ne suffisent.
  - **Résolution de nom ROBUSTE** : un **mot fonctionnel** émis par le LLM est
    résolu vers le **libellé exact du référentiel** (« support » → « Customer
    Support ») — **match exact insensible à la casse** puis **mot-unique NON
    ambigu** (un mot présent dans **un seul** libellé) ; un mot **ambigu**
    (« management ») **ne résout rien** (garde anti-sur-correction). Réutilise le
    même référentiel `StandardDepartment` que le scope partagé, pas de moteur
    fuzzy inventé.
  - **`usage_scope` (TEAM / COMPANY / UNKNOWN) CONSERVÉ = ÉCHELLE**,
    **complémentaire** du M2M (le **QUI** est orthogonal à l'**à quelle
    échelle**) — plus aucun couplage conditionnel entre les deux.
  - **Bascule mono→multi COMPLÈTE** : **extraction, prep_call, deal_health,
    affichage ET saisie manuelle** (serializer Create/Update + wizard
    activities/accounts) tous repointés sur le M2M ; **FK singulier droppé**
    (migration). Le serializer accepte une **liste d'ids** de département ; le
    wizard passe d'un select unique conditionnel à un **multi-select** toujours
    disponible.
  - **Affichage — UNE seule ligne d'usage** : **départements si présents** (en
    **texte simple**, séparés par virgule), **sinon l'échelle** (Company-wide /
    Team / Unknown). Plus de **chip**, plus de **doublon** « Company-wide » +
    « Marketing » côte à côte (le département **PRIME** sur l'échelle).
  - **Cluster tech INCHANGÉ** (toujours par **nom** — `tech_name_normalized`,
    pas de `canonical_key`).
- **Migrations** : **0027** (ajout du M2M `usage_departments` + table de
  liaison, sans backfill), **0028** (drop du FK `usage_department`, réversible),
  **0029** (merge des deux feuilles 0028 — le drop et le drift pré-existant
  `signalclusterarchival` — no-op de schéma, réconciliation de graphe).
- **Validation** : suites **backend / front vertes** (Postgres ; `next build`
  clean). **Smoke PO de bout en bout** : **HubSpot → Marketing**, **Zendesk →
  Customer Support** (mot fonctionnel « support » résolu), **outil non désigné →
  vide** (+ `usage_scope` cohérent) ; création/édition manuelle écrivant bien le
  M2M ; une seule ligne d'usage, sans doublon.
- **Dette fermée** : **TD-201** (scope tech faux — le département d'usage est
  désormais capté, multi-département, avec résolution robuste).
- **Dette ajoutée** : **aucune nouvelle entrée** — le resserrement prompt tech
  (techno UTILISÉE vs ENVISAGÉE ; incohérence `usage_scope=COMPANY` + département
  désigné) et le test multi-département au smoke A→Z sont tracés en TECH_DEBT (à
  la suite de TD-206) et rattachés au sprint Competitors / au smoke ; les
  docstrings `usage_scope`/`UsageScope` résiduelles après le drop sont rattachées
  à **TD-206** (nettoyage code mort).
- **Prochain jalon** (ordre cible) : suite du **Bloc « Commandes IA » (#4)** —
  **Competitors** (prompt + pipeline + UX) puis **M2M scope transverse** (voir la
  **séquence PO réordonnée 2026-08-28 post Tech scope** ci-dessous).

---

### Sprint Bloc IA / Competitors ✅ — Signal détaché CompetitorSignal (DC-only) + drops is_competitor / is_integration (branche `claude/competitor-signal-model-migration-lzc5dh`)
- **Objectif** : traiter l'étape **Competitors** — faire du concurrent un **signal
  DÉDIÉ et DÉTACHÉ** (annule l'ancien attribut booléen `is_competitor`), l'afficher
  au bon endroit (Activité + DC), et nettoyer les booléens tech morts.
- **Livré** (chaque sous-étape : reproduction ROUGE d'abord + sonde de NON-VACUITÉ,
  restauration par édition ciblée jamais `git checkout`) :
  - **CompetitorSignal, signal détaché DC-only** : modèle + migration **0030**
    (verbatim `source_quote` + `summary` LLM + `competitor_name` / `_normalized`),
    cloné sur `ConstraintSignal`. Trois signaux **non exclusifs** coexistent pour
    un même outil : TechStack (utilisé) + Constraint TECHNICAL + Competitor.
  - **Extraction dédiée** : prompt `competitor_v1` + stage competitor.
  - **Backfill 0031** : `is_competitor=True` → CompetitorSignal (marker de
    réversibilité) — data de test, pas de perte.
  - **Recâblage lecteurs** : prep_call / deal_health lisent le CompetitorSignal
    (match read-time par `competitor_name_normalized`), puis neutralisation de
    l'écriture à l'extraction.
  - **Affichage** : Activité (flat + grouped) + DC (flat + **cluster par
    `competitor_name_normalized`** + **filtre par nom, DC-only**) ; **absent
    d'Account**.
  - **Retrait du tagging manuel** : Competitor (8-bis) puis Integration (9b —
    + suppression du doublon deal_health « Integration: yes », le chemin
    **Constraint TECHNICAL** couvrant déjà).
  - **Drops de colonnes** : régularisation de la dérive `signal_type` (**0032**),
    drop `is_competitor` (**0033**), drop `is_integration` (**0034**).
- **Migrations** : **0030** (CompetitorSignal + index), **0031** (backfill
  data, réversible), **0032** (AlterField `signalclusterarchival.signal_type`,
  choices-only, régularise une dérive pré-existante depuis 6.1), **0033**
  (RemoveField `is_competitor`, pur/réversible), **0034** (RemoveField
  `is_integration`, pur/réversible). **Pas de backfill de perte** (décision PO).
- **Validation** : suites backend / front vertes (Postgres ; `pytest tests/signals`
  357, `tests/ai_pipelines` 360, `vitest` 999). **Smoke PO** : extraction prouvée
  sur transcript réel — 3 signaux NON exclusifs sur un même outil (Salesforce =
  TechStack utilisé + Constraint TECHNICAL + Competitor) + non-confusion
  (Slack/Outreach) ; section Competitors présente en Activité (**présentation à
  revoir — nom concurrent non affiché, renvoyé à l'UX Activity**) ; retrait des
  tags manuels Competitor/Integration vérifié. **Smoke front DC (cluster par nom +
  filtre par nom + absence Account) NON réalisé — reporté au sprint UX Activity**
  (rendu réel des surfaces DC), le cluster et le filtre étant **prouvés par tests**
  (cluster DC-only group-by `competitor_name_normalized` : test vert ; filtre par
  nom : vitest vert). Cohérent avec la stratégie PO « une seule vérification sur le
  rendu réel, pas de smoke à l'aveugle ».
- **Dette fermée** : **aucune entrée TECH_DEBT** n'était ouverte sur le signal
  competitor lui-même (étape planifiée, pas une dette).
- **Dette ajoutée** : **TD-209** (chantier DC deal health : lecture directe du
  CompetitorSignal + « Who we're up against » + reconstruction snapshot) et
  **TD-210** (grounding extraction competitor sur catalogue produit). **MAJ** :
  **TD-199** (`is_to_replace` **NON** supprimé au Competitors — conservé, drop
  reporté à cette passe cluster), **TD-196** (doc filtre fantôme cite désormais
  un champ droppé), **TD-189** (filtre-nom competitor livré ≠ filtres tech),
  **TD-13/TD-52** (Postgres-only re-confirmé), **TD-207** (rattachement revu —
  non livré ici), **TD-198** (docstring `source_activity` NOT NULL faux à balayer).
- **Prochain jalon** (ordre cible) : **People** (voir la séquence PO 2026-08-31
  post Competitors ci-dessous).

---

### Sprint Bloc IA / People ✅ — PeopleSignal câblé E2E : full_name + cluster à deux niveaux + réconciliation contact (branche `feat/people-full-name`)
- **Objectif** : câbler le signal People de bout en bout — identité nominale
  (`full_name`), clustering par personne, surface Activité, et prouver la
  réconciliation contact sur les briques EXISTANTES. People reste **éditable
  manuel** (décision PO verrouillée) — pas d'extraction LLM.
- **Livré** (chaque sous-étape : reproduction ROUGE d'abord par le VRAI chemin +
  sonde de non-vacuité, restauration par édition ciblée jamais `git checkout`) :
  - **`full_name` + `full_name_normalized`** sur PeopleSignal (dérivé en save(),
    read-only par contrat), cloné sur tech / competitor ; **3e chemin d'identité**
    aux côtés de `target_contact` / `target_department` (l'invariant clean()
    reste : au moins un des trois).
  - **Cluster à deux niveaux** (read-time, DC-only, REJECTED exclu) :
    `contact:<id>` si contact, sinon `name:<norm>|dept:<id>` si nom, sinon
    `signal:<id>` — un People sans nom = **entrée propre, jamais fusionnée**.
  - **Serializers** : `full_name` writable (Create + Update), `full_name` +
    `full_name_normalized` en lecture (List + Detail) ; invariant d'identité
    appliqué sur **create ET update** (400 standard, jamais 500).
  - **Surface Activité** : People rejoint la liste des signaux (flat + grouped).
  - **Réconciliation prouvée** (test d'intégration, vrais endpoints) : suggest
    (`GET /contacts/`) → create (`POST /contacts/`) → link / unlink
    (`PATCH module-signals/people/{id}`) ; `POST /contacts/` renvoie désormais
    l'objet créé (id inclus).
- **Migrations** : **0035** (AddField `full_name` + `full_name_normalized`
  + AddIndex `peoplesig_name_norm_idx`).
- **Validation** : suites vertes (Postgres, en série) — `pytest tests/signals`
  **372**, `tests/ai_pipelines` **360**, `tests/contacts` **27**, `vitest`
  **1000** (134 fichiers) ; flux d'intégration réconciliation **8/8**. **Pas de
  smoke UI** People — reporté au sprint **UX Activity** (rendu réel des surfaces),
  le cluster à deux niveaux et l'invariant d'identité étant **prouvés par tests**.
- **Dette fermée** : **aucune entrée TECH_DEBT** ouverte sur le signal People
  lui-même (étape planifiée, pas une dette).
- **Dette ajoutée** : **TD-211** (surface front People : modale de réconciliation
  suggest/create/link + split `full_name` → first/last + rendu/édition manuelle),
  **TD-212** (`POST /contacts/` renvoie l'objet créé — **RESOLVED** ce sprint),
  **TD-213** (influence mal placée : `Contact.influence_level` vs
  `PeopleSignal.influence` — décision produit). **MAJ** : **TD-204** (rendu
  section People), **TD-205** (drawer edit people + champ `full_name`), **TD-206**
  (garde morte cluster People). **Incitation à nommer** un People sans identité :
  vit à la fois dans le **drawer d'édition manuelle** (TD-211) **ET** dans le
  **deal health / missing elements** (TD-209) — les deux **reliés**, pas
  contradictoires.
- **Prochain jalon** : **Next steps** (voir la séquence PO 2026-08-31 post
  Competitors ci-dessous).

---

### Sprint Bloc IA / Next steps ✅ — Garde DC-only + objectif du next step généré/affiché E2E (branche `feat/next-steps-dc-only`)
- **Objectif** : finir le câblage du NextStepSignal — le proposer UNIQUEMENT en
  contexte decision_cycle (feature DC-only), et faire porter au next step
  l'OBJECTIF de l'activité qu'il propose (rôle + enjeux, prospect + commercial),
  généré par le LLM et propagé jusqu'à `Activity.call_to_action`.
- **Livré** (chaque sous-étape : reproduction ROUGE d'abord par le VRAI chemin +
  sonde de non-vacuité, restauration par édition ciblée jamais `git checkout`) :
  - **Garde DC-only (BE)** : `want_nextsteps` conditionné à
    `activity.decision_cycle_id` (`activity_extraction_view.py:171`) — saut
    SILENCIEUX en campagne (200, pas de 400), qualification intacte ; toggle
    unique gate dedup + run + réponse.
  - **Garde DC-only (front)** : l'onglet Next Steps reste TOUJOURS visible
    (campagne ET DC) ; seul le BLOC de suggestions IA est masqué sans DC
    (`ActivityNextStepsTab`) ; « Set a next step manually » reste accessible en
    campagne (une campagne réussie peut matérialiser une activité / faire naître
    un DC).
  - **Objectif du next step (`suggested_objective`) alimenté E2E** : le prompt
    `next_steps_v1` l'émet (OUTPUT SCHEMA + règle d'émission), le builder
    `next_step_extractor` le stocke (toléré vide), le serializer l'expose
    (List + Detail), il s'affiche sur toutes les surfaces (AISuggestionCard,
    drawer, SignalDetailCard/Content) et pré-remplit `call_to_action` à la
    conversion (mapping `serializers.py:1100` ACTIVÉ + pré-remplissage
    `ActivityModal.jsx`).
  - **`suggested_contacts`** : capacité DORMANTE **documentée** (commentaires
    seuls), NON retirée — câblée API mais jamais alimentée (LLM ne l'émet pas).
- **Migrations** : **aucune** (le champ `suggested_objective` et le mapping
  `call_to_action` préexistaient — activés, pas recréés ; aucun champ retiré).
- **Validation** : suites vertes (Postgres, en série) — `pytest tests/signals`
  **373**, `tests/ai_pipelines` **364**, `vitest` **1012** (136 fichiers) ;
  **smoke PO OK** (objectif visible/éditable dans le modal de conversion,
  pré-rempli depuis le signal).
- **Dette fermée** : **aucune entrée TECH_DEBT** sur le next step lui-même
  (étape planifiée, pas une dette).
- **Dette ajoutée** : **TD-214** (audit discipline de logging — log via patterns
  existants), **TD-215** (enrichissement objectif → étape DC que le next step
  fait progresser). **MAJ** : **TD-7** (`suggested_contacts` dormant documenté,
  résolution nom→Contact toujours à faire), **TD-204**/**TD-205** (rendu soigné
  de l'objectif sur carte/drawer au sprint UX Activity).
- **Prochain jalon** : **UX Activity** (layout Activity sans onglets — voir la
  séquence PO 2026-08-31 ci-dessous).

---

### Sprint Bloc IA / M2M scope départements ✅ — Scope département FK → M2M pour Pain, Impact, Constraint (branche `feat/signal-scope-m2m`)
- **Objectif** : un même signal peut concerner PLUSIEURS départements. Passer le
  scope département de FK simple (`target_department`) à M2M (`target_departments`
  → StandardDepartment) pour les 3 signaux TRANSVERSAUX **Pain, Impact, Constraint**.
  **Objective et People RESTENT FK mono-département** (décision produit : un
  objectif vise une cible unique ; une personne appartient à un département).
  Blocker/Competitor/NextStep : pas de scope département. Patron cloné =
  `TechStackSignal.usage_departments` (Sprint Tech scope, TD-201).
  ⚠️ **Insertion cadrée hors-séquence** (« M2M scope transverse », suite déjà
  cadrée dans la séquence PO 2026-08-31), traitée AVANT UX Activity à la demande
  PO. La séquence signaux reste **UX Activity → Blocker**.
- **Livré** (chaîne complète par signal — Constraint 1a-1d, Pain+Impact 2a-2d ;
  chaque sous-étape : reproduction ROUGE d'abord par le VRAI chemin + sonde de
  non-vacuité, restauration par édition ciblée, jamais `git checkout`) :
  - **Modèle + backfill** : champ `target_departments` (M2M, cloné sur
    `usage_departments`) + migration de données FK → 1ère entrée du M2M
    (baseline PO prouvée par SELECT : Constraint 14, Pain 15, Impact 4 lignes).
  - **Recâblage de TOUS les lecteurs** (serializer read, clustering
    `_compute_departments` + perimeter + fetch, prep_call, deal_health, endpoint
    agrégé) de la FK (objet unique) vers le M2M (collection), **PAR TYPE** —
    sans casser Objective/People (restés FK) : lecteurs partagés isolés par
    type/flag (helper `_compute_m2m_departments` dédié pain/impact ;
    `_apply_member_filters(uses_m2m_departments=…)` ; filtre agrégé branché sur le
    slug). Test de non-régression Objective à chaque étape.
  - **Extraction** : `constraint_v1` et `pain_impact_v1` (combiné) émettent une
    LISTE de départements ; résolution multi clonée sur
    `resolve_tech_usage_departments`. `scope_level` **RETIRÉ** du prompt Constraint
    (pas de colonne `scope_level` sur Constraint), **GARDÉ** sur Pain/Impact
    (descriptif). Objective (prompt séparé + resolver partagé) intact.
  - **Drop des anciennes FK** `target_department` (Constraint, Pain, Impact)
    après recâblage — migrations à la main, réversibles.
  - **Assainissement** de la dérive `signal_type` (matérialise le choix `people`
    oublié par le sprint People — analogue de 0032 pour `competitor`) : arbre de
    migrations enfin propre (`makemigrations --check` vert).
- **Migrations** (toutes écrites À LA MAIN, dérive `signal_type` exclue des étapes
  M2M) : **0036** (AddField M2M Constraint), **0037** (backfill Constraint),
  **0038** (drop FK Constraint), **0039** (AddField M2M Pain+Impact), **0040**
  (backfill Pain+Impact), **0041** (drop FK Pain+Impact), **0042** (assainissement
  `signal_type`, choices-only, sans DDL).
- **Validation** : suites vertes (Postgres, en série) — `pytest tests/signals`
  **395**, `tests/ai_pipelines` **370** ; `makemigrations --check module_signals`
  **propre (« No changes detected », exit 0)** ; `vitest` **inchangé** (aucun
  front touché ce chantier — backend + prompts uniquement). **Smoke PO à faire.**
- **Dette fermée** : **aucune** (chantier planifié / insertion PO, pas une dette ;
  TD-201 — précédent TechStack `usage_departments` — déjà RESOLVED).
- **Dette ajoutée** : **TD-216** (garde-fou anti-dérive `signal_type` en CI).
  **MAJ** : **TD-204** / **TD-205** (front M2M : rendu + édition multi-département
  au sprint UX Signals), **TD-206** (docstrings/prompts morts résiduels FK
  `target_department` à balayer).
- **Prochain jalon** : **UX Activity** (séquence PO 2026-08-31 — inchangée :
  UX Activity → Blocker).

---

## Ordre cible des sprints à venir + jalon LAUNCH (réorg 2026-08-15)

> **Réorganisation PO (2026-08-15).** Le PO a redéfini l'ORDRE des sprints à
> venir et la frontière PRÉ/POST-LAUNCH. Cette section RÉORDONNE et AJOUTE
> (recadrages, nouveaux sprints, jalon LAUNCH) ; elle ne SUPPRIME ni ne
> REFORMULE aucune fiche existante. Les fiches détaillées restent en place
> ci-dessous (« ## Sprints planifiés — phase fonctionnelle » et suivantes),
> contenu CONSERVÉ, avec le cas échéant une note de recadrage ajoutée. En cas
> de doute sur une fiche : la LAISSER intacte (on clarifiera au cadrage du
> sprint). Tout le livré (✅) et toutes les sections non citées sont préservés.

### Ordre cible (sprints à venir)

1. **S13 — Intention & Prep Call** — RECADRÉ. Fiche existante conservée
   ci-dessous + note de recadrage. Absorbe le ciblage/sélection des contacts et
   le PLAFONNEMENT contacts/compte/campagne (références existantes conservées).
   **✅ LIVRÉ (branche `feat/s13-activity-objective`) — voir la fiche « Sprint S13 ✅ »
   ci-dessus. NB : le PLAFONNEMENT 3-contacts/compte/campagne n'est PAS livré dans
   ce sprint (objectif + ciblage départements + retrait mode ACCOUNT seulement).
   Prochain sprint : #2 S10 — Tech Catalogue.**
2. **S10 — Tech Catalogue** — RECADRÉ. Fiche existante conservée + note.
   **✅ LIVRÉ (branche `feat/s10-techstack-signal`) — voir la fiche « Sprint S10 ✅ »
   ci-dessus.** Catalogue supprimé, signal tech autoporté (`tech_name` +
   `tech_name_normalized` + 3 booléens). NB : l'AFFICHAGE (technos au niveau compte,
   concurrents/intégrations au niveau DC), l'UI du filtre et le WORDING des prompts
   de qualification ne sont PAS livrés — voir « ⏸️ REPORTÉ » dans la fiche.
   Prochain sprint : #3 Bloc « Modèle Decision Cycle ».
3. **Bloc « Modèle Decision Cycle »** (regroupe deux fiches conservées) :
   Sprint C — Produit & Finance + Sprint decision_cycles/steps.
   **✅ Sprint C — Produit & Finance LIVRÉ** (branche `feat/sprint-c-product-finance`)
   **et Sprint C — Wiring / UI / métriques LIVRÉ** (branche `feat/sprint-c-wiring`)
   — voir les deux fiches « Sprint C ✅ » ci-dessus. Le **Sprint
   decision_cycles/steps** est **✅ LIVRÉ** (branche `feat/dc-step-elagage`) — voir
   la fiche « Sprint DC-step élagage ✅ » ci-dessus : mort/vivant tranché (endpoint
   VIVANT, conservé) + élagage UI de la page per-step. Ce bloc est donc terminé.
   Prochain sprint : #3bis Workspace / DC.
3bis. **Workspace / DC** — NOUVEAU (2026-08-21). Édition complète de l'overview
   DC. Voir la fiche « Sprint Workspace / DC » dans « Nouveaux sprints ».
3ter. **Objectifs — Vue** — NOUVEAU (2026-08-21), APRÈS le sprint DC. UI +
   permissions + filtres de périmètre. Voir la fiche « Sprint Objectifs — Vue »
   dans « Nouveaux sprints ».
4. **Bloc « Commandes IA »** (UN SEUL sprint, pensé d'un bloc, sous-étapes
   possibles) : S12 — Signaux Tech stack (prompt) DÉPLACÉ ici + Prep call
   (prompt + UI) + Signaux (tester TOUS les signaux + UI) + Deal health
   (prompt + UI) + Recherche produit / commandes IA MANAGER (à définir).
5. **Gestion des erreurs** — NOUVEAU, **PRÉ-LAUNCH**.
6. **Finition & vues** (trois fiches conservées) : Filtres & recherche
   transverses + Overviews (Sprint B) + Finalisation Home + performance / vues
   selon le TIER.
7. **Sprint UI** (fiche conservée) : visuel / modales (blocage UI du cap
   contacts, cartes Targeted → `secondary`).
8. **Homogénéisation** — NOUVEAU, distinct du Sprint UI, **POST-LAUNCH**.
9. **Snapshot / Deal History** (fiche conservée) — **POST-LAUNCH**.
10. **UI Admin Produit / gestion des tenants** — NOUVEAU, **POST-LAUNCH**.

> Les sprints 1, 2, 3, 4, 6 et 7 ne sont PAS classés pré/post launch (le PO ne
> l'a pas tranché) — ils gardent leur position dans l'ordre, sans étiquette
> launch. Ne PAS inventer de classement.

> **Note de numérotation (2026-08-21).** Les deux sprints ajoutés après le bloc
> DC sont numérotés **3bis** et **3ter** plutôt que par décalage de #4 → #12 :
> les numéros #3 à #10 sont référencés en 13 endroits du document (fiches de
> recadrage, jalon LAUNCH, « Nouveaux sprints »), qu'une renumérotation
> invaliderait silencieusement. L'ORDRE est celui de la liste ; seule
> l'étiquette évite le décalage. À renuméroter proprement si le PO préfère.

### 🚀 Jalon LAUNCH (frontière pré / post déploiement)

**PRÉ-LAUNCH — bloquant AVANT déploiement :**
- **Gestion des erreurs** (#5 ci-dessus) — audit complet des vues d'erreur.
- **Doublons de requêtes + efficacité cache** — TD principal existant, déjà
  marqué « pré-launch » dans sa fiche (« Sprint — Doublons de requêtes +
  efficacité cache », ⏸️ REPORTÉ / à faire AVANT déploiement ; TD-159
  invalidation BI tenant-wide). Référencé ici, non dupliqué.
- **Checklist infra** (NOUVEAU — absente de la roadmap, ajoutée ici) : pooling
  DB Supabase, dimensionnement des workers web. À vérifier/durcir avant la
  montée en charge multi-tenant.
- **Sprint test** (NOUVEAU 2026-08-21) — smoke PO de bout en bout de TOUTE la
  chaîne visible, **sur un environnement AVEC Redis**. Voir la fiche « Sprint
  test » dans « Nouveaux sprints ». DERNIER avant déploiement.

**POST-LAUNCH :**
- **Homogénéisation** (#8) — audit CODE des patterns.
- **Snapshot / Deal History** (#9).
- **UI Admin Produit / gestion des tenants** (#10).

### Détail des blocs regroupés

**Bloc « Modèle Decision Cycle » (#3)** — regroupe, sans les reformuler, deux
fiches existantes conservées telles quelles ci-dessous :
- **Sprint C — Produit & Finance de bout en bout** (fiche conservée, absorbée
  dans ce bloc).
- **Sprint — decision_cycles/steps (mort ou vivant AVANT d'optimiser)** (TD
  existant, fiche conservée).

**Bloc « Commandes IA » (#4)** — UN SEUL sprint, pensé d'un bloc (sous-étapes
possibles) :
- **S12 — Signaux Tech stack (prompt)** : DÉPLACÉ ici (ne plus le laisser en
  sprint séparé en amont). Toute mention existante de S12 est conservée dans sa
  fiche, avec ce cadrage ajouté.
- **Prep call** : prompt + UI.
- **Signaux** : tester TOUS les signaux + UI (réplicable dans la vue account).
- **Deal health** : prompt + UI.
- **Recherche produit / commandes IA pour MANAGER** : **à définir** — pas de
  besoin précis pour l'instant ; lié aux « vues selon le tier » ; à réfléchir
  avec le PO.

**Séquence CONFIRMÉE PO (2026-08-27) — sous-étapes du bloc, dans l'ordre :** _(⤷ SUPERSEDÉE par la « Séquence CONFIRMÉE PO (2026-08-28) » plus bas — réordonnancement post-Contrainte ; conservée pour l'historique.)_
- **0. Tech Stack (cluster stack actuelle)** — **✅ LIVRÉ** (branche
  `feat/techstack-cluster`) : prompt canonique `tech_name`, clustering tech
  **read-time**, drawer + ligne épurée, colonne droite branchée sur le pipeline
  cluster, fix 500 sentinel de tri. Voir la fiche « Sprint Bloc IA / Tech Stack
  ✅ » ci-dessus. **Ferme TD-190.**
- **1. Objection** — inclut le routage `is_integration` → signal `constraint`
  « must integrate ». **NB : l'extraction `constraint` N'EXISTE PAS aujourd'hui
  — à CONSTRUIRE (nouvelle émission d'extraction), PAS un simple routage de
  booléen.**
- **2. Competitors** — conception UX (où le signal competitor apparaît en
  **Activité ET DC**) ; routage `is_competitor` au **point central
  `SignalManager.create`** ; **SUPPRESSION du champ `is_to_replace`** du signal
  tech ; câblage des **filtres de la famille Tech** (ferme TD-189 partie Tech +
  TD-196).
- **3. Passe cluster — fin du bloc Signaux** : reprendre **TOUS** les clusters
  (pain / impact / objectif / tech) et décider les infos pertinentes/faciles à
  afficher par cluster ; pour le tech, piste **« remplacement envisagé »**
  (l'account utilise une techno mais songe à en changer, **non acté**, info de
  **NIVEAU CLUSTER dérivée des signaux, PAS un booléen** — remplace l'ancien
  `is_to_replace`). TD-199.
- **4. Prep call** (prompt + UI) — le bloc Signaux est alors **entièrement
  fermé, prod-ready**.
- **Note de cadrage (sprints finaux)** : chaque fermeture de sprint =
  **PRODUCTION READY** (comportement + UX prêts) ; seul le **vernis UI** (thème,
  composants) est reporté au **paufinage UI final**.

**Séquence CONFIRMÉE PO (2026-08-28) — réordonnancement du RESTE du bloc Signaux, post-Contrainte (SUPERSEDES la séquence 2026-08-27 ci-dessus) :** _(⤷ SUPERSEDÉE par la « Séquence CONFIRMÉE PO (2026-08-28, post Tech scope) » plus bas — réordonnancement post-Tech scope ; conservée pour l'historique.)_
- **✅ LIVRÉ** : **0. Tech Stack** (`feat/techstack-cluster`) ; **Contrainte**
  (`feat/constraint-signal` + `feat/constraint-scope-guard`) — voir les fiches
  « Sprint Bloc IA / Tech Stack ✅ » et « Sprint Bloc IA / Contrainte ✅ »
  ci-dessus.
- **Reste du bloc Signaux (ordre confirmé PO)** :
  1. **Tech scope (usage)** — capter *qui utilise quoi* (le **département
     d'usage**) + **filtre `usage_scope`** (TD-201).
  2. **Blocker (Objection)** — **scope + cluster + affichage**.
  3. **Next steps**.
  4. **Filtres transverse** — **TOUS** les filtres d'un coup, **regroupables** ;
     **ferme TD-189** (et TD-202 — filtres non exhaustifs).
  5. **Passe cluster** — infos pertinentes par cluster ; pour le tech, piste
     **« remplacement envisagé »** (info de **niveau cluster**, dérivée des
     signaux, **non actée**) — TD-199.
  6. **UX Signals** — décider onglet **Flat / Grouped partagé ou non**
     (**TD-186**) ; **homogénéisation UI Activity / DC** (TD-204) ; **modaux
     Edit** des signaux (TD-205).
  7. **Nettoyage code mort AI / Signals** (clean code — TD-206).
  8. **Smoke Signals A→Z** — transcript d'un **cycle de vente COMPLET**, étape
     par étape.
  9. **Clôture du bloc Signaux** → puis **Prep call** (prompt + UI).
- **Note de routage tech** : le **routage `is_competitor`**, la **SUPPRESSION du
  champ `is_to_replace`** et le **drop de la colonne `is_integration`**
  (neutralisée au sprint Contrainte) restent au **sprint Competitors** (tech) —
  cf. TD-196 / TD-199.
- **Note de cadrage (sprints finaux)** : chaque fermeture = **PRODUCTION READY**
  (comportement + UX) ; seul le **vernis UI** va au **paufinage UI final**.

**Séquence CONFIRMÉE PO (2026-08-28, post Tech scope) — réordonnancement du RESTE du bloc Signaux (SUPERSEDES la séquence 2026-08-28 ci-dessus) :** _(⤷ SUPERSEDÉE par la « Séquence CONFIRMÉE PO (2026-08-31, post Competitors) » plus bas — réordonnancement post-Competitors ; conservée pour l'historique.)_
- **✅ LIVRÉ** : **0. Tech Stack** (`feat/techstack-cluster`) ; **Contrainte**
  (`feat/constraint-signal` + `feat/constraint-scope-guard`) ; **Tech scope
  (usage)** (`feat/techstack-usage-scope`) — voir les fiches « Sprint Bloc IA /
  Tech Stack ✅ », « Sprint Bloc IA / Contrainte ✅ » et « Sprint Bloc IA / Tech
  scope ✅ » ci-dessus. **Ferme TD-201.**
- **Reste du bloc Signaux (ordre confirmé PO)** :
  1. **Competitors — prompt + pipeline + UX** : **conception UX D'ABORD** (où le
     signal competitor apparaît en **Activité ET DC** pour servir la stratégie
     commerciale) ; **routage `is_competitor`** ensuite ; **SUPPRESSION du champ
     `is_to_replace`** ; **drop de la colonne `is_integration`** (neutralisée au
     sprint Contrainte). Ce sprint fait le **FONCTIONNEL** (extraction juste +
     affichage au bon endroit) ; l'**UI fine** (vernis visuel) est **distincte**
     → **paufinage UI**. Cf. TD-196 / TD-199.
  2. **M2M scope transverse** — passer le scope de **TOUS** les signaux
     (**pain / impact / objective / constraint**) de **FK unique
     (`target_department`) à M2M multi-département**, sur le **modèle du tech**.
     **NOTE : refonte sur types VALIDÉS + migration de données existantes** (FK
     remplis → M2M) — à **cadrer avec audit + précaution** ; le **tech M2M
     `usage_departments` est le précédent réutilisable**. C'est un **SPRINT**,
     pas une simple dette.
  3. **Blocker (Objection)** — **scope + cluster + affichage**.
  4. **Next steps**.
  5. **Filtres transverse** — **TOUS** les filtres d'un coup, **regroupables** ;
     **ferme TD-189** (et TD-202 — filtres non exhaustifs).
  6. **Passe cluster** — infos pertinentes par cluster ; pour le tech, piste
     **« remplacement envisagé »** (l'account utilise une techno mais songe à en
     changer, **non acté**, info de **NIVEAU CLUSTER dérivée des signaux, PAS un
     booléen** — remplace l'ancien `is_to_replace`) — TD-199.
  7. **UX Signals** — décider onglet **Flat / Grouped partagé ou non**
     (**TD-186**) ; **homogénéisation UI Activity / DC** (TD-204) ; **modaux
     Edit** des signaux (TD-205).
  8. **Nettoyage code mort AI / Signals** (clean code — **TD-206**).
  9. **Smoke Signals A→Z** — transcript d'un **cycle de vente COMPLET**, étape
     par étape ; **inclut le test tech MULTI-DÉPARTEMENT + company-wide**.
  10. **Clôture du bloc Signaux** → puis **Prep call** (prompt + UI).
- **Note de cadrage (sprints finaux)** : chaque fermeture = **PRODUCTION READY**
  (fonctionnel + UX) ; seul le **vernis** va au **paufinage UI final**.

**Séquence CONFIRMÉE PO (2026-08-31, post Competitors) — SUPERSEDES la séquence 2026-08-28 post Tech scope ci-dessus :**
- **✅ LIVRÉ** : **Competitors** (`claude/competitor-signal-model-migration-lzc5dh`)
  — voir la fiche « Sprint Bloc IA / Competitors ✅ » ci-dessus ; **People**
  (`feat/people-full-name`) — signal People **éditable manuellement**, voir la
  fiche « Sprint Bloc IA / People ✅ » ci-dessus ; **Next steps**
  (`feat/next-steps-dc-only`) — garde DC-only + objectif du next step généré et
  affiché E2E, voir la fiche « Sprint Bloc IA / Next steps ✅ » ci-dessus ;
  **M2M scope transverse** (`feat/signal-scope-m2m`) — scope département FK→M2M
  pour Pain/Impact/Constraint (Objective/People restent FK), voir la fiche
  « Sprint Bloc IA / M2M scope départements ✅ » ci-dessus.
- **Reste du bloc Signaux (ordre confirmé PO)** :
  1. **UX Activity** — layout Activity **sans onglets** (tranche TD-186 : pas de
     bascule onglet).
  2. **Blocker (Objection)**.
  - [+ suites déjà cadrées : **Filtres transverse**
    (TD-189/202), **Passe cluster** (TD-199, dont **drop `is_to_replace`**),
    **UX Signals**, **Nettoyage** (TD-206), **Smoke A→Z**, **Clôture → Prep call**.]
- **Resserrement prompt tech (TD-207) à traiter AVANT la fin d'Activity** :
  rattaché à la passe de nettoyage / resserrement prompt qui **précède la clôture
  d'Activity** (avec **TD-206**), **PAS** à People ni Next steps.
- **Décisions verrouillées (2026-08-31)** : **competitor = signal détaché** (annule
  l'attribut booléen) ; **People signal éditable manuel** ; **layout Activity sans
  onglets** ; **`is_to_replace` conservé** (drop reporté **TD-199**).

### Nouveaux sprints

#### Gestion des erreurs (NOUVEAU — PRÉ-LAUNCH)
- **Position** : #5 de l'ordre cible ci-dessus. À faire AVANT launch.
- **Objectif** : audit COMPLET du produit et de TOUTES les vues d'erreur.
  Vérifier que chaque cas d'erreur est traité proprement.
- **Honnêteté UX** : **ROUGE = vraie erreur technique** ; **ORANGE = règle
  métier** ; **aucune exception brute ni fuite SQL** exposée à l'utilisateur.
- **Nature** : transverse (tout le produit).
- **NB** : distinct de la fiche existante « Sprint Gestion d'erreur — revue BE +
  FR de bout en bout » (conservée ci-dessous) ; les deux se rejoignent sur
  l'objectif « aucune fuite technique » — à réconcilier au cadrage, sans rien
  supprimer pour l'instant.

#### Homogénéisation (NOUVEAU — POST-LAUNCH)
- **Position** : #8 de l'ordre cible. DISTINCT du Sprint UI (qui est du visuel /
  modales) : ici c'est un audit **CODE**.
- **Objectif** : vérifier que TOUT le produit utilise les MÊMES patterns /
  méthodes — pas d'implémentations divergentes pour un même besoin.
- **Nature** : dette de qualité interne.

#### UI Admin Produit / gestion des tenants (NOUVEAU — POST-LAUNCH)
- **Position** : #10 de l'ordre cible.
- **Objectif** : interface d'administration de gestion des tenants — suivi de
  CONSOMMATION, LIMITATIONS, etc.
- **Lien** : rattaché à **G3 — Provisioning des tenants** (voir phase Go-Live).

#### Sprint Workspace / DC (NOUVEAU 2026-08-21)
- **Position** : **3bis** de l'ordre cible, juste après le bloc « Modèle
  Decision Cycle » (#3).
- **Objectif** : **édition complète de l'overview DC** — rendre éditables depuis
  le workspace les champs que le rep doit pouvoir corriger là où il travaille,
  et non seulement depuis la modale de création.
- **⚠️ Smoke REPORTÉ ICI depuis le Sprint C wiring — `expected_close_date`** :
  l'**INPUT EXISTE** (modale DC, Formik, `DecisionCycleModal.jsx`) et le
  **BACKEND est PRÊT** (`expected_close_date` écrivable, `effective_close_date`
  annoté et sérialisé, puce d'en-tête repointée dessus au Sprint C wiring). Ce
  qui manque est l'**accès éditable final dans le workspace DC**, qui appartient
  à ce sprint. Le smoke PO « éditer `expected_close_date` → la puce d'en-tête se
  déplace sur CETTE date » est donc **DIFFÉRÉ à ce sprint + à la période de test
  finale**. Statut à retenir : **backend prêt, smoke reporté au sprint
  workspace** — **NE PAS marquer fait**.
- **Lien** : voir aussi TD-29 (front manager-notes hors intention produit, point
  de départ logique du recadrage DC) et TD-174
  (`estimated_timeline_days` conservé mais débranché de la puce — à re-câbler si
  la fonctionnalité « jours restants » est construite ici).

#### Sprint Objectifs — Vue (NOUVEAU 2026-08-21)
- **Position** : **3ter** de l'ordre cible, **APRÈS** le sprint Workspace / DC.
- **Constat racine** : un utilisateur peut aujourd'hui **VOIR et TENTER
  D'ÉDITER des objectifs qui ne sont pas les siens** — le refus arrive au
  niveau du propriétaire (mismatch owner) et remonte sous forme d'erreur de
  permission, donc l'interface propose une action qu'elle aurait dû ne pas
  offrir.
- **Objectif** :
  - **Modèle de permissions vue/édition** : ses propres objectifs éditables ; le
    manager voit ceux de son équipe en **lecture seule**.
  - **Filtre de périmètre de vue** : ne présenter que ce que le rôle a le droit
    de consulter, au lieu de tout lister et d'échouer à l'écriture.
  - **UI propre** : l'action indisponible ne doit pas être proposée puis
    refusée.
- **Lien** : le moteur d'objectifs moderne (`/quotas/quotas/` →
  `bi/metrics/sales_metrics.py`) est la source unique depuis le Sprint C wiring ;
  voir TD-171 (retrait des vestiges legacy) et TD-175 (ambiguïté de vocabulaire
  `quotas` / `objectives`).

#### Sprint test (NOUVEAU 2026-08-21 — PRÉ-LAUNCH, DERNIER avant déploiement)
- **Position** : après la phase fonctionnelle, **avant le déploiement** (voir
  « 🚀 Jalon LAUNCH »).
- **Objectif** : **smoke PO de bout en bout de TOUTE la chaîne visible**, en une
  seule traversée : ligne produit + remise → valeur du deal → objectif personnel
  **et** métriques campagne → fraîcheur des cartes.
- **⚠️ Exigence d'environnement : AVEC REDIS.** Les deux couches de cache se
  court-circuitent en son absence (`campaign_views.py`, `bi/cache.py`), donc
  toute la moitié « fraîcheur » du Sprint C wiring est **inobservable** sans
  Redis — c'est précisément pourquoi ses tests assertent sur la clé de cache et
  non sur une péremption constatée. Un smoke sans Redis validerait à VIDE.
- **Contenu** : reprise groupée des smokes différés des sprints précédents, dont
  celui d'`expected_close_date` (voir Sprint Workspace / DC).

---

## Sprints planifiés — phase fonctionnelle

### S7b ✅ — Peaufinage vues Go-to-Market (Territory + Campaign)
- **Objectif** : cohérence et complétude des vues GTM (Territory + Campaign).
- **Branche** : `claude/views-inventory-audit-b4sjxe` (part de `main` 924a46a).
- **Ordre des commits** (décidé avec le PO) : recherche → delete → filtre
  drawer → multi-select → enrichissement cartes.

#### Commits FAITS et validés à l'écran
- **Commit 1 ✅** — recherche limitée à nom + owner + exécutant (les deux
  vues).
- **Commit 2 ✅** — retrait bouton edit ; delete individuel au hover (coin
  haut-droite, error light, `stopPropagation` pour ne pas rediriger).
- **Commit 3 ✅** — filtre entonnoir + drawer sur les deux vues, harmonisé
  et COMPLET (validé à l'écran).
  - Onglets Mine/My Team/All retirés des deux vues.
  - `owner_scope` dans le drawer (radio) — défaut par tier :
    individual→mine, manager→team, admin→all, ré-appliqué à chaque visite,
    chip supprimable (remplace le défaut neutre `all` décidé au commit 3 ;
    livré comme commit hors-plan, voir ci-dessous).
  - **Filtres Territory** : `owner_scope`, type (contact/account/both),
    owner (async), team (async, `owner__team` simple — pas de OR car
    Territory n'a pas d'exécutant).
  - **Filtres Campaign** : `owner_scope`, statut, type, territoire,
    exécutant (async), channel strategy (auto/email only), team (async, OR
    owner/exécutant), owner (async).
  - **Sélecteurs async** : `AsyncUserSelect` (existant) + `AsyncTeamSelect`
    (créé — wrapper `AsyncSelect` + `useGetTeams`).
  - **Bug corrigé au passage** : signature `onChange` de `AsyncUserSelect`
    `(event, user)`.
  - **Permission élargie INTÉGRÉE** (commit séparé, poussé et validé) :
    `teams.read` pour `individual` passe de `mine` à `client` (un AE peut
    LIRE toutes les équipes du tenant — read seulement,
    create/update/delete restent `none`).
  - **Tri par défaut** = `created_at desc`, sélecteur de tri abandonné
    (Territory conserve ce tri ; le tri de la liste Campaign est remplacé par
    la priorité de statut, voir commits hors-plan ci-dessous).
  - **Zéro filtre mort** (contrainte dure PO).
- **Commit 4 ✅** — DELIVERED, mergé sur main (PR #69, merge commit
  `bd063540`) — multi-select refait sur Territory ET Campaign.
  - **Machine à états du coin haut-droite des cartes**, unifiée sur les deux
    vues : repos → icône statut · hover → delete individuel · sélection →
    case à cocher (`is_system` / TARGETED restent inertes).
  - **Cluster Select icône-seule** calqué sur l'entonnoir (mirroring).
  - Sélection en palette error ; bande pleine largeur "N selected" retirée.
  - **Backend bulk-delete Campaign** : nouveau `CampaignBulkViewSet`
    (`/campaigns/bulk-delete/`) calqué sur `TerritoryBulkViewSet` (sync,
    partial/strict, max 500, `BulkOperationThrottle`, client-scoped,
    `ScopedPermission`), divergeant uniquement par la suppression explicite
    des activités liées AVANT les campagnes (`Activity.campaign` en
    `SET_NULL` les orphelinerait), invalidation cache sur campagnes +
    activités.

- **Commit 5 ✅ — enrichissement des cartes** (livré en 3 sous-commits, FAIT
  AVEC LE PO) :
  - **5a — comptes par territoire** : `ContactFilterService`, endpoint
    batché `/territories/counts/`, fix `opted_out`.
  - **5b — enrichissement des cartes** : Territory (comptes / couverture /
    équipe) ; Campaign (statut reflété par la date, attribution) ;
    correction du décalage de date DANS la carte ET dans l'en-tête du
    workspace.
  - **5c — carte Campaign** : barre de progression par statut + placeholder
    de zone objectif vide + alignement du footer.

#### Commits hors-plan (au-delà du plan initial — livrés et mergés)
- **Défaut `owner_scope` par tier** sur les drawers de filtre Territory +
  Campaign : individual→mine, manager→team, admin→all ; ré-appliqué à chaque
  visite ; chip supprimable. Expose `role_tier` sur les payloads `/me`, login
  et refresh ; corrige le défaut pré-existant `useOwnerScope` / accounts.
- **Même défaut par tier sur le filtre Decision Cycles.**
- **Tri par défaut de la liste Campaign** : priorité de statut (ACTIVE →
  PAUSED → DRAFT → COMPLETED → CANCELLED) puis `created_at` DESC, TARGETED
  épinglé en tête.
- **Chip « Email only » ✅** : la carte affiche un chip « Email only » à côté
  du chip de type de séquence quand `channel_override` de la campagne vaut
  `EMAIL_ONLY`, gaté sur OUTBOUND. `channel_override` exposé sur le serializer
  de liste ; libellé centralisé en export partagé `CHANNEL_LABELS` — l'étape
  de revue de création garde délibérément sa copie plus riche « Auto (per
  contact data) », divergence documentée sur la constante.

- **Validation** : chaque commit validé à l'écran (smoke) + tests avant de
  merger.

### Sprint ✅ — Cycle de vie des cibles de campagne (livré, 3 commits)
- **Objectif** : rendre les vues de campagne lisibles comme « qui me reste-t-il
  à relancer », refondre l'affichage de progression des cartes en conséquence.
- **Résolu autrement qu'anticipé** : les cibles en état final sont FILTRÉES des
  vues de chasing (pas retirées de la donnée). Conséquence : la barre de
  progression OUTBOUND (worked/total, S7b 5c) reste INCHANGÉE, et la carte
  TARGETED porte des COMPTES plutôt qu'une barre. (L'anticipation initiale —
  cibles retirées de la liste, barre remplacée par « N in chasing » — est donc
  caduque.)

**Commit 1 — onglet cibles = « qui me reste-t-il à relancer »** :
- Toggle binaire Active / All dans la toolbar propre de la table (défaut Active
  sur TARGETED, All sur OUTBOUND — la distinction n'a pas de sens en
  prospection).
- Lignes ordonnées par priorité de statut (in progress, pending, callback
  pending, paused, puis completed et stopped), nom du contact en départage.
- En-têtes de colonnes triables mais inertes sous tri manuel : réparés ; la
  priorité de statut est le tri par défaut.
- Action Reactivate RETIRÉE — elle régénérait toute la séquence depuis l'étape
  1, exactement ce que fait déjà l'enrôlement. Relancer une chasse terminée
  passe désormais par Add to campaign (qui re-chase déjà un contact en état
  final déjà présent) ; la méthode modèle `CampaignContact.reactivate()` reste,
  un test garde cette dépendance. Une ligne terminée n'affiche aucune action.
- L'arrêt étant désormais irréversible depuis cette vue, Stop demande
  confirmation en nommant le contact ET le compte.

**Commit 2 — cartes et playlist** :
- Carte TARGETED : reporte les contacts encore à relancer au lieu d'un compte
  de comptes.
- Cartes Territory : gros compte basculé sur la même disposition en ligne
  horizontale que les cartes Campaign (homogénéité).
- Tous les libellés de compte se pluralisent conditionnellement.
- Cartes d'activité de la playlist : nomment leur contact en 2e ligne
  (ACCOUNT — CONTACT) avec un +N défensif.
- L'accordéon « completed » ne montre plus les activités des séquences
  terminées, via un nouveau filtre opt-in `active_sequence` sur `ActivityFilter`
  (côté serveur, car cet endpoint est paginé).
- Revalidation centralisée dans un helper partagé `revalidateCampaignPlaylist`
  utilisé par stop, pause, resume, remove, enroll et complete — quatre d'entre
  eux ne revalidaient jamais l'accordéon, et complete portait une clé dont le
  `page_size` la faisait échouer au préfixe.

**Commit 3 — activités du jour sur la carte TARGETED** :
- La carte TARGETED reporte aussi les activités dues aujourd'hui, en réutilisant
  EXACTEMENT le critère du chip de la playlist (voir le suivi ci-dessous).

### Suivi — Playlist « today » : source unique (dette de refactor)
Le calcul « activités dues aujourd'hui » a désormais TROIS implémentations : la
dérivation JS dans `CampaignPlaylistTab` (`todayActivities`, qui pilote le chip
que voit le rep), le bucketing Python de `get_playlist`, et la nouvelle
sous-requête corrélée `_activities_today` sur le queryset de liste des
campagnes. **Le chip est la référence.**
- `get_playlist` LAGGE aujourd'hui la référence dans deux cas, chacun épinglé
  par son propre test nommé : une activité dont `scheduled_date` est null (son
  test est `if scheduled and scheduled <= today`, donc les nulls tombent en
  upcoming), et une activité sans `campaign_contact` (son `is_first_planned`
  exige un id de contact). Les deux sont comptées par le chip et l'annotation,
  pas par `get_playlist`. Aligner `get_playlist` sur la référence.
- Le vrai fix : extraire le bucketing today/upcoming/on_hold dans UN seul helper
  partagé consommé par `get_playlist`, l'annotation et (idéalement) le frontend
  — plutôt que trois règles parallèles. Refactor de service, délibérément hors
  scope quand la carte a été construite.
- `get_playlist` expose désormais `today_count` de façon additive, ce qui fait
  du test de parité un vrai garde-fou de drift ET ouvre la porte à supprimer la
  dérivation chip côté client, pour une source unique du nombre que voit le rep.

### S7c ✅ — Filtres de la liste Decision Cycles (construction)
- **Livré** : PR #90 (merge `1d61f56d`).
- **Objectif** : construire les facettes de filtre manquantes sur la vue
  liste DC. (La navigation Home « See all » / noms cliquables a été SÉPARÉE
  dans S7d — décision PO ; elle n'appartient plus à S7c.)
- **Rappel de l'audit** : la prémisse « filtres DC morts, le hook forwarde
  stage/status » était FAUSSE — les filtres n'étaient pas morts, ils
  n'EXISTAIENT pas (le drawer n'avait que Account, Status, Owner scope ;
  `buildUrlWithParams` portait des branches `stage`/`status` inertes). C'était
  donc une CONSTRUCTION de filtres, PAS une réparation.
- **Réalisé (6 sous-étapes)** :
  - **1a — dérivation du statut d'ÉTAPE en annotations SQL**, source unique ;
    le service Python la consomme et reste l'oracle de parité.
  - **1b — statut EFFECTIF du cycle** (outcome sinon état dérivé) + étape
    courante en SQL ; contrat du KPI `dc_cycle_state` préservé (la Home
    continue de l'appeler).
  - **2 — backend** : `DecisionCycleFilterSet` (status unifié, owner, team
    nommée, contact en union step+activité, `source_campaign`, produit),
    ordering des 8 colonnes, recherche (nom / account / owner / team,
    description retirée), module config `decision_cycles` source unique,
    serializer servant les annotations. N+1 TD-90 supprimé (compte de requêtes
    constant, prouvé).
  - **3 — frontend** : suppression de l'appel KPI par ligne de la liste,
    colonnes réordonnées et toutes triables, drawer 3 → 8 facettes avec chips
    supprimables, nettoyage des branches d'URL `stage`/`status` inertes.
  - **4a — DÉFAUT corrigé (repro rouge d'abord)** : `DecisionStep.is_current`
    lisait une colonne toujours à `NOT_STARTED`, donc désignait toujours le
    PREMIER step ; il alimentait la MAUVAISE étape courante aux pipelines deal
    health et prep call. Réaligné sur l'étape courante DÉRIVÉE (même définition
    que l'annotation).
  - **4b — suppression de la colonne morte `DecisionStep.status`**, de son
    index, de l'endpoint `update_status` (backend + helper front inutilisé) ;
    migration `0019`.
- **Décisions produit du sprint (VOIE A)** :
  - La dérivation d'état passe en SQL et devient la SOURCE UNIQUE : le DC n'a
    pas de colonne statut et son état change avec le temps SANS écriture (Q6
    interdit de le rafraîchir dans un GET).
  - Le filtre de statut couvre DEUX vocabulaires (`outcome` + état dérivé).
  - Stage filtrable comme ÉTAPE COURANTE dérivée, JAMAIS comme `steps__stage`.
  - Recherche SANS description.
- **Reporté** : le filtre PAR MONTANT de la liste DC (dépend d'un montant
  fiable) — repoussé au Sprint C (voir ci-dessous ; TD-124).

### Sprint B — Pages Overview
- **Objectif** : chaque élément (compte, DC, campagne, territoire, product)
  a sa page overview riche consommant le BI, avec édition.
- **Problématique** : les vues listes existent mais leurs destinations
  (overviews) sont pauvres ; le BI n'est pas exploité en profondeur par
  élément.
- **Solution** : à cadrer — définir le contenu d'overview par type
  d'élément (KPI pertinents, champs éditables).
- **Validation** : à définir. Frontière à clarifier avec S9 (UI Produit).

### S8 — Administration & Objectifs
- **Objectif** : poser les quotas et définir/suivre les objectifs de
  campagne.
- **Problématique** : la Home affiche déjà des quotas et objectifs NON
  configurables → la BI n'est pas vérifiable de bout en bout.
- **Solution** : UI de définition des quotas + des objectifs de campagne.
- **Déjà livré (S8a)** : le BRANCHEMENT du suivi des objectifs de campagne
  (avancement sur la carte + attribution par origine) — voir Sprints livrés.
  Reste ici : l'UI de DÉFINITION des quotas/objectifs et l'over-achievement.
- **Connexion cartes GTM** : l'avancement des objectifs sur les cartes GTM
  (zone préparée en S7b commit 5) — le suivi est branché (S8a) ; reste à
  connecter la DÉFINITION des objectifs ici.
- **Over-achievement (>100%)** : afficher le dépassement (ex "102%"),
  couleur warning dark (doré, palette standard) + icône étoile. À construire
  À LA FOIS sur les cartes ET sur la Home (cohérence).
  - **NOTE** : la Home aujourd'hui écrête à 100% (`goalGradient.js` clampe
    `remaining` et `pct`) — l'over-achievement est un comportement NEUF à
    créer des deux côtés.
- **Validation** : poser un quota/objectif → la Home le reflète.
- **Note** : candidat à remonter avant Sprint B (ferme une incohérence
  visible) — arbitrage PO en attente.

### Sprint ✅ — Corrections cycle de vie campagne (PR #98 + #99)
- **Objectif** : corriger le cycle de vie des campagnes (accordéon completed,
  statuts de séquence, enrôlement, plafonds). Absorbe et LIVRE l'ancien
  mini-sprint « Corrections workspace campagne » (3.1 accordéon completed →
  item A ; 3.2 bouton header → « Log Response »).
- **Livré** :
  - **Accordéon completed (item A / TD-126)** : OUTBOUND montre TOUT ; TARGETED
    masque les séquences finies.
  - **`NO_ANSWER` en fin de séquence → `COMPLETED`** (au lieu de `STOPPED`).
  - **Statut de `CampaignAccount` re-dérivé au re-chase** d'un contact TARGETED
    (garde anti-sur-correction ; OUTBOUND intact).
  - **Retrait de la barre bulk contacts** (onglet Targets) + nettoyage des
    `CampaignAccount` orphelins. Endpoints bulk backend conservés DORMANTS
    (voir TD-129).
  - **Socle `sequence_run`** : le re-chase incrémente le run, les activités
    sont estampillées (IMMUABLE) ; l'accordéon completed = run COURANT
    seulement ; les runs précédents restent conservés en base.
  - **`activities_count`** : correction du « 0 mensonger » (collision prefetch
    `ON_HOLD`).
  - **Feedback d'enrôlement honnête** sur les deux modales (plus de faux succès
    ni de rouge à tort ; warning pour « déjà actif » et « aucun contact
    joignable » ; `unreachable_count` fiable dans tous les modes — voir TD-128
    pour le cas MIXTE).
  - **Header workspace** : « Log Response » action principale (bouton plein) ;
    « Pause » au dropdown sur OUTBOUND ACTIVE.
  - **Plafonds** : 50 comptes/campagne (bruts à la création OUTBOUND / actifs à
    l'ajout manuel) ; 10 OUTBOUND + 1 TARGETED actives par user. Constantes
    dans `campaigns/constants.py`.

### Mini-sprint ✅ — Fiabilisation campagne + territoire (PR #100)
- **Livré** :
  - **C1** : retrait UI de la barre de progression playlist (le calcul
    `completion` est conservé pour l'Overview).
  - **C2** : `accounts_count` exclut les comptes orphelins (0 contact).
  - **C3** : invariant « TARGETED jamais terminée » durci au niveau MODÈLE
    (pas de `CheckConstraint` DB — choix assumé, voir TD-130).
  - **C4** : création de territoire au nom dupliqué → erreur 4xx élégante
    (scope tenant).
  - **Suppression de territoire** : bloquée si campagne ACTIVE liée ; cascade
    DC-safe si uniquement des campagnes non-actives (mono-territoire → campagne
    supprimée ; multi-territoires → détachement) ; transaction ATOMIQUE.
  - **Cleanup** : dédup `mark_activities_generated`, magic numbers →
    `constants.py`, code mort prouvé retiré.

### Sprint ✅ — Enrichissement carte activity (front) (PR #120, 2026-08-12)
- **Objectif** : rendre la carte d'activité (playlist) actionnable et lisible.
- **Périmètre** :
  - Coordonnées CLIQUABLES selon le canal de l'activité : `tel:` sur un Call,
    `mailto:` sur un Email, lien LinkedIn sur une activité LinkedIn.
  - Micro-libellé « LinkedIn Message » → « LinkedIn ».
  - Correction du CTA PARASITE « Account stopped — All contacts stopped — no
    successful outcome » affiché à tort sur des activités ACTIVES (voir TD-145).
- **Livré (FIL A)** :
  - Backend : `phone_number` + `linkedin` ajoutés au payload playlist
    (`ActivityListSerializer.get_contacts`), à côté de l'`email` déjà présent.
  - Front : coordonnée du canal rendue CLIQUABLE sur la carte playlist
    (Call→`tel:`, Email→`mailto:`, LinkedIn→lien externe nouvel onglet) ;
    `stopPropagation` pour ne pas déclencher la navigation de la carte ;
    coordonnée absente → rien, AUCUN fallback (verrouillé par tests sur les 3
    canaux).
  - Backend : relabel du type LinkedIn « LinkedIn Message » → « LinkedIn » à la
    source (enum `ActivityType`) + 2 migrations d'état no-op SQL (activities,
    signals).
  - Front : copie vivante `ACTIVITY_TYPE_LABELS` alignée sur « LinkedIn » ; clé
    de locale morte `activity-type-linkedin` supprimée.
- **FIL B (CTA parasite « Account stopped… »)** : SORTI de ce sprint, renvoyé à
  **S13 — Intention & Prep Call** (cause racine = modèle d'intention, pas un
  correctif d'affichage local ; voir TD-145).

### Sprint Timeout ✅ — Régression d'emballement de requêtes (perf backend, LIVRÉ)
- **Objectif** : corriger une RÉGRESSION de dégradation progressive en
  navigation (latence croissante → `408`).
- **Cause (hypothèse initiale INVALIDÉE)** : ce n'était PAS une boucle de
  revalidation SWR côté front (piste de départ), mais le **coût unitaire
  backend (N+1)** de plusieurs endpoints, dont la latence croît avec le volume.
  Audit → 5 causes racines, corrigées chacune avec repro rouge/verte CHIFFRÉE en
  requêtes SQL. Dette liée : **TD-147** (RESOLVED partiel).
- **Livré (5 fils, tous mergés main)** :
  - **Fil 1 — Batch KPI `dc_cycle_state`** : groupage (`bulk_compute_fn` +
    `get_bulk_summaries`) + `default_period='all'` + mémoïsation fiscale.
    **44 req (11 cycles) → 3, pente 0.**
  - **Fil 2 — Objectifs de campagne** : calcul groupé au point PARTAGÉ
    (`calculate_objective_values`), 3 chemins (dashboard / detail / KPI).
    Pente +1/objectif → +0,5, plafond 4. **dashboard 34→32, detail 15→13,
    KPI 9→7.**
  - **Fil 3 — Dashboard campagne** : groupage exécuteurs (agrégation + `in_bulk`)
    + dédup COUNT (GROUP BY réutilisés). **31→14 (2 exécuteurs), pente 6→~0.**
  - **Fil 4 — Liste client-accounts** : annotation `Count`
    (`users_count`/`organizations_count`) au lieu du N+1 sérialiseur.
    **Pente 1/ligne → 0.**
  - **Fil 5 — Sérialiseur d'activité** (`/module-activities/` + `/by-account/`) :
    prefetch/select_related + Prefetch filtré (`get_contacts`) + annotations.
    **~185 req (page 20) → ~15, pente ~9/activité → 0.** LE plus gros N+1 du
    sprint (sérialiseur partagé par 6 actions).
- **Vérification smoke PO (réel)** : tous les endpoints corrigés répondent < 1s en
  navigation réelle (batch 347ms, dashboard 278ms, module-activities 301ms,
  playlist 272ms) ; **0 timeout `408`** post-fix. `company-accounts` mesuré rapide
  (104-254ms) → AUCUN fil nécessaire (faux problème). Prod-ready perf atteint hors
  reports ci-dessous.
- **Reports (sortis du scope, renvoyés à des sprints dédiés)** :
  - `territory_progress_by_team` (7,4s froid + double-comptage multi-territoires)
    → **Sprint « Finalisation Home + performance »** (refonte métrique par
    personne). Dette : **TD-153**.
  - `/decision_cycles/steps/` (3,3s, possiblement MORT) → **Sprint dédié
    decision_cycles/steps** (vérifier consommateurs avant tout). Dette : **TD-154**.
  - Autres dettes ouvertes du sprint : playlist non bornée (**TD-155**),
    asymétries re-chase (**TD-156**), doublon param front `territory_id`
    (**TD-157**), doublons de requêtes + cache trop large (**TD-158**).

### Sprint « Finalisation Home + performance » (APRÈS les sprints Signaux)
- **Objectif** : finaliser la Home par TYPE d'utilisateur et refondre la métrique
  de couverture (perf + justesse).
- **Périmètre** :
  - **Cadrer le contenu Home par persona** : utilisateur individuel = INCITER À
    AGIR (ce qu'il doit faire) ; manager = AVANCEMENT de l'équipe.
  - **Découpage en ONGLETS** (À faire / Avancement / Objectifs) pour un chargement
    progressif (ne pas tout charger d'un coup).
  - **REFONTE de la métrique de couverture** : passer de « par territoire » (lente
    7,4s + double-comptage des comptes présents dans plusieurs territoires) à
    « par personne » (comptes du user touchés cette période / total). Le
    **territoire redevient un regroupement STRATÉGIQUE, pas une base de calcul
    BI**. Attention perf des requêtes BI. Relié à **TD-153** (branche
    `perf/territory-coverage-snapshot` gardée, porte la repro rouge).

> **↪ Recadrage (réorg 2026-08-15) — rattaché à « Finition & vues » (#6 de
> l'ordre cible), volet « vues selon le TIER ».** Note : un manager n'a pas les
> mêmes commandes IA qu'un commercial. Fiche conservée telle quelle.

### Mini-sprint — Cap 3 contacts/compte/campagne (backend d'abord, APRÈS perf)
- **Objectif** : plafonner à **3 contacts ENRÔLÉS par compte par campagne**.
- **Périmètre** :
  - S'applique **OUTBOUND ET TARGETED**. Targeted → plus de « tout le compte » :
    on CHOISIT jusqu'à 3 contacts.
  - **Existants NON touchés** (pas de rétroactif).
  - **Message ORANGE (règle métier)** : « Max 3 contacts par compte par
    campagne ». Le blocage UI des modales est renvoyé au **Sprint UI**.
  - **Constante CENTRALISÉE** (miroir des caps campagne, pas de magic number).
- **Prérequis** : **audit de structure OBLIGATOIRE avant code** — le cap doit
  s'appliquer sur TOUS les chemins d'enrôlement (bulk, unitaire, targeted,
  outbound). Note : borne davantage le volume playlist (**TD-155**).

### Sprint — decision_cycles/steps (mort ou vivant AVANT d'optimiser)
- **Objectif** : trancher le sort de `/decision_cycles/steps/` (lent 3,3s et
  possiblement MORT), puis agir.
- **Périmètre** :
  - **D'ABORD vérifier les consommateurs** (front + back). La forme cycle-scopée
    a des consommateurs vivants ; la forme LISTE-TOUT n'en a aucun connu.
  - Si **mort** → suppression. Si **vivant** → optimisation (`derive_bulk` au lieu
    de `derive()` par step, prefetch des activités, éviter `.count()`/`.exists()`
    par step).
  - **Ne PAS optimiser avant d'avoir tranché mort/vivant.** Dette : **TD-154**.

> **↪ Recadrage (réorg 2026-08-15) — regroupé dans le bloc « Modèle Decision
> Cycle » (#3 de l'ordre cible), avec le Sprint C — Produit & Finance.** Fiche
> conservée telle quelle ; regroupement seulement.
>
> **✅ LIVRÉ — voir la fiche « Sprint DC-step élagage ✅ » plus haut** (branche
> `feat/dc-step-elagage`). Question mort/vivant TRANCHÉE : l'endpoint est **VIVANT**
> (pickers d'étape via `?cycle_id=`), donc **conservé, ni supprimé ni optimisé**.
> Le sprint a fait l'ÉLAGAGE UI (suppression de la page per-step workspace + reroutes
> vers le DC workspace timeline), PAS la perf : la lenteur 3,3s reste ouverte dans
> **TD-179** (distincte de **TD-154**, désormais RESOLVED).

### Sprint — Doublons de requêtes + efficacité cache (front/back) — ⏸️ REPORTÉ (pré-launch)
- **Statut (décision PO)** : **REPORTÉ / à faire AVANT déploiement** (pré-launch,
  pas supprimé de la roadmap). La perf actuelle est prod-ready (tout < 1s), mais
  l'audit a PROUVÉ un vrai défaut d'archi cache à corriger avant la montée en
  charge multi-tenant. **Audit LIVRÉ** (annoncé en **TD-158**) ; résultats tracés
  en **TD-159** (principal — ⚠️ invalidation BI TENANT-WIDE, à faire avant
  déploiement) + **TD-160/161/162** (doublons front, priorité faible/cosmétique).
  **Le prochain jalon actif reste le Sprint C** (ci-dessous).
- **Objectif** : supprimer les requêtes dupliquées en navigation et resserrer
  l'invalidation de cache.
- **Périmètre (décisions produit DÉJÀ prises)** :
  - **Requêtes dupliquées** en navigation (visibles dans l'onglet Network) → dédup.
    L'audit a montré que les vrais doublons simultanés sont déjà dédupliqués par
    SWR ; le gisement réel est la revalidation au remontage (**TD-160**).
  - **Invalidation de cache trop large** : aujourd'hui chaque écriture invalide
    les KPIs de TOUT le tenant → cache souvent froid. Cible : **invalidation
    CIBLÉE par objet** (pas par tenant) + **dédup des KPIs partagés**. Défaut
    d'archi prouvé et détaillé en **TD-159** (à faire avant déploiement).
  - **Rafraîchissement AUTO conservé** (pas de refresh manuel).
  - **Audit LIVRÉ.** Dettes : **TD-158** (umbrella), **TD-159** (principal),
    **TD-160/161/162** (secondaires front).

### Sprint C — Produit & Finance de bout en bout (backend d'abord)
- **Objectif** : le produit et la finance qui FONCTIONNENT de bout en bout,
  backend d'abord (avant tout peaufinage UI).
- **Périmètre** :
  - Créer un produit avec plusieurs TYPES DE PRICING.
  - Refléter le produit et son pricing sur le Decision Cycle.
  - En sortir du reporting : le montant doit être fiable et exploitable.
  - Réconcilier `DecisionCycle.estimated_value` (saisi à la main) et le
    roll-up produit (`Σ deal_products`) — décider lequel fait foi (roll-up
    dérivé recommandé). Renvoi explicite à **TD-74** (pas de contrainte 0-100
    sur `discount_percent`) et **TD-75** (réconciliation `estimated_value` vs
    roll-up).
  - Gérer la DEVISE et les unités du montant total : stockage, affichage,
    saisie — aujourd'hui non gérées.
  - **Débloque `PIPELINE_VALUE` / `REVENUE_WON`** (objectifs de campagne ET
    quotas personnels), aujourd'hui bloqués à 0 : leur calcul somme
    `DecisionCycle.estimated_value`, qu'AUCUN chemin runtime ne peuple — le
    montant saisi va dans `DealProduct.line_total` sans roll-up vers
    `estimated_value`. Ces deux métriques dépendent donc de la réconciliation
    montant de ce sprint (voir **TD-75**).
  - **Renommer le LIBELLÉ d'affichage « Revenue Won » → « Deals Won »** (ou
    « Won Value ») : le terme actuel est trompeur. C'est le LIBELLÉ, PAS le nom
    technique de la métrique (`REVENUE_WON` inchangé). Peut aussi se faire au
    sprint UI (voir TD-127).
- **Conséquence pour la liste DC** : une fois le montant fiable, la colonne
  Amount (qui lit `estimated_value` aujourd'hui) bascule sur la SOURCE DE
  VÉRITÉ, et le FILTRE PAR MONTANT reporté de S7c (TD-124) devient
  constructible sans mentir.

> **↪ Recadrage (réorg 2026-08-15) — absorbé dans le bloc « Modèle Decision
> Cycle » (#3 de l'ordre cible), avec le Sprint decision_cycles/steps.** Fiche
> conservée telle quelle ; regroupement seulement.

### S9 — UI Produit (peaufinage / homogénéisation / UX — APRÈS Sprint C)
- **Objectif** : peaufinage UI, homogénéisation et UX de la ligne de produits
  + onglet Product Financial, une fois le backend produit-finance solide
  (Sprint C).
- **Paradigme** : backend d'abord (Sprint C), UI en dernier — S9 ne construit
  plus le backend produit-finance, il l'HABILLE. (Renvoi TD-74/75 traité au
  Sprint C.)
- **Problématique / Solution / Validation** : à cadrer. Frontière avec
  Sprint B (overview produit) à clarifier.

### S10 — Tech Catalogue (conception approfondie)
À cadrer.

> **↪ Recadrage (réorg 2026-08-15) — S10 = #2 de l'ordre cible.** Le modèle
> actuel est trop complexe → RETIRER le modèle et accepter TOUS les signaux
> tech SANS vérification (« Salesforce » écrit tel quel). Enjeux : éviter les
> doublons AVEC LE SYSTÈME LE PLUS SIMPLE POSSIBLE + FILTRAGE des technologies.
> Revérifier le bug « HubSpot n'apparaît jamais » (lié à l'anti-doublon
> actuel). Contenu existant « À cadrer » conservé.
>
> **✅ LIVRÉ — voir la fiche « Sprint S10 ✅ » plus haut** (branche
> `feat/s10-techstack-signal`). NB : le bug « HubSpot n'apparaît jamais » a été
> ÉCARTÉ par le PO au cadrage et n'a pas été traité ; l'audit S10 l'a rattaché à
> la classification du prompt (tech vendeur vs prospect), pas au mapping
> d'extraction — cf. TD-64, qui reste OPEN et relève du bloc « Commandes IA ».

### S11 — Signals UX (+ TD-29)
- **Objectif** : améliorer l'UX des signaux, réponse aux notes de signal.
- **À tester ici (groupé avec les vérifications IA)** : smoke sur VRAIE sortie
  LLM du fix `is_current` (S7c 4a) — prep call / deal health affichant la
  bonne étape courante. Le fix est prouvé par repro rouge/verte + 66 tests IA,
  mais le smoke sur sortie LLM réelle a été REPORTÉ à ce sprint (TD-123).
- À cadrer.

### S12 — Prompts (+ intégration HubSpot)
- **Objectif** : couche prompts + connexion HubSpot.
- À cadrer.

> **↪ Recadrage (réorg 2026-08-15) — S12 DÉPLACÉ dans le bloc « Commandes IA »
> (#4 de l'ordre cible).** S12 n'est plus un sprint séparé en amont : sa partie
> « Signaux Tech stack (prompt) » devient une sous-étape du sprint Commandes IA
> (voir « ## Ordre cible des sprints à venir + jalon LAUNCH »). Toute mention
> existante de S12 est CONSERVÉE ici ; seul ce cadrage est ajouté.

### S13 — Intention & Prep Call
- **Objectif** : objectif d'activité + approche stratégique de campagne +
  Prep Call multi-canal.
- **Problématique** : ces trois éléments répondent à une seule question —
  pourquoi je fais cette activité et comment je la prépare. Les construire
  séparément = retrofit.
- **Solution** : à cadrer, groupés. Après S12 (la génération multi-canal
  en dépend).
- **Validation** : à définir.
- **Ciblage & sélection des contacts** (le cap contacts n'est PAS un
  sprint autonome — décision PO ; il est absorbé ici comme conséquence
  d'un vrai sujet ciblage/sélection) :
  - Constat : pour une campagne OUTBOUND sur territoire, on ne choisit à
    aucun moment QUELS contacts du compte cibler → sélection aujourd'hui
    implicite/arbitraire.
  - À construire, avec une vraie logique UX (à cadrer) :
    * un FILTRE de ciblage à la création de campagne (ex. département —
      critères à définir) pour cibler les bons profils dans chaque compte ;
    * une SÉLECTION STRATÉGIQUE des contacts (selon la campagne / le
      meilleur contact à joindre), PAS un choix arbitraire des 3 ;
    * un CAP max de contacts enrôlés par compte par campagne, comme
      CONSÉQUENCE de la sélection (pas un sujet isolé). Note : ATTENTION
      PERFORMANCE — un nombre non borné de contacts par compte fait grossir
      la playlist et les enrôlements.
  - Décisions PO DÉJÀ FIGÉES (input pour le cadrage, à ne pas reperdre) :
    * cap = 3 contacts ENRÔLÉS par compte par campagne ;
    * s'applique OUTBOUND + TARGETED ;
    * TARGETED : plus de « ajouter tout le compte », on choisit jusqu'à 3
      contacts ;
    * enrôlements existants au-delà de 3 non touchés (pas de rétroactif) ;
    * comportement SKIP-AND-ENROLL-REST (enrôler jusqu'à 3, ignorer le
      surplus) ;
    * message ORANGE (règle métier, pas rouge) « max contacts reached per
      campaign » ;
    * comptage sur les enrôlements ACTIFS (un retrait libère un slot) ;
    * constante N centralisée dans `campaigns/constants.py` (pattern des
      caps existants) ;
    * blocage UI (retrait « tout le compte » + sélection bloquée au-delà
      de 3) → volet UI.
  - Point technique établi par audit (à réutiliser le moment venu) : le
    POINT CENTRAL pour poser le cap est la création de `CampaignContact`
    (tous les chemins d'enrôlement le traversent — bulk, unitaire,
    targeted, « tout le compte »). L'audit de structure enrôlement a déjà
    été fait ; le resservir au cadrage S13.

> **↪ Recadrage (réorg 2026-08-15) — S13 = #1 de l'ordre cible.** Cadrer
> l'OBJECTIF dans chaque activité : OUTBOUND → objectif issu de la CRÉATION de
> la campagne ; TARGETED → objectif ajouté à l'ajout d'un TARGET ; Decision
> Cycle → objectif qui ÉVOLUE selon l'étape. But : nourrir l'IA. Techno à
> concevoir, LE PLUS SIMPLE POSSIBLE. Ce sprint ABSORBE le ciblage/sélection
> des contacts ET le PLAFONNEMENT contacts par compte/campagne — la référence
> existante ci-dessus (« Ciblage & sélection des contacts », décisions PO
> figées, cap = 3) est CONSERVÉE telle quelle.

### Sprint — Sales Cycle Snapshot / Deal History (APRÈS S13)
- **Objectif** : à la clôture d'un cycle (win/loss), figer un snapshot
  immuable de tout son parcours.
- **Problématique** : la donnée opérationnelle vit et change ; reconstruire
  l'historique après coup est fragile ; le corpus d'entraînement exige des
  photos fidèles et permanentes.
- **Solution** : snapshot JSON structuré à la clôture — origine (campagne/
  inbound), signaux, étapes, décisions, résultat. Format compact et
  non-redondant MAIS sans perte d'information causale. Double usage :
  retrieval immédiat (alimenter les prompts de prep call avec des cycles
  similaires gagnés) + corpus d'entraînement futur.
- **Validation** : un cycle clôturé produit un snapshot complet et
  relisible ; un prep call peut être enrichi de cycles similaires.
- **Note** : à implémenter seulement quand les structures commerciales sont
  stables (post-S13) pour éviter des snapshots incohérents entre eux.

### S14 — Deal Health · S15 — Campaign UX
À cadrer.

### Sprint Filtres — Filtres & recherche transverses (AVANT le sprint UI)
- **Ordre** : INVERSÉ avec le sprint UI — les Filtres passent AVANT l'UI.
  Raison PO : tout doit être fonctionnel avant d'attaquer l'UI.
- **Objectif** : filtres & recherche transverses sur l'ensemble des vues.
- **Note** : le modal de création Territory est en réalité un sujet UI
  (filtres avancés), traité dans le sprint UI ci-dessous — pas ici.
- **Input produit — critères candidats du modal de définition Territory**
  (à AJOUTER quand le backend les évalue — jamais de filtre mort, c.-à-d.
  un critère posé côté company que le backend ignore) :
  - **company profile** (`company_size`, multi-select) — NOTE :
    `company_size` est DÉJÀ évalué par `AccountFilterService` aujourd'hui,
    donc peut atterrir plus tôt si souhaité.
  - **techstack** (`has_tech_stack`, multi-select) — déjà évalué (sous-
    requête `Exists`).
  - **signal** (dimension + what, multi-select) — BLOQUÉ : `has_qualification`
    / `signals_since_days` sont des stubs/no-ops dans `AccountFilterService`
    aujourd'hui, en attente de ce sprint. L'ajouter au modal avant le
    support backend = filtre mort.
  - **filtre DC** : « without active DC » — nécessite un audit backend ;
    pas clair que le `filter_definition` supporte encore un critère DC.
  - Cadrage : ces critères sont l'input du sprint Filtres, construits
    backend + UI ENSEMBLE, zéro filtre mort.

### Sprint UI — Homogénéisation UI (EN DERNIER de la phase fonctionnelle)
- **Objectif** : homogénéisation UI + FINIR TOUS LES MODALS.
- **Inclut le modal de création Territory** : filtres avancés (Tech Stack,
  Buying Process, Signals, Owner) — actuellement bridé avec un placeholder
  "coming soon". Les signaux sont mûrs, pas de blocage de dépendance.
- **Audit des opérations bulk (cohérence transverse)** : auditer TOUTES les
  opérations bulk existantes à travers les modules et garantir un
  comportement homogène, en particulier la gestion d'erreur (abort 403 au
  niveau requête via `get_objects_for_bulk` vs skip-and-report partiel 207 ;
  sémantique strict/partial). L'alignement bulk-delete Territory/Campaign a
  confirmé un même comportement 403 au niveau requête ; les autres bulk ops
  (ex. campaign account bulk-add / bulk-remove) N'ONT PAS été vérifiées pour
  la même cohérence.
- **Polish responsive** : sur écrans étroits, les boutons-icônes Select et
  Filtre des toolbars de liste Territory/Campaign s'empilent verticalement /
  se désalignent. Restaurer la gestion élégante des tailles utilisée ailleurs
  dans l'app.
- **Cartes Targeted en `secondary`** : harmoniser la couleur des cartes de
  campagne Targeted vers `secondary` (rattaché ICI à l'homogénéisation UI, PAS
  un sprint neuf).

### Sprint Gestion d'erreur — revue BE + FR de bout en bout (APRÈS l'UI, DERNIER avant Go-Live)
- **Position** : après le sprint UI et TOUTES les fonctionnalités ; dernier
  sprint avant le durcissement Go-Live. PAS un volet de S9. Décision PO :
  refaire les messages d'erreur avant que les endpoints et les écrans soient
  stables reviendrait à les refaire DEUX fois.
- **Objectif** : revue COMPLÈTE de la gestion d'erreur, backend ET frontend,
  de bout en bout — pas un patch ponctuel.
- **Backend** :
  - Les 500 ne doivent JAMAIS exposer de détail technique au client.
    Aujourd'hui `handle_exception` renvoie `str(exc)` brut — un utilisateur a
    vu « column decision_steps.status does not exist » avec le SQL Postgres
    complet (bug réel, filtre produit de la liste DC, corrigé en PR #92).
    Rattache **TD-118** (fuite `str(exc)` sur les 500) ici.
  - Cohérence des messages via `core/error_messages.py` : centralisation, plus
    de classes de messages au niveau module. Rattache **TD-99**
    (`CampaignModuleErrorMessages` dévie de la convention) ici.
- **Frontend** :
  - Revue des handlers d'erreur — `displayError`, `errorHandler`,
    `formErrorHandler`, le mapping des statuts — pour que l'utilisateur
    reçoive un message intelligible, JAMAIS un dump technique.
- **Validation** : aucun 500 n'expose de détail technique au client ; messages
  cohérents via `core/error_messages.py` (plus de classes de messages au
  niveau module) ; un message intelligible côté frontend pour chaque classe
  d'erreur.

---

## Notes d'anticipation (à garder en tête, pas à coder maintenant)
- **Gestion des fuseaux horaires selon la localisation du user** — sujet
  transverse. Déjà effleuré au S6 avec le bug UTC/local de la date callback
  (D3a). L'app va servir des users dans différentes timezones, il faudra une
  stratégie cohérente (stockage UTC, affichage local, saisie de dates dans
  le fuseau du user). À cadrer proprement à un moment, probablement avant ou
  pendant le Go-Live.

---

## Étape Data Structure Review (pré-Go-Live)
- **Objectif** : audit complet de la structure de données sur toute la
  chaîne commerciale (prospection via campagnes → construction de
  territoire → cycle de vente → signature).
- **Problématique** : les erreurs de structure d'aujourd'hui sont des trous
  irréparables dans le corpus d'entraînement de demain. Plus on accumule de
  donnée saine tôt, mieux c'est.
- **Solution** : passe globale de vérification — résultats bien capturés,
  causalité tracée, liens non perdus. Vérifie notamment la complétude du
  Sales Cycle Snapshot.
- **Validation** : la donnée accumulée est jugée saine et complète pour
  l'entraînement.

---

## Phase Go-Live (tout à la fin, une fois le fonctionnel terminé)

### Cleanup (prérequis technique — voir TECH_DEBT.md)
- **build-health ✅ FERMÉ (PR #102, TD-18 résolu)** : `next build` exit 0, 23
  routes. Le diagnostic initial (« cassé Linux, OK macOS — divergence
  d'environnement ») était FAUX : le build cassait sur LES DEUX OS, pour deux
  causes qui se masquaient (Linux : `react-csv`/`@dnd-kit/core` non résolus ;
  macOS : 5 erreurs ESLint `rules-of-hooks`), le tout masqué par un
  `node_modules` parasite à la racine (sorti du projet). Corrections vs les
  cibles annoncées ici : casses d'import (`businessData`, `UserCSVValidation`)
  TRAITÉES ; `react-csv` et `@dnd-kit/core` DÉCLARÉS ; **`@dnd-kit/sortable` et
  `@dnd-kit/utilities` n'étaient importés NULLE PART — cible inexacte, retirée** ;
  `@mui/x-tree-view` **`^6`→`^8`** (API `RichTreeView`, PAS `^7` comme annoncé).
- **Reste NON traité** : dette S6 **TD-99 / 101 / 102 / 103** (⚠️ TD-97 est
  déjà RESOLVED — retiré de la liste) + la dette frontend neuve de ce sprint
  (**TD-132 → TD-140**, voir TECH_DEBT.md). Le volet build-health du Cleanup
  est fermé ; le reste du Cleanup ne l'est pas.

### G1 — Sécurité (rapprochement SOC 2)
Durcissement avant exposition client : permissions, isolation multi-tenant
bout-en-bout, secrets, headers, logs, chiffrement. Pas la certif SOC 2, s'en
rapprocher au maximum. Prérequis absolu avant tout accès client.
- **Durcissement permissions & modules** :
  - **Supprimer les modules FANTÔMES** : plusieurs modules ont été
    anticipés dans les settings/config alors qu'ils n'existeront pas.
    Auditer `config.MODULES` et SUPPRIMER uniquement ces entrées
    inexistantes (sans backend réel derrière).
  - **GARDER les modules RÉELS-mais-inactifs** — à NE PAS confondre avec
    les fantômes ci-dessus, ni supprimer par erreur : `sales_quotas`,
    `sales_plans`, `sales_milestones` back de VRAIS KPI BI et s'activent au
    sprint Admin & Objectifs. Ils sont réels, juste pas encore activés :
    les conserver.
  - **Auditer le fail-open des modules NON LISTÉS (inventaire élargi)** : un
    module absent de `config.MODULES` fail-open aujourd'hui vers le scope
    `client` (`checks.py:52-55`). L'audit établit que le sujet dépasse les
    « fantômes vs réels-inactifs » : `config.MODULES`
    (`permissions/config.py:32-48`) ne liste PAS `signals`, `ai_pipelines`,
    `tech_catalog`, `product_catalog`, `notifications`, `organizations`,
    `sales_quotas`, `sales_plans`, `sales_milestones`. Pour ces modules, la
    matrice du registry ET leurs `action_policies` sont donc CONTOURNÉES au
    portail ; l'enforcement se réduit à l'isolation tenant. Évaluer le
    fail-CLOSED comme défaut sécurisé → changement de permissions transverse,
    repro + audit d'impact dédiés, PAS un simple flip de config. Précision de
    chiffrage : enregistrer `signals` serait quasi neutre (registry = `client`
    partout), mais `ai_pipelines` a update/delete = `none` pour tous les tiers
    → l'enregistrer CHANGERAIT le comportement.
  - **Général** : garantir que tout le chemin permissions/sécurité est
    solide, sans bug et propre (pas de branche morte, pas de fail-open
    silencieux) — readiness SOC-like.
- **Scellage du modèle de permissions (en UNE passe, pas au coup par coup —
  c'est le rafistolage par petits bouts qui a créé l'incohérence actuelle)** :

  1. **Deux couches de décision concurrentes.** Le registry de permissions
     est tier-aware et correct (ex. `campaigns_registry.py:28-32` — `update` :
     admin=client, manager=team, individual=mine, conforme à la règle
     produit). MAIS les `action_policies` des viewsets portent une chaîne de
     scope PLATE et tier-aveugle qui CONTOURNE le registry. Dans
     `campaign_views.py:139-144`, les cinq actions de cycle de vie
     (start/pause/resume/complete/cancel) sont toutes
     `{'crud':'update','scope':'mine'}` — donc un manager ne peut pas mettre
     en pause une campagne détenue par un AE de sa propre équipe :
     `get_queryset` résout le scope `mine` (`mixins.py:370` ; l'admin est
     bumpé à `client` en 373-380 mais le manager n'est PAS bumpé à `team`),
     l'objet sort du scope et `get_object` lève un 403. Origine : commit
     `85ec926` (3 juin 2026), inchangé depuis — ça n'a JAMAIS marché, ce
     n'est PAS une régression des commits de permissions S7 (vérifié au
     `git blame` ; `30bc820` et le travail owner_scope ne touchent que le
     scope de LECTURE). Contournement en attendant : l'édition PATCH de la
     campagne marche (normalisée en `update` → registry → team → autorisé) ;
     seules les transitions de cycle de vie sont bloquées. Contrainte de
     fix : le `scope` d'action-policy est une chaîne unique et ne peut pas
     exprimer manager=team + individual=mine ; et SUPPRIMER la clé scope est
     dangereux car un scope de policy absent vaut `none` par défaut
     (`mixins.py:370`) → queryset vide. Le fix doit router ces actions vers le
     scope `update` tier-aware du registry. Question ouverte à trancher au
     fix : sous le scope `team`, un manager voit-il toujours ses PROPRES
     objets ? (l'appartenance équipe est un FK manager sur Team + `team_id`
     sur les membres ; un team-scope résolu comme « users dont le `team_id`
     est dans mes équipes gérées » pourrait exclure le manager lui-même — une
     régression que le fix doit éviter.) À élargir au fix : auditer si
     D'AUTRES modules ont aussi des `action_policies` plates masquant leur
     registry — le problème n'est peut-être pas limité aux campagnes.
     **Réponse (audit)** : OUI, le défaut n'est PAS propre aux campagnes. 21
     déclarations d'`action_policies` recensées, dont au moins DEUX
     ÉLARGISSENT au-delà du registry — `activities.create_with_entities` =
     create/`client` alors que le registry dit individual=mine
     (`activities/views/views.py:98`), et `decision_step.update_status` =
     update/`client` alors que le registry dit manager=team / individual=mine
     (`decision_cycles/views/views.py:940`).

  2. **Doctrine admin vs superuser (à trancher ; le code fait aujourd'hui
     l'INVERSE).** Intention : séparer le DROIT (ai-je le droit de faire
     l'action) du SCOPE (sur quels objets).
     - admin (rôle métier tenant) : droit sur tout, scope = tout (le client
       entier).
     - superuser (compte plateforme/technique) : droit sur tout, mais
       scope = mine — il ne doit PAS agir sur la donnée d'un tenant comme s'il
       la possédait.
     Rationale : dans une petite équipe, la personne qui configure l'app est
     aussi vendeuse — elle a besoin des droits admin pour configurer, mais
     quand elle travaille ses comptes elle agit dans son propre périmètre.
     Aujourd'hui : `is_superuser` résout vers le tier admin et est bumpé au
     scope `client` (`mixins.py:373-380`, et la résolution rôle→tier) — donc
     le superuser est traité comme un admin plein-périmètre. Changer ça touche
     la résolution de permissions sur TOUS les modules et est sensible côté
     sécurité : nécessite son propre audit d'impact et des tests de
     non-régression, pas un tweak de config.

  3. **Hiérarchie d'équipe.** Le scope `team` résout déjà l'équipe directe
     PLUS les membres de toutes les équipes descendantes
     (`owner_scope.py:175-201`), et retombe sur `mine` pour un manager sans
     équipe. Confirmer que c'est bien la sémantique voulue pour le scope
     d'ÉCRITURE aussi, pas seulement pour la LECTURE.

### G2 — Environnements + CI/CD
Séparer test/démo et client/prod. Le build-health est un prérequis (pas de
CI/CD tant que le build ne passe pas sur Linux).

### G3 — Provisioning des tenants
Interface ou commande pour créer un client/tenant. Simple d'abord (commande),
UI plus tard.

### G4 — Limites & quotas d'usage (surtout IA)
Empêcher un client de dépasser ce qu'il a payé, en particulier sur les appels
IA (pipelines signaux, prep call). Métering + plafonds par tenant.
- **Note d'anticipation** : instrumenter le comptage des appels au moment où
  on touche ai_pipelines/, plutôt que tout re-tracer à la fin.

### G5 — Sandbox + stratégie données d'entraînement
- **G5a** : tenant sandbox / de test, marqué NON-ENTRAÎNABLE (flag
  is_sandbox / is_training_eligible au niveau tenant) — les données de test
  ne doivent JAMAIS entrer dans le corpus d'entraînement.
- **G5b** : stratégie de données d'entraînement — quelles données, quel
  consentement, quelle frontière étanche sandbox/prod. Question
  consentement/contrat (CGU) à trancher AVANT de collecter (sujet juridique,
  peut invalider rétroactivement le corpus si mal cadré).
- **Note d'anticipation** : le flag tenant non-entraînable gagne à exister
  tôt dans le modèle, pas rétrofitté sur des années de données.

---

## Références
- Dette technique détaillée : TECH_DEBT.md
- Ce document évolue : toute décision de roadmap prise en session est
  ajoutée ici via un commit docs(roadmap) séparé.

### Rappel dette critique (renvoi TECH_DEBT.md)
TD critiques non traités :
- **build-health : ✅ FERMÉ (PR #102, TD-18 résolu)** — deps déclarées, casses
  d'import traitées, `@mui/x-tree-view` `^6`→`^8` (pas `^7`) ;
  `@dnd-kit/sortable`/`utilities` étaient une cible inexacte (importés nulle
  part). Neuf constats frontend résiduels tracés en TD-132 → TD-140.
- **TD-99 / 101 / 102 / 103** (sprint S6 — TD-97 déjà RESOLVED).

---

## Prompt de reprise Claude assistant

_(à coller en nouvelle conversation)_

> Reprise du travail sur SalesCommands. Contexte :
> - Le ROADMAP.md (à jour) et TECH_DEBT.md sont dans le repo — je peux te
>   les recoller.
> - On est en plein sprint S7b (peaufinage vues Go-to-Market Territory +
>   Campaign), sur la branche `claude/views-inventory-audit-b4sjxe` (part de
>   `main` 924a46a).
> - Méthode de travail : audit CC d'abord → tu ajustes → prompts CC → CC
>   implémente → je valide localement (pytest/vitest + smoke à l'écran) →
>   merge via PR squash. Un commit par item, validé à l'écran avant
>   d'avancer. Règles clés : NE RIEN EXTRAPOLER (se baser sur l'existant,
>   citer le fichier de référence avant de coder), audit-first, repro rouge
>   d'abord pour les bugs, Q6 (pas d'écriture en GET).
> - État S7b : commits 1 (recherche), 2 (retrait edit + delete hover), 3
>   (filtre drawer, permission team `mine`→`client` intégrée) FAITS et
>   validés ; commit 4 (multi-select refait + bulk-delete Campaign) LIVRÉ
>   et mergé (PR #69). Reste commit 5 (enrichissement cartes, à faire avec
>   moi). S7b reste EN COURS tant que le commit 5 n'a pas atterri.
> - Détail complet du commit 5 : dans ROADMAP.md (section S7b).
>
> Reprends là où on en est : attaquer le commit 5 (enrichissement des
> cartes Territory + Campaign, à cadrer avec moi).
