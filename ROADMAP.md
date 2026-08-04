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

### S13 — Intention & Prep Call
- **Objectif** : objectif d'activité + approche stratégique de campagne +
  Prep Call multi-canal.
- **Problématique** : ces trois éléments répondent à une seule question —
  pourquoi je fais cette activité et comment je la prépare. Les construire
  séparément = retrofit.
- **Solution** : à cadrer, groupés. Après S12 (la génération multi-canal
  en dépend).
- **Validation** : à définir.

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
