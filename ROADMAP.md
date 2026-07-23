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

#### Reliquat de finition (identifié au smoke — hors périmètre livré, à traiter)
- **Option « Email Only »** : quand une campagne est créée avec l'option
  Email Only, la carte doit l'indiquer à côté du chip « Outbound Sequence ».
  L'option vit sur le modèle Campaign (choix à la création) ; vérifier
  qu'elle atteint le payload de liste avant de supposer que c'est purement
  frontend.

- **Validation** : chaque commit validé à l'écran (smoke) + tests avant de
  merger.

### Sprint — Cycle de vie des cibles de campagne (après S7b, avant S7c — prioritaire)
- **Objectif** : gérer la sortie des cibles atteignant un état final et
  refondre l'affichage de progression des cartes en conséquence. Trois items
  liés, à construire ENSEMBLE.
- **Priorité sur S7c** : ce chantier modifie la barre de progression livrée
  en S7b 5c — ne pas laisser en place un affichage qu'on sait provisoire.
1. Une cible (`CampaignContact`) atteignant un état final — toutes les
   activités terminées, OU arrêt manuel — doit QUITTER la liste des cibles de
   la campagne (historique préservé ailleurs). VÉRIFIER si c'est déjà le cas ;
   hypothèse de travail : non.
2. L'arrêt manuel nécessite un modal de confirmation : « are you sure you want
   to remove {CONTACT NAME} — {ACCOUNT NAME} from the campaign? ».
3. Conséquence pour les cartes : si les cibles quittent la liste, le
   dénominateur bouge → un pourcentage worked/total n'a plus de sens.
   L'affichage de progression devient « N contacts in chasing » (le compte
   restant à travailler), et la carte TARGETED — qui n'affiche aucune barre
   aujourd'hui — reçoit ce même compte. NOTE : ceci CHANGE la barre livrée en
   S7b 5c (worked/total, correcte sous le modèle actuel où les cibles
   terminées restent dans la liste).

### S7c — Filtres avancés DC + câblage Home "See all"
- **Objectif** : filtres DC complets + destinations réelles pour les "See
  all" de la Home.
- **Problématique** : filtres DC user/team/contact/stage non fonctionnels
  (le hook forwarde stage/status mais le backend les ignore) ; les "See
  all" de la Home ne mènent nulle part.
- **Solution** : ajouts backend (filterset), câblage des liens Home vers
  les vues S7a.
- **Navigation Home — noms cliquables** : depuis la section "My Progress" de
  la Home, les NOMS de campagne et de territoire doivent être cliquables →
  redirection vers la vue / le workspace correspondant. Même chantier de
  navigation Home que les liens "See all".
- **Validation** : chaque filtre DC filtre réellement ; chaque "See all"
  ouvre la vue filtrée correspondante.

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
- **Connexion cartes GTM** : l'avancement des objectifs sur les cartes GTM
  (zone préparée en S7b commit 5) sera CONNECTÉ ici.
- **Over-achievement (>100%)** : afficher le dépassement (ex "102%"),
  couleur warning dark (doré, palette standard) + icône étoile. À construire
  À LA FOIS sur les cartes ET sur la Home (cohérence).
  - **NOTE** : la Home aujourd'hui écrête à 100% (`goalGradient.js` clampe
    `remaining` et `pct`) — l'over-achievement est un comportement NEUF à
    créer des deux côtés.
- **Validation** : poser un quota/objectif → la Home le reflète.
- **Note** : candidat à remonter avant Sprint B (ferme une incohérence
  visible) — arbitrage PO en attente.

### S9 — UI Produit (+ TD-74/75)
- **Objectif** : ligne de produits + onglet Product Financial.
- **Problématique / Solution / Validation** : à cadrer. Frontière avec
  Sprint B (overview produit) à clarifier.

### S10 — Tech Catalogue (conception approfondie)
À cadrer.

### S11 — Signals UX (+ TD-29)
- **Objectif** : améliorer l'UX des signaux, réponse aux notes de signal.
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
- **URGENT (bloque le déploiement) — build-health** : `next build` échoue
  sur FS sensible à la casse (Linux/CI/prod), invisible sur macOS.
  Cibles connues : casses d'import (techCatalog/list.jsx:16-17
  businessdata→businessData ; userCSVConfig.js:24 UserCSVValidation) +
  sweep rg complet ; deps absentes de package.json (react-csv, @dnd-kit/
  core+sortable+utilities) ; version @mui/x-tree-view ^6→^7. Plus toute la
  dette S6/S7 (TD-97, 99, 101, 102, 103).

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
  - **Auditer le fail-open des modules désactivés** : un module absent/
    désactivé dans `config.MODULES` fail-open aujourd'hui vers le scope
    `client` (`checks.py`). Évaluer le fail-CLOSED comme défaut sécurisé.
    Changement de permissions transverse → repro + audit d'impact dédiés,
    PAS un simple flip de config.
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
- **build-health URGENT** : casses d'import (`businessData`/`businessdata`
  + `userCSVConfig`) ; deps absentes de `package.json` (`react-csv`,
  `@dnd-kit/core`+`sortable`+`utilities`) ; version `@mui/x-tree-view`
  `^6`→`^7`.
- **TD-97 / 99 / 101 / 102 / 103** (sprint S6).

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
