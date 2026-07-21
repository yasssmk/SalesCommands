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

### S7b — Peaufinage vues Go-to-Market (Territory + Campaign) — EN COURS
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
  - `owner_scope` dans le drawer (radio, défaut neutre `all`).
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
  - **Tri par défaut** = `created_at desc` (sélecteur de tri abandonné).
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

#### Commits RESTANTS
- **Commit 5** — enrichissement des cartes (FAIT AVEC LE PO) :
  - **Territory** : icône + nom, chip contact/account (les deux en
    secondary, tonalités light/dark différentes), nb contacts/comptes,
    territory coverage, "is in active campaign", owner + team, DATE DE
    CRÉATION (à afficher car tri par date).
  - **Campaign** : logo + nom + chip type (garder), statut reflété par la
    DATE (en cours : start–end date en secondary, sauf end date passée →
    warning light ; finished : "completed the {date}"), nom contact + nb
    comptes, avancement "X contacts left to contact" (via `queueGradient`
    copié de la Home — framing 'queue', pas de seuil), retrait de
    "Sequence: Targeted Campaign", zone objectif PRÉPARÉE (données en S8).
  - **Perf** : cartes déjà en batch 1-requête (`territory-metrics/batch`,
    `campaign-batch`) — enrichir le payload, pas de N+1.
  - **Logique de progression** : réutiliser `queueGradient` de la Home
    (`goalGradient.js`), ne pas réinventer de seuil.
- **Validation** : chaque commit validé à l'écran (smoke) + tests avant
  d'avancer.

### S7c — Filtres avancés DC + câblage Home "See all"
- **Objectif** : filtres DC complets + destinations réelles pour les "See
  all" de la Home.
- **Problématique** : filtres DC user/team/contact/stage non fonctionnels
  (le hook forwarde stage/status mais le backend les ignore) ; les "See
  all" de la Home ne mènent nulle part.
- **Solution** : ajouts backend (filterset), câblage des liens Home vers
  les vues S7a.
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
