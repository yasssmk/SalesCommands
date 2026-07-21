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

### S7b — Peaufinage des vues existantes
- **Objectif** : cohérence et complétude des vues déjà en place.
- **Problématique** : multi-select absent (Tech Catalogue), asymétrie
  Campaign/Territory, cartes GTM disparates (TerritoryCard/CampaignCard),
  pas de clic pleine ligne sur ReusableTable partagé.
- **Solution** : à cadrer — commencer par une analyse de différence entre
  les vues à harmoniser (structure + visualisation), puis le PO définit le
  comportement attendu.
- **Validation** : à définir après l'analyse de différence.

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

### S14 — Deal Health · S15 — Campaign UX · S16 — Homogénéisation UI · S17 — Filtres & Recherche
À cadrer.

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
