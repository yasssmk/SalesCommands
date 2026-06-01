# Rapport UX/Workflow — Post-call Activity Workspace

**Version** : 2 (mai 2026)
**Objectif** : décrire de façon exhaustive le workflow utilisateur et l'UX du post-call dans l'Activity Workspace. Document de référence pour la conversation d'implémentation à venir.

**Scope** : Activity Workspace (refonte des onglets : Notes / Signals / Next Steps), et les deux pipelines LLM impliqués (`qualification-signals`, `next-steps`).

**Hors scope** : Account / DC / Account Overview / Deal Health / Prep Call (traités dans le prochain rapport).

---

Note: point important qui n ont pas ete ajouter dns le rapport:

1 - Un signal peut etre incomplet - mettre des alerte pour que le user le rentre manuellement avant valider

## 1. Contexte et fondations

### 1.1 État actuel (audit)

L'Activity Workspace expose aujourd'hui **3 onglets actifs** :

| Onglet      | Composant                    | Rôle                                                             |
| ----------- | ---------------------------- | ---------------------------------------------------------------- |
| Overview    | `ActivityOverviewTab.jsx`    | Métadonnées en lecture (CTA, planning, contacts, cycle/step lié) |
| Preparation | `ActivityPreparationTab.jsx` | Notes de préparation éditables (placeholder)                     |
| Wrap-up     | `ActivityWrapUpTab.jsx`      | Orchestrateur post-call : capture + signaux + next steps         |

Le Wrap-up embarque actuellement deux sous-composants (`WrapUpCaptureSection.jsx` et `NextStepsSection.jsx`) et orchestre les deux wizards LLM (`WizardSignalAITranscript.jsx` et `WizardSignalAdd.jsx`). UX validée comme inadaptée à l'usage cible (linéaire, modal-only, force la validation atomique).

L'Activity possède déjà les champs `transcript` (TextField) et `preparation_notes` (TextField), marqués « stub IA » dans l'audit, peu exploités. Les champs `outcome` (enum), `outcome_notes`, `next_step_agreed` (auto-calculé, voir §3.1) et `no_next_step_reason` existent côté modèle.

Des fichiers résiduels (`ActivitySignalsTab.jsx`, `ActivityTranscriptTab.jsx`, `ActivityOutcomeTab.jsx`) sont présents dans le projet mais désactivés. Ils témoignent d'une ancienne architecture multi-onglets qui a été fusionnée dans Wrap-up. La refonte les réactive en partie.

### 1.2 Cible : 5 onglets après refonte

```
[Overview] [Preparation] [Notes] [Signals (5)] [Next Steps (3)]
```

| Onglet         | Statut                                                                    | Évolution                               | Régime               |
| -------------- | ------------------------------------------------------------------------- | --------------------------------------- | -------------------- |
| Overview       | Inchangé                                                                  | —                                       | passif               |
| Preparation    | Inchangé                                                                  | sera traité plus tard (Prep Call LLM)   | pre-call             |
| **Notes**      | **Nouveau** (remplace partiellement Wrap-up)                              | Transcript + bouton Run AI Analysis     | **CAPTURE**          |
| **Signals**    | **Nouveau** (réécriture du placeholder désactivé)                         | Vue Grouped + Flat des signaux du call  | **EXPOSE**           |
| **Next Steps** | **Nouveau** (refonte de `NextStepsSection.jsx`, déplacé en onglet propre) | Suggestions LLM + Activities planifiées | **EXPOSE + CAPTURE** |

Le **Wrap-up disparaît** comme onglet — son contenu est redistribué.

### 1.3 Principe directeur — deux régimes mentaux

L'Activity Workspace post-call sert **deux régimes d'usage** qu'il faut séparer pour éviter le chevauchement cognitif :

- **CAPTURE** (pendant et juste après le call) : prise de notes en live, collage progressif du transcript, ajout manuel de next-steps au fil de la discussion. Mode édition active, écriture brute, sans pollution AI.
- **EXPOSE** (après run AI, ou en revisite) : lecture des signaux extraits, validation/rejet, traitement des suggestions next-step, consultation du résumé. Mode lecture et action ciblée, sans champ libre.

L'onglet **Notes** sert le régime CAPTURE. Les onglets **Signals** et **Next Steps** servent le régime EXPOSE. L'onglet **Next Steps** est à cheval (on peut y ajouter manuellement à chaud), ce qui est légitime car les next-steps naissent autant pendant qu'après le call.

L'**ActivityHeader** porte les compteurs globaux et l'état du dernier run AI, visibles depuis n'importe quel onglet.

---

## 2. Workflow utilisateur post-call (parcours canonique)

### Phase A — Pendant et juste après le call

L'AE/SDR ouvre l'Activity en début ou pendant son call (depuis Playlist de campagne, Account Activities tab, ou liste activités). Il atterrit sur l'onglet **Notes** (onglet par défaut tant que l'Activity n'est pas COMPLETED).

Dans Notes, il :

- Colle ou édite le transcript au fur et à mesure (autosave sur `Activity.transcript`).
- Saisit des observations subjectives si besoin (notes libres — champ à formaliser avec backend, voir §11).
- Peut switcher vers l'onglet **Next Steps** pour créer un follow-up manuel pendant le call si une idée surgit (« il faut que je rappelle X demain »).

Pas encore d'AI à ce stade.

### Phase B — Lancement Run AI Analysis

Une fois le transcript stable, l'AE clique sur le bouton **`Run AI Analysis`** (présent dans l'onglet Notes, en bas de la zone transcript). Un **wizard léger en 2 steps** s'ouvre :

**Step 1 — Sélection des objectifs**

> _« Que veux-tu extraire de ce transcript ? »_
>
> Checkboxes :
>
> - ☐ Qualification signals (Pain, Objective, Impact, TechStack, Frein)
> - ☐ Next-step suggestions
>
> Si une option a déjà été extraite précédemment sur le même transcript (dédup `input_hash`), la case correspondante est cochée + grisée avec label _« Already extracted · il y a 12 min »_. Seule la case restante est cliquable.
>
> Bouton `Continue` désactivé tant qu'aucune option n'est cochée.

**Step 2 — Sanitization**

> _« Vérifie les éléments confidentiels avant envoi au LLM. »_
>
> Le transcript est affiché avec les éléments confidentiels (noms de contacts, nom du compte) **déjà pré-remplacés automatiquement** par des placeholders (`[CONTACT_1]`, `[COMPANY]`) — substitution UUID-based déjà implémentée côté backend.
>
> L'utilisateur peut :
>
> - Voir un diff visuel (avant/après).
> - Ajouter manuellement des occurrences à remplacer.
> - Revenir à l'original si besoin.
> - Ajouter les notes
>
> Bouton `Run analysis` (primaire) + `Back` (retour Step 1).

### Phase C — Run en arrière-plan, apparition des résultats

Au déclenchement du run, **le wizard se ferme**. Le bouton `Run AI Analysis` dans Notes se transforme en :

- Spinner intégré + label _« Analyzing… (qualif + next-step) »_. Désactivé.

**L'AE peut continuer à travailler** dans n'importe quel onglet pendant le run (prendre des notes, créer des next-steps manuels, consulter Overview/Preparation). Aucun blocage.

L'**ActivityHeader** affiche en parallèle un badge discret _« AI running… »_ visible depuis tous les onglets.

À la fin du run :

- **Badge orange** sur l'onglet Signals (`Signals (5)`).
- **Badge orange** sur l'onglet Next Steps (`Next Steps (3)`).
- **Toast non-bloquant** _« 5 qualification signals + 3 next-step suggestions extracted »_, disparaît après ~6 secondes.
- Le bouton `Run AI Analysis` dans Notes revient à un état informatif _« Last run · 12 min ago · qualif (5) + next-step (3) »_. Si l'utilisateur reclique, le wizard rouvre Step 1 avec options déjà extraites grisées.
- L'**ActivityHeader** met à jour son badge global de compteur : _« 8 to validate »_ (somme signaux PENDING + suggestions PENDING).

### Phase D — Validation des signaux (onglet Signals)

L'AE bascule sur l'onglet **Signals**. Vue par défaut : **Grouped**. Il voit :

- Section **Qualification** : signaux Pain/Obj/Imp/TS groupés par thème `what × dimension`.
- Section **Blockers / Objections** : freins en cards uniformes, sans taxonomie.

Pour chaque signal : action inline rapide `✓ Validate` / `✗ Reject`. Click sur une ligne → drawer compact avec source_quote + métadonnées + actions étendues (Edit, Validate, Reject).

S'il veut éditer un signal en profondeur ou lire toutes les source_quote, il bascule sur la vue **Flat** (toggle en haut de l'onglet) : liste linéaire de cards complètes, une par signal, avec tous les champs et édition inline.

### Phase E — Traitement des Next Steps (onglet Next Steps)

L'AE bascule sur **Next Steps**. Il voit :

- Section **AI Suggestions (PENDING)** en haut : cards LLM-sourced, chacune avec actions `Create activity` / `Edit then create` / `Reject`.
- Section **Planned Activities** en bas : Activities déjà planifiées (manuelles ou issues de validations précédentes).

Il traite chaque suggestion :

- `Create activity` → mini-form Activity prérempli (titre, type, due_date, contacts hérités, si il; manque des info informer les users pour qui les ajoute manuellement), modifiable, save → Activity créée avec FK `next_step_signal` vers le signal NextStep. Le signal passe en VALIDATED. La card LLM se transforme en place en card Activity standard.
- `Reject` → signal NextStep marqué REJECTED. La card disparaît de la sous-section AI Suggestions. Retrouvable via filtre Rejected dans la vue Flat de l'onglet Signals.

### Phase F — Complétion de l'Activity [Garder comme c'est]

Indépendamment du traitement des signaux et suggestions, l'AE peut clôturer l'Activity via le menu actions de l'**ActivityHeader** (`Complete`). Une modale s'ouvre :

- **Outcome** (chip selector) : Successful / No answer / Callback requested / Not interested / etc.
- **Outcome notes** (textarea libre).
- **No next step reason** (chip selector, conditionnel — affiché uniquement si aucune Activity ultérieure n'est planifiée pour ce compte/cycle).

**Pas de champ `next_step_agreed` dans la modale** : ce booléen est **dérivé automatiquement** côté backend en vérifiant l'existence d'autres activités ultérieures. L'utilisateur ne le saisit jamais.

À save → Activity passe en COMPLETED. Le compteur global de l'ActivityHeader reste visible tant qu'il existe des signaux PENDING ou suggestions PENDING (la complétion n'est pas bloquée par eux).

### Phase G — Retour ultérieur (rattrapage)

L'AE qui rouvre une Activity 3 jours après arrive dans l'état persistant :

- Onglet Notes : transcript et notes intacts.
- Onglet Signals : badge éventuel _« 3 to validate »_ si signaux PENDING.
- Onglet Next Steps : badge éventuel _« 2 to handle »_ si suggestions PENDING.
- ActivityHeader : compteur global cumulé si applicable, badge _« Last AI run · 3 days ago »_.

Aucun travail n'est perdu. L'AE traite ce qui reste à son rythme.

**Propagation aux listes externes** : _(à confirmer comme partie du scope ou reporter)_ — un badge sur la ligne de l'Activity dans Account Activities tab et Campaign Playlist permet de repérer les activities ayant du travail post-call en attente sans avoir à entrer dans chacune.

---

## 3. Anatomie détaillée des onglets

### 3.1 ActivityHeader (refonte légère du composant existant)

Le composant `ActivityHeader.jsx` actuel (chip type, titre éditable, statut, menu actions Complete/Cancel/Reopen/Delete) est enrichi de **trois éléments** :

1. **Badge état Run AI** (côté droit, discret) :
   - Idle (aucun run jamais) : pas de badge.
   - Running : badge avec spinner _« AI running… »_.
   - Success : badge _« AI run · 12 min ago »_ + tooltip détaillant les options extraites au survol.
   - Error : badge rouge _« AI run failed »_ + tooltip avec message d'erreur.

2. **Compteur global PENDING** (badge orange cliquable) :
   - Visible si signaux PENDING > 0 ou suggestions PENDING > 0.
   - Format : _« 8 to validate »_ (cumul).
   - Click → bascule sur l'onglet pertinent (Signals si plus de signaux, Next Steps si plus de suggestions, ou le premier qui contient des items PENDING).

3. **Menu Complete enrichi** : la modale qui s'ouvre depuis `Complete` est modifiée pour exposer `outcome` + `outcome_notes` + `no_next_step_reason` (conditionnel). Pas de `next_step_agreed` (auto-calculé backend).

### 3.2 Onglet Notes (régime CAPTURE)

Stack vertical simple, mode édition active. Pas de colonnes — c'est de la saisie, pas de la lecture.

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  TRANSCRIPT                                                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ [textarea — transcript collé, autosave sur blur]     │    │
│  │                                                      │    │
│  │ Pierre: « Aujourd'hui on perd beaucoup de temps... » │    │
│  │ Moi: « Vous chiffrez ça à combien ? »                │    │
│  │ ...                                                  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                          [Run AI Analysis ▾] │
│                                                              │
│  NOTES (optional — observations subjectives)                 │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ [textarea libre, autosave]                           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Champs** :

- `transcript` (existant) : zone primary, large.
- Notes subjectives : à formaliser (nouveau champ `Activity.notes` ou réutilisation de `outcome_notes` ?). **Question ouverte §11**.

**Bouton `Run AI Analysis`** :

- Position : juste sous la zone transcript, alignement à droite.
- Comportement détaillé §4.

**Pas d'Outcome ici** : saisi via la modale Complete depuis l'ActivityHeader.

### 3.3 Onglet Signals (régime EXPOSE)

**Toggle de vue Grouped / Flat** en haut de l'onglet, l'état est persisté en session.

#### 3.3.1 Vue Grouped (par défaut)

```
┌────────────────────────────────────────────────────────────────┐
│  SIGNALS                                                       │
│  ● 5 to validate · 3 validated · 2 rejected                    │
│                                                                │
│  View: [● Grouped] [Flat]                                      │
│  Filter: [All] [Pending] [Validated] [Rejected]                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ── QUALIFICATION ────────────────── (by theme)                │
│                                                                │
│  ╭─ DATA × TIME ─────────────────────────────  3 ───────╮     │
│  │ 🔴 Pain   Les équipes perdent 5h/semaine    [✓][✗]   │     │
│  │ 🎯 Obj    Réduire le temps de préparation   [✓][✗]   │     │
│  │ 💰 Imp    200K€/an estimé, non confirmé     [✓][✗]   │     │
│  ╰─────────────────────────────────────────────────────────╯   │
│                                                                │
│  ╭─ OPS × COST ──────────────────────────────  2 ───────╮     │
│  │ 🔴 Pain   Coût opérationnel élevé           [✓][✗]   │     │
│  │ 💻 TS     Salesforce — usage limité         ✓ validé │     │
│  ╰─────────────────────────────────────────────────────────╯   │
│                                                                │
│  ╭─ TECH × QUALITY ──────────────────────────  3 ───────╮     │
│  │ ...                                                    │     │
│  ╰─────────────────────────────────────────────────────────╯   │
│                                                                │
│  ── BLOCKERS / OBJECTIONS ─────────                            │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Budget gelé Q4, décision attendue Q1            [✓][✗]│    │
│  │ 💬 "On a déjà bloqué le budget jusqu'en janvier"      │    │
│  │ 👤 Pierre Dupont                                      │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Pas une priorité avant l'été                    [✓][✗]│    │
│  │ 💬 "On a d'autres chantiers d'ici juin"               │    │
│  │ 👤 Sophie Martin                                      │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

**Section Qualification** :

- Groupement par thème `what × dimension`.
- Header de thème : titre dense + count.
- Lignes signal compactes : icône type + titre court + actions inline.
- Pain/Obj/Imp/TS partagent la même densité visuelle (icône différenciatrice par type).
- Click sur une ligne → drawer compact avec source_quote + métadonnées + actions étendues.

**Section Blockers / Objections** :

- Cards uniformes, **pas de groupement par taxonomie** (les freins sont en texte libre).
- Chaque card : texte du frein + source_quote (italique) + contact + actions.
- Le Frein n'a pas de what×dimension ni de blocker_type structuré côté UI. Texte libre + quote + contact.

**Filtres** :

- View toggle : Grouped / Flat.
- Statut chips : All / Pending / Validated / Rejected.
- Les REJECTED sont visibles via le filtre `Rejected` ou `All` — affichés grisés/collapsés au sein de leur thème ou section, pas masqués.

#### 3.3.2 Vue Flat (toggle)

```
┌────────────────────────────────────────────────────────────────┐
│  SIGNALS                                                       │
│  ● 5 to validate · 3 validated · 2 rejected                    │
│                                                                │
│  View: [Grouped] [● Flat]                                      │
│  Filter: [All] [Pending] [Validated] [Rejected]                │
│  Sort: [Date ▼] [Type] [Theme] [Status]                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─[🔴 Pain · DATA × TIME · PENDING]─────────────────────┐   │
│  │ Les équipes perdent 5h/semaine sur la consolidation   │   │
│  │ 💬 "On a 5h par semaine qui partent en consolidation  │   │
│  │     pour préparer les revues"                         │   │
│  │ 👤 Pierre Dupont                                      │   │
│  │ Extracted: 12 May 14:32                               │   │
│  │              [Edit] [Validate] [Reject]               │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─[🎯 Objective · DATA × TIME · PENDING]────────────────┐   │
│  │ Réduire le temps de préparation des account reviews   │   │
│  │ 💬 "L'idéal serait de descendre à 2h par semaine"     │   │
│  │ 👤 Pierre Dupont                                      │   │
│  │ ...                                                    │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─[⚠️ Blocker · PENDING]────────────────────────────────┐   │
│  │ Budget gelé Q4, décision attendue Q1                  │   │
│  │ 💬 "On a déjà bloqué le budget jusqu'en janvier"      │   │
│  │ 👤 Pierre Dupont                                      │   │
│  │ ...                                                    │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─[💻 TechStack · OPS × COST · VALIDATED]──────────────┐    │
│  │ Salesforce — usage limité aux équipes commerciales    │   │
│  │ ...                                                    │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Cards complètes**, une par signal :

- Header de card : type + thème (si applicable) + statut, en chips colorés.
- Titre / résumé du signal.
- `source_quote` en pleine longueur, encadrée, italique.
- Contact source.
- Date d'extraction.
- Actions : Edit (mode édition inline avec Formik), Validate, Reject.

**Tri** : par défaut Date (plus récent en haut), options Type / Theme / Status.

**Filtre statut** : même chips que vue Grouped. Les REJECTED sont visibles via filtre `Rejected` ou `All` (cards grisées).

**Partage de composants avec AccountSignalsTab** : la card de la vue Flat est le même composant `SignalDetailCard` que celui utilisé dans l'AccountSignalsTab (refonte également prévue, hors scope cette itération). DRY garanti.

### 3.4 Onglet Next Steps (régime EXPOSE + CAPTURE)

Stack vertical, **2 sous-sections distinctes** :

```
┌──────────────────────────────────────────────────────────────┐
│  NEXT STEPS                              + Add manually      │
│  ● 2 AI suggestions to handle · 3 activities planned         │
│                                                              │
│  [All] [AI Suggestions (2)] [Activities (3)]                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ── AI SUGGESTIONS (PENDING) ──────────                      │
│                                                              │
│  ┌─[🤖 AI] 📞 Call · suggested Wed ────────────────────┐    │
│  │ Quantifier l'impact financier du pain                 │   │
│  │ "consolidation"                                        │   │
│  │ 👤 Pierre Dupont · Sophie Martin                      │   │
│  │ 💬 "On n'a pas eu le temps de chiffrer l'impact       │   │
│  │     financier sur ce point"                           │   │
│  │              [Create activity] [Edit] [Reject]         │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─[🤖 AI] 📧 Email · suggested Tomorrow ──────────────┐    │
│  │ Envoyer benchmark coûts sectoriel à Sophie            │   │
│  │ 👤 Sophie Martin                                      │   │
│  │ 💬 "Elle a demandé un benchmark"                      │   │
│  │              [Create activity] [Edit] [Reject]         │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                              │
│  ── PLANNED ACTIVITIES ────────────                          │
│                                                              │
│  ┌─📞 Call · Wed 12 May ─────────────  PLANNED ───────┐     │
│  │ Démo PoC sur module consolidation                     │   │
│  │ 👤 Pierre Dupont · Sophie Martin                      │   │
│  │ 💬 Suite au call du 10 mai                            │   │
│  │              [Open activity] [Edit] [Cancel]           │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─📧 Email · Today ─────────────────  PLANNED ───────┐     │
│  │ Suivi documentation technique                         │   │
│  │ 👤 Pierre Dupont                                      │   │
│  │              [Open activity] [Edit] [Cancel]           │   │
│  └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**Cards** — structure commune Quand / Quoi / Qui / Pourquoi :

| Élément             | Card AI Suggestion               | Card Activity planifiée                   |
| ------------------- | -------------------------------- | ----------------------------------------- |
| Badge haut-gauche   | `🤖 AI Suggestion`               | Type d'activity (📞 Call, 📧 Email, etc.) |
| Quand               | `suggested [date]`               | Statut + date programmée                  |
| Quoi                | Titre suggéré par le LLM         | Titre Activity                            |
| Qui                 | Contacts hérités du call         | Contacts liés à l'Activity                |
| Pourquoi            | `source_quote` du transcript     | Description ou chaînage signal source     |
| Action primaire     | `Create activity` (bouton plein) | `Open activity` (lien tertiary)           |
| Actions secondaires | `Edit then create`, `Reject`     | `Edit`, `Cancel`                          |
| Bordure             | Dashed orange (PENDING)          | Solid neutral                             |
| Background          | Légère teinte orange-pâle        | Blanc                                     |

**Différenciateur visuel immédiat** : à un regard, l'AE distingue ce qui demande action (AI Suggestion) de ce qui est déjà engagé (Activity planifiée).

**Action `Create activity` sur card LLM** :

- Ouvre un mini-form modal compact (titre, type, due_date suggérés et modifiables, contacts hérités modifiables).
- Save → Activity créée avec FK `next_step_signal` vers le signal NextStep validé.
- Signal NextStep passe à VALIDATED.
- La card LLM-sourced se transforme en place en card Activity standard (animation courte).

**Action `Reject` sur card LLM** :

- Signal NextStep passe à REJECTED.
- La card disparaît de la section AI Suggestions.
- Retrouvable dans l'onglet Signals vue Flat avec filtre Rejected, ou via filtre statut dans l'onglet Next Steps si exposé.

**Bouton `+ Add manually`** (haut droit) : ouvre le quick-create existant (de `NextStepsSection.jsx`), création directe d'une Activity manuelle qui rejoint la section Planned Activities.

**Filtre All / AI Suggestions / Activities** : permet à l'AE de zoomer sur une sous-population.

---

## 4. Comportement du wizard Run AI Analysis

### 4.1 Wizard 2 steps

**Step 1 — Objectifs** :

- Modal compact (~400px de large), 2 checkboxes verticales :
  - ☐ Qualification signals (Pain, Objective, Impact, TechStack, Blocker)
  - ☐ Next-step suggestions
- Si une option a déjà été extraite (dédup `input_hash` côté backend) : checkbox cochée + grisée + label _« Already extracted · il y a 12 min »_.
- Bouton `Continue` (primary) désactivé tant qu'aucune case active n'est cochée.
- Bouton `Cancel` (tertiary).

**Step 2 — Sanitization** :

- Affichage du transcript avec substitutions appliquées en surbrillance (placeholders `[CONTACT_1]`, `[COMPANY]`, etc.).
- Toggle « Show original / Show sanitized ».
- Champ d'ajout manuel d'occurrences à remplacer (text → placeholder).
- Bouton `Run analysis` (primary).
- Bouton `Back` (retour Step 1).

### 4.2 Comportement post-déclenchement

Au clic `Run analysis` :

- Le wizard **se ferme** immédiatement.
- Le bouton `Run AI Analysis` dans Notes passe en état Running (spinner + label _« Analyzing… (qualif + next-step) »_, désactivé).
- L'ActivityHeader affiche un badge _« AI running… »_.
- L'AE peut continuer à travailler sur n'importe quel onglet, aucun blocage.
- Polling via `pollOperationStatus.js` sur les `Idempotency-Key` (un par pipeline lancé).

### 4.3 Effets visuels à l'apparition des résultats

À la fin d'un pipeline (success) :

- **Animation fade-in** douce sur les blocs nouvellement remplis dans Signals ou Next Steps.
- **Chip PENDING** des nouveaux items pulse légèrement les premières secondes (subtile, atténué après 5s).
- **Badge orange** sur l'onglet concerné (`Signals (5)`, `Next Steps (3)`).
- **Toast non-bloquant** (top-right ou bottom-right selon convention codebase) avec récap : _« 5 qualification signals + 3 next-step suggestions extracted »_. Disparaît après ~6s.
- Le bouton `Run AI Analysis` dans Notes revient à un état informatif : _« Last run · 12 min ago · qualif (5) + next-step (3) »_.

### 4.4 États du bouton Run AI

| État backend                         | UI bouton                                  | Cliquable ?                              |
| ------------------------------------ | ------------------------------------------ | ---------------------------------------- |
| Idle (jamais lancé)                  | `Run AI Analysis`                          | Oui                                      |
| Running                              | Spinner + `Analyzing… (options)`           | Non                                      |
| Success (au moins 1 option extraite) | `Last run · {time} · {résumé}`             | Oui (rouvre wizard avec options grisées) |
| Partial                              | `Partial run · {time} · {détail}` + alerte | Oui (rouvre wizard, retry possible)      |
| Error                                | `Run failed ({type}) · Retry`              | Oui (re-lance)                           |

### 4.5 Transcript modifié après run

Si l'AE modifie le transcript après un run réussi (autosave change le `input_hash`) :

- Avertissement non-bloquant : _« Transcript modified — re-running will create new signals. Already-validated signals stay. »_
- Le bouton `Run AI Analysis` se réactive automatiquement.

---

## 5. Comportement des pipelines LLM

### 5.1 Pipeline `qualification-signals`

**Endpoint** : `POST module-ai-pipelines/qualification-signals/extract/` (extension de l'existant `transcript-signals`).

**Input** : `Activity.transcript` sanitized (UUID substitution déjà implémentée).

**Stages internes** (recommandation : séquentiel pour cohérence contextuelle, parallélisable si latence critique) :

1. Pain extraction
2. Objective extraction
3. Impact extraction
4. TechStack extraction
5. **Blocker extraction** (nouveau)

**Output** : N signaux créés en base, statut PENDING, attachés à l'Activity via `source_activity`. `AIPipelineRun` créé avec statut RUNNING/SUCCESS/PARTIAL/PARSE_ERROR/LLM_ERROR/TIMEOUT.

**Filtres de sécurité** (existants) : `confidence ≥ 0.5`, drop `is_inferred=true`.

**Idempotence** : header `Idempotency-Key`, polling `ops/{key}/`, dédup DB sur `input_hash`. Re-run sur même transcript renvoie le run existant.

**Cas PARTIAL** : si N stages sur 5 ont réussi, on crée les signaux des stages réussis et on remonte une alerte côté UI _« Partial · N of 5 stages succeeded — see details »_. Bouton retry possible.

### 5.2 Pipeline `next-steps`

**Endpoint** : `POST module-ai-pipelines/next-steps/extract/` (nouveau).

**Input** : `Activity.transcript` sanitized.

**Stage** : unique, extraction des next-step suggestions comme **signaux NextStep** (lifecycle SignalStatus standard, PENDING par défaut).

**Output** : N signaux NextStep PENDING créés en base, attachés à l'Activity via `source_activity`. Chaque signal porte un payload structuré : titre suggéré, type d'activity, due_date suggérée, raison/`source_quote`, contacts liés suggérés.

**Idempotence** : même mécanisme.

### 5.3 Architecture commune

Les deux pipelines :

- Sont **indépendants** (deux runs distincts, deux `AIPipelineRun` séparés).
- Partagent le `Idempotency-Key` / polling pattern.
- Génèrent chacun un audit (provider, model, tokens, status, input_hash, sub_calls).
- Sont **manuellement déclenchés** via le wizard depuis l'onglet Notes.
- Peuvent être **lancés séparément** (qualif seul, next-step seul) ou ensemble.

### 5.4 Pipeline `deal-health` (hors scope cette itération)

Mentionné pour mémoire : 3ème pipeline, lancé depuis le DC (pas l'Activity), output rhéto-sentimental par stakeholder. Traité dans le prochain rapport (Account / DC).

---

## 6. Navigation et drill-down

### 6.1 Depuis l'ActivityHeader

- Click sur badge compteur global _« 8 to validate »_ → bascule sur l'onglet pertinent (Signals ou Next Steps selon le poids).
- Click sur badge état AI → affiche un tooltip détaillé (dernière run, options, timestamp). Pas de navigation.
- Menu actions `Complete` → modale Complete (outcome + outcome_notes + no_next_step_reason conditionnel).

### 6.2 Depuis l'onglet Notes

- Bouton `Run AI Analysis` → ouvre le wizard 2 steps.
- Aucune autre navigation directe (Notes est un espace de saisie pur).

### 6.3 Depuis l'onglet Signals (vue Grouped)

- Click sur ligne signal compacte → drawer compact latéral (source_quote + métadonnées + actions Edit/Validate/Reject) **sans quitter l'onglet**.
- Click sur header de thème → option collapse/expand du bloc.
- Toggle View Grouped/Flat → bascule la vue, état persisté en session.
- Filtre statut → filtre in-place de la liste.

### 6.4 Depuis l'onglet Signals (vue Flat)

- `Edit` sur card → mode édition inline avec Formik+Yup, save/cancel.
- `Validate` / `Reject` → action immédiate, refresh SWR de la card concernée.
- Click sur contact mentionné dans une card → drawer contact (à créer ou réutiliser existant).
- Sort dropdown → re-tri in-place.

### 6.5 Depuis l'onglet Next Steps

- `Create activity` sur card LLM → modal mini-form prérempli, save → transformation en place de la card.
- `Edit then create` sur card LLM → idem mais avec form plus large pour modifs approfondies.
- `Reject` sur card LLM → action immédiate, card disparaît.
- `Open activity` sur card Activity → navigation vers l'Activity Workspace concerné.
- `Edit` sur card Activity → édition inline ou modal selon le pattern existant.
- `Cancel` sur card Activity → confirme + statut CANCELLED.
- `+ Add manually` → quick-create existant.

### 6.6 Contexte large

- Depuis Account Activities tab : click sur ligne d'activity → navigation vers Activity Workspace, onglet par défaut Notes si pas de signaux PENDING, sinon Signals.
- Depuis Account SignalsTab à plat : click sur un signal → option `Open source activity` qui navigue vers Activity Workspace > onglet Signals avec signal pré-sélectionné.
- Depuis Campaign Playlist : idem Activity Workspace.

---

## 7. Composants frontend à créer ou modifier

### 7.1 À créer

| Composant                                                             | Emplacement                         | Rôle                                                                           |
| --------------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------ |
| `ActivityNotesTab`                                                    | `sections/activities/workspace/`    | Nouveau onglet — transcript + bouton Run AI + notes libres optionnelles        |
| `RunAIAnalysisButton`                                                 | `sections/activities/notes/`        | Bouton primary qui ouvre le wizard ; expose états Idle/Running/Success/Error   |
| `RunAIWizard`                                                         | `sections/activities/notes/wizard/` | Modal léger 2 steps (Objectifs + Sanitization)                                 |
| `RunAIWizardStepObjectives`                                           | `sections/activities/notes/wizard/` | Step 1 — checkboxes + détection options déjà extraites                         |
| `RunAIWizardStepSanitization`                                         | `sections/activities/notes/wizard/` | Step 2 — diff visuel + ajout manuel substitutions                              |
| `ActivityHeaderAIStatusBadge`                                         | `sections/activities/workspace/`    | Badge état dernier run AI dans l'ActivityHeader                                |
| `ActivityHeaderPendingCounter`                                        | `sections/activities/workspace/`    | Badge compteur global PENDING cumulé                                           |
| `ActivitySignalsTab` (réécriture du placeholder désactivé)            | `sections/activities/workspace/`    | Onglet Signals avec toggle Grouped/Flat                                        |
| `SignalsViewToggle`                                                   | `sections/activities/signals/`      | Toggle Grouped/Flat persistant en session                                      |
| `SignalsGroupedView`                                                  | `sections/activities/signals/`      | Vue Grouped (Qualif par thème + Blockers cards)                                |
| `SignalsFlatView`                                                     | `sections/activities/signals/`      | Vue Flat (liste linéaire cards complètes)                                      |
| `SignalsFilterBar`                                                    | `sections/activities/signals/`      | Barre filtres statut (+ sort en vue Flat)                                      |
| `SignalThemeBlock`                                                    | `sections/activities/signals/`      | Bloc thème avec header dense + lignes signal compactes                         |
| `SignalCompactLine`                                                   | `sections/activities/signals/`      | Ligne signal compacte (vue Grouped, dans un thème)                             |
| `BlockerCompactCard`                                                  | `sections/activities/signals/`      | Card frein uniforme (texte + quote + contact + actions)                        |
| `SignalQuickDrawer`                                                   | `sections/activities/signals/`      | Drawer compact latéral pour drill-down rapide depuis vue Grouped               |
| `SignalDetailCard` (refonte, à partager avec AccountSignalsTab futur) | `components/cards/signals/`         | Card pleine taille pour vue Flat (source_quote + métadonnées + édition inline) |
| `ActivityNextStepsTab`                                                | `sections/activities/workspace/`    | Nouveau onglet — sections AI Suggestions + Planned Activities                  |
| `NextStepsFilterBar`                                                  | `sections/activities/nextSteps/`    | Barre filtres All / AI Suggestions / Activities                                |
| `AISuggestionCard`                                                    | `components/cards/nextSteps/`       | Card LLM-sourced (badge AI, source_quote, 3 actions)                           |
| `PlannedActivityCard`                                                 | `components/cards/nextSteps/`       | Card Activity planifiée (variant existant repensé)                             |
| `LLMNextStepActivityFormModal`                                        | `sections/activities/nextSteps/`    | Mini-form Activity prérempli depuis signal NextStep                            |
| `CompleteActivityModal` (refonte de la modale existante)              | `sections/activities/workspace/`    | Modale outcome + outcome_notes + no_next_step_reason conditionnel              |
| `usePipelineRunner` (hook)                                            | `hooks/`                            | Hook pour lancer un pipeline, polling, état                                    |
| `useActivitySignals` (hook SWR)                                       | `hooks/`                            | Récupère les signaux d'une Activity, filtrable par statut/type/thème           |
| `useActivityNextSteps` (hook SWR)                                     | `hooks/`                            | Récupère AI suggestions PENDING + Activities planifiées de cette Activity      |
| `useActivityAIRunStatus` (hook SWR)                                   | `hooks/`                            | Récupère le dernier `AIPipelineRun` par pipeline pour cette Activity           |

### 7.2 À modifier

| Composant                              | Emplacement                      | Modification                                                                    |
| -------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------- |
| `ActivityTabs.jsx`                     | `sections/activities/workspace/` | Passer de 3 à 5 onglets (Overview / Preparation / Notes / Signals / Next Steps) |
| `ActivityHeader.jsx`                   | `sections/activities/workspace/` | Intégrer badges AI status + compteur global PENDING + menu Complete enrichi     |
| `views/activities/workspace/index.jsx` | `views/activities/workspace/`    | Routing par défaut sur Notes ou Signals selon présence de PENDING               |

### 7.3 À déprécier ou supprimer

| Composant                      | Action                                                                                  |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| `ActivityWrapUpTab.jsx`        | Supprimer (remplacé par Notes / Signals / Next Steps en onglets propres)                |
| `WrapUpCaptureSection.jsx`     | Supprimer (contenu absorbé par Notes + déclenchement AI par le wizard)                  |
| `NextStepsSection.jsx`         | Supprimer ou refondre en `ActivityNextStepsTab`                                         |
| `WizardSignalAITranscript.jsx` | Supprimer (remplacé par le nouveau wizard + sections persistantes)                      |
| `WizardSignalAdd.jsx`          | À conserver comme outil de fallback `+ Add manually` depuis Signals vue Flat, simplifié |

### 7.4 Stack rappelée

- **Framework** : Next.js App Router, JSX (pas TypeScript).
- **UI** : MUI + `@ant-design/icons` (jamais MUI icons — convention codebase).
- **Forms** : Formik + Yup.
- **Data fetching** : SWR + axios via hooks dans `frontend/src/api/`.
- **PropTypes** : au bas de chaque composant.
- **Référence patterns** : `views/businessData/accounts/`, `sections/businessData/accounts/`.

---

## 8. Endpoints API à utiliser ou créer

### 8.1 Existants à réutiliser

| Endpoint                                          | Usage                                               |
| ------------------------------------------------- | --------------------------------------------------- |
| `GET module-activities/{id}/`                     | Récupération Activity (transcript, statut, etc.)    |
| `PATCH module-activities/{id}/`                   | Sauvegarde transcript en autosave                   |
| `POST module-activities/{id}/complete/`           | Complétion (à enrichir avec champs modale Complete) |
| `GET ops/{key}/`                                  | Polling statut pipeline                             |
| `GET module-signals/{type}/?source_activity={id}` | Liste signaux d'une Activity par type               |
| `POST module-signals/{type}/{id}/validate/`       | Validation signal individuel                        |
| `POST module-signals/{type}/{id}/reject/`         | Rejet signal individuel                             |
| `GET module-signals/choices/`                     | Enums pour formulaires                              |

### 8.2 À étendre

| Endpoint                                               | Modification                                                                                                                                                                                              |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST module-ai-pipelines/transcript-signals/extract/` | Renommer en `qualification-signals/extract/` et ajouter stage Blocker (5 stages au total). Frein = nouveau type concret BlockerSignal côté backend (modélisation à valider dans la conversation suivante) |
| `POST module-activities/{id}/complete/`                | Body accepte `outcome` + `outcome_notes` + `no_next_step_reason` (conditionnel). Pas de `next_step_agreed` (auto-calculé)                                                                                 |

### 8.3 À créer

| Endpoint                                                  | Action                                                                                                                                                             |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `POST module-ai-pipelines/next-steps/extract/`            | Nouveau pipeline next-steps, output signaux NextStep PENDING                                                                                                       |
| `POST module-signals/blocker/{id}/validate/`              | Validation signal Blocker (texte libre, pas de what×dimension obligatoire)                                                                                         |
| `POST module-signals/blocker/{id}/reject/`                | Rejet signal Blocker                                                                                                                                               |
| `POST module-signals/next-step/{id}/validate/`            | Validation signal NextStep (à voir : déclenche-t-il la création Activity côté backend ou frontend ?)                                                               |
| `POST module-signals/next-step/{id}/reject/`              | Rejet signal NextStep                                                                                                                                              |
| `GET module-signals/by-activity/{activity_id}/counts/`    | Compteurs agrégés (PENDING / VALIDATED / REJECTED par type) pour les badges du Header                                                                              |
| `POST module-activities/from-next-step/{signal_id}/`      | (Alternative) Création Activity depuis NextStep validé, avec FK `next_step_signal` câblée automatiquement. À débattre vs création frontend standard + FK explicite |
| `GET module-ai-pipelines/runs/by-activity/{activity_id}/` | Liste des `AIPipelineRun` de cette Activity (pour le badge état dans Header et le label du bouton Run AI)                                                          |

### 8.4 Cache et invalidation

- Tags existants : `SIGNALS_CACHE_TAG`, `SIGNAL_CLUSTERS_CACHE_TAG`.
- À invalider sur : validation/rejet signal, création Activity depuis NextStep.
- À ajouter : cache key par Activity pour compteurs (`activity:{id}:signal_counts`).

---

## 9. Cas limites et erreurs à gérer

| Cas                                                           | Comportement attendu                                                                                                                                                            |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Transcript vide → utilisateur clique Run AI                   | Bouton désactivé par défaut, tooltip _« Paste a transcript first »_                                                                                                             |
| Pipeline timeout                                              | Bouton revient actif, message d'erreur dans Header et bouton, CTA Retry                                                                                                         |
| Pipeline PARTIAL (3 of 5 stages OK)                           | Signaux des stages réussis créés, alerte UI claire, retry possible _(question §11 : retry global ou stage manquant ?)_                                                          |
| Aucun signal extrait                                          | Onglet Signals affiche état Empty _« No relevant signals found in this transcript »_. Badge sur l'onglet absent                                                                 |
| Utilisateur modifie le transcript après run                   | Avertissement non-bloquant, bouton réactivé, signaux existants conservés intacts                                                                                                |
| Utilisateur valide un signal supprimé entre-temps             | Toast erreur, refresh SWR de la liste                                                                                                                                           |
| 2 onglets navigateur ouverts                                  | SWR mutate cross-tab si supporté, sinon dernière action gagne. À débattre en implémentation                                                                                     |
| Activity supprimée pendant qu'on est dessus                   | Redirection vers liste activités + toast                                                                                                                                        |
| Réseau perdu pendant un run                                   | Polling continue en arrière-plan, affichage _« Connection lost, retrying… »_, reprise au retour                                                                                 |
| Run AI pendant que l'utilisateur édite le transcript          | Le hash de référence du run est celui au moment du lancement. Modifications post-lancement ne tuent pas le run en cours. À la fin du run, si transcript a changé, avertissement |
| Activity COMPLETED mais signaux PENDING restants              | Compteur global reste visible. L'AE peut rouvrir l'Activity (Reopen) pour traiter                                                                                               |
| Signal Blocker sans contact source (LLM n'a pas pu attribuer) | Affiché sans le `👤 [contact]`, mention _« No contact attributed »_ discrète                                                                                                    |

---

## 10. Décisions actées (récap atelier)

1. **5 onglets** dans Activity Workspace : Overview / Preparation / Notes / Signals / Next Steps.
2. **Régimes séparés** : Notes = CAPTURE, Signals = EXPOSE, Next Steps = EXPOSE+CAPTURE.
3. **Wrap-up disparaît** comme onglet (son contenu est redistribué).
4. **Outcome saisi via menu Complete** du Header, pas dans Notes. Modale : outcome + outcome_notes + no_next_step_reason conditionnel.
5. **`next_step_agreed` auto-calculé** côté backend (présence d'autres activités ultérieures). Pas saisi par l'utilisateur.
6. **3 pipelines LLM** mais 2 exposés depuis l'Activity (qualification-signals + next-steps). Deal-health lancé depuis le DC, traité plus tard.
7. **Wizard Run AI Analysis à 2 steps** : Objectifs (checkboxes qualif/next-step) + Sanitization (UUID substitution déjà existante côté backend + ajout manuel possible).
8. **Comportement (b)** au déclenchement : wizard se ferme, spinner sur bouton, l'utilisateur continue à travailler. Badge état dans ActivityHeader.
9. **Pas de re-run sur même transcript** : dédup via `input_hash`. Re-run autorisé si transcript modifié.
10. **Effets visuels post-run** : animation fade-in, chip PENDING qui pulse, badges sur onglets, toast non-bloquant.
11. **Onglet Signals — toggle Grouped/Flat** :
    - Grouped : Qualif par thème + Blockers en section séparée
    - Flat : liste linéaire cards complètes avec édition fine
    - REJECTED visibles dans les 2 vues (via filtre statut)
12. **Freins (Blockers)** : texte libre + source_quote + contact. **Pas de taxonomie structurée** (pas de `blocker_type` enum).
13. **Cluster thématique cross-type** par `what × dimension` : Qualification seulement (Pain/Obj/Imp/TS). **Les Freins ne participent PAS au cluster thématique**.
14. **Suggestion LLM next-step = signal de type NextStep**, lifecycle SignalStatus standard (PENDING / VALIDATED / REJECTED + ARCHIVED).
15. **Dismiss d'une suggestion = REJECTED**. Retrouvable via filtre statut dans la vue Flat de Signals.
16. **Activity créée depuis NextStep validé** porte FK `next_step_signal` vers le signal source. Chaînage indirect vers l'Activity-call via `signal.source_activity`.
17. **Distinction REJECTED / ARCHIVED** côté data : REJECTED = faux d'origine, ARCHIVED = vrai mais obsolète. ARCHIVED géré par futur Deal Health / Prep Call (re-validation client lors d'un appel).
18. **Pas de champ `is_actionable`** sur les modèles. Service dérivé pour les suggested actions (hors scope cette itération).
19. **Bouton Run AI Analysis** dans Notes uniquement. Pas de duplication sur Signals ou Next Steps. Badge état dans ActivityHeader pour visibilité globale.
20. **Cards Next Step structurées Quand / Quoi / Qui / Pourquoi** : variants visuels distincts pour AI Suggestion (bordure dashed orange, badge IA) vs Activity planifiée (bordure neutre solid).
21. **Section Next Steps avec 2 sous-sections explicites** : AI Suggestions PENDING (haut) + Planned Activities (bas).
22. **`source_quote` mise au cœur** des cards signals (vue Flat) et des cards AI Suggestion.
23. **Confidence cachée** côté UI (risque d'embrouille).
24. **Activity peut être COMPLETED même avec signaux PENDING** : la complétion n'est pas bloquée. Compteur global persiste tant qu'il reste du PENDING.

---

## 11. Questions ouvertes à trancher en implémentation

1. **Champ notes subjectives dans Notes** : nouveau champ `Activity.notes` ou réutilisation de `outcome_notes` / `description` ? Trancher avec backend.
2. **Pipeline `qualification-signals`** : renommer l'endpoint existant `transcript-signals` ou créer un nouveau et déprécier l'ancien ?
3. **Création Activity depuis NextStep validé** : tout côté frontend (Activity create standard + FK explicite) ou nouvel endpoint backend dédié (`POST module-activities/from-next-step/{signal_id}/`) ?
4. **Click sur ligne signal vue Grouped** : drawer compact (mon vote) ou jump vers vue Flat avec signal pré-sélectionné ?
5. **Transformation card LLM après Create** : animation in-place (mon vote) ou disparait+apparait dans Planned Activities ?
6. **Cas PARTIAL** : retry du stage manquant seul (si techniquement possible côté backend) ou retry complet ?
7. **Champ `summary` ou `title` court** pour affichage compact des signaux (vue Grouped) : dérivé de `original_value`, dérivé par template, ou nouveau champ ? À voir avec backend.
8. **Devenir de `WizardSignalAdd.jsx`** : conservé en fallback simple pour `+ Add manually` depuis vue Flat ?
9. **Propagation compteurs aux listes externes** (Account Activities tab, Campaign Playlist) : in scope cette itération ou reporté ?
10. **Modélisation backend du signal Blocker** (texte libre, pas de what×dimension) : nouveau type concret `BlockerSignal` héritant de `BaseSignal` mais avec des champs spécifiques minimaux ? À cartographier dans la conversation suivante.
11. **Modélisation backend du signal NextStep** : nouveau type concret `NextStepSignal` ? Structure du payload (titre, type, due_date, contacts) ? À cartographier dans la conversation suivante.
12. **Onglet par défaut à l'ouverture** d'une Activity : Overview (état actuel) ou Notes si pas encore complétée et signaux PENDING ?
13. **`Activity.next_step_signal` FK** : nouveau champ sur le modèle Activity pour la traçabilité création depuis suggestion ?

---

## 12. Hors scope cette itération — à traiter dans le prochain rapport

- Cartes thématiques cross-type côté Account Qualification (sections Pain / Objective / Impact / Metrics / Evidence / Missing).
- Refonte `AccountSignalsTab` (vue à plat des signaux du compte) — partage `SignalDetailCard` avec l'onglet Activity Signals vue Flat.
- DC : signaux du DC vs signaux hérités du compte, freshness/dormancy/staleness visible et filtrable.
- Pipeline Deal Health (nom non encore tranché, placeholder DealHealth) — lancé depuis le DC, output rhéto-sentimental par stakeholder.
- Suggested actions service (dérivation par règles déterministes à partir du contenu d'un thème ou d'un cluster).
- Prep Call pipeline (futur).
- Account Overview (cartes thématiques agrégées).
- Propagation des compteurs PENDING aux listes externes (Account Activities tab, Campaign Playlist) — à confirmer.

---

## 13. Diagramme de flux résumé

```
                    ┌─────────────────────────┐
                    │   Pendant / juste après │
                    │       le call           │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   Onglet NOTES          │
                    │   (capture transcript)  │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Click Run AI Analysis  │
                    │  → Wizard 2 steps       │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Run en arrière-plan    │
                    │  (wizard fermé, spinner │
                    │   sur bouton, AE libre) │
                    └───────────┬─────────────┘
                                │
                  ┌─────────────┴─────────────┐
                  ▼                           ▼
        ┌──────────────────┐        ┌──────────────────┐
        │  Pipeline        │        │  Pipeline        │
        │  qualification-  │        │  next-steps      │
        │  signals         │        │                  │
        └────────┬─────────┘        └────────┬─────────┘
                 │                           │
                 ▼                           ▼
        ┌──────────────────┐        ┌──────────────────┐
        │  Signaux Pain/   │        │  Signaux         │
        │  Obj/Imp/TS/     │        │  NextStep        │
        │  Blocker PENDING │        │  PENDING         │
        └────────┬─────────┘        └────────┬─────────┘
                 │                           │
                 ▼                           ▼
        ┌──────────────────┐        ┌──────────────────┐
        │  Onglet SIGNALS  │        │  Onglet NEXT     │
        │  Vue Grouped/    │        │  STEPS           │
        │  Flat avec       │        │  Cards AI        │
        │  validation      │        │  + Activities    │
        │  inline          │        │  planifiées      │
        └────────┬─────────┘        └────────┬─────────┘
                 │                           │
        ┌────────┴────────┐         ┌────────┴─────────┐
        ▼                 ▼         ▼                  ▼
   ┌─────────┐       ┌─────────┐  ┌──────────┐    ┌─────────┐
   │VALIDATED│       │REJECTED │  │ Create   │    │REJECTED │
   │         │       │         │  │ Activity │    │         │
   │ feeds   │       │ stays   │  │ (FK to   │    │ stays   │
   │ clusters│       │ for     │  │ next_    │    │ for     │
   │ Account │       │ audit   │  │ step_    │    │ audit   │
   │ + DC    │       │         │  │ signal)  │    │         │
   └─────────┘       └─────────┘  └──────────┘    └─────────┘

                                ▼
                    ┌─────────────────────────┐
                    │   Click Complete dans   │
                    │   ActivityHeader        │
                    │   → Modale outcome      │
                    │   → Activity COMPLETED  │
                    └─────────────────────────┘
```

---

_Fin du rapport. Base de référence pour l'implémentation du post-call Activity Workspace. Version 2, mai 2026._
