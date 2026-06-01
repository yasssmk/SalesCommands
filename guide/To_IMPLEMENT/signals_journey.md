# Signals -> Decision Cycle — Voyage de la donnée & vues

**Version** : 2 (mai 2026)
**Objectif** : valider la faisabilité de bout en bout en traçant le voyage de chaque signal, du transcript jusqu'à chaque vue du DC Workspace. Puis préparer la vue Prep Call en définissant le contrat JSON consommable avant chaque RDV important.
**Changements v1 -> v2** : nouveaux types de signaux (People, Contrainte) ; Metric logé dans Contrainte ; résistance rattachée à un acteur ; concurrent via TechStack ; attribution `target_department` ; `human_impact` self-report ; intégration de la règle Themes <-> People (même matière, deux pivots) ; modèle mental à trois niveaux.

---

## Partie 0 — Le modèle mental (clé de lecture)

Un deal = faire avancer une vente à travers des étapes, en donnant à chaque acteur ce qui le débloque. **Trois vues, trois niveaux, un moteur** :

| Vue             | Question                       | Niveau           |
| --------------- | ------------------------------ | ---------------- |
| **Themes**      | Quel est le problème ?         | le SUJET         |
| **People**      | Comment je parle à qui ?       | l'ACTEUR         |
| **Deal Health** | Où on en est, comment gagner ? | le DEAL (global) |

**Moteur — Prep Call** : croise les trois à chaque étape, donne la combinaison de l'interlocuteur du prochain call, liste ce qu'il faut récupérer.

**Règle anti-confusion** : Themes et People sont **la même matière, deux pivots** (par sujet / par acteur). Le **détail** de la qualif ne s'affiche qu'à un seul endroit (**Themes**) ; People **résume** et ajoute sa **couche exclusive** (rôle, critères/contraintes, résistances).

---

## Partie 1 — Le voyage des signaux (transcript -> DC Workspace)

### 1.1 Vue d'ensemble du flux

```
                        +--------------------------+
                        |   TRANSCRIPT (Activity)   |
                        |   colle dans l'onglet     |
                        |   Notes du call           |
                        +------------+--------------+
                                     |
                          Run AI Analysis (wizard)
                          + sanitization (UUID subst.)
                                     |
                        +------------v--------------+
                        |  Pipeline qualification-   |
                        |  signals (LLM)             |
                        |  extraction multi-type     |
                        +------------+--------------+
                                     |
   +--------+--------+--------+------+-----+--------+--------+----------+
   v        v        v        v     v     v        v        v          v
 Pain   Objective Impact  TechStack Frein People Contrainte NextStep  (...)
   |        |        |        |       |     |       |          |
   +--------+--------+--------+-------+-----+-------+----------+
                                     |
                   Chaque signal cree en PENDING
                   + attribution best-effort :
                     - canonical_key (what x dim, ou catalog)
                     - target_department (le concerne)
                     - scope_level (business/dept/perso)
                     - source derivee de source_activity
                     - human_impact SI self-report
                     - role/rigidity selon le type
                                     |
                        +------------v--------------+
                        |  VALIDATION HUMAINE        |
                        |  (onglet Signals, Activity)|
                        |  PENDING -> VALIDATED /      |
                        |  REJECTED                  |
                        +------------+--------------+
                                     |
                          Signaux VALIDATED uniquement
                                     |
   +----------------+----------------+----------------+----------------+
   v                v                v                v                v
 PIVOT par         PIVOT par         PIVOT par        CONTEXTE         ACTIONS
 canonical_key     target_dept       acteur+role      decision_cycle   NextStep ->
 = Themes          = People          (role, code,     (null=account,   activites /
 (detail qualif)   (resume +         resistances)     set=ce DC)       acteurs
                    couche exclusive)                                   (ex. CFO)
   +----------------+----------------+----------------+----------------+
                                     |
                        +------------v--------------+
                        |   DC WORKSPACE             |
                        |   (5 onglets)              |
                        +------------+--------------+
                                     |
   +----------+--------------+-------+--------+-----------------+
   v          v              v       v        v
Timeline   People       Products  Strategic  Signals
(activites)(par dept)  &Financial (Deal Health (a plat)
                                   + Themes)
                                       |
                          Run Deal Health (manuel, DC-level)
                          Evidence Pack = signaux valides
                          + transcripts + contexte + snapshot
                                       |
                        +--------------v--------------+
                        |  Pipeline deal-health (LLM)  |
                        |  -> snapshot date            |
                        +------------------------------+
```

### 1.2 Voyage detaille, type par type

| Type                         | Cle d'agregation         | Attribution « concerne »                                   | Vues du DC ou il atterrit                                                                              |
| ---------------------------- | ------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Pain**                     | `pain:<what>:<dim>`      | `target_department` (MVP) + `scope_level`                  | Themes (detail) ; People (resume, acteur produit) ; Deal Health (Probleme/Douleur)                     |
| **Objective**                | `objective:<what>:<dim>` | `target_contact`/`target_department` (existant)            | Themes (detail) ; People (resume) ; Deal Health (Gain desire) ; Strategic -> Desirs                    |
| **Impact**                   | `impact:<what>:<dim>`    | `target_department` (MVP) ; `human_impact` si self-report  | Themes (detail) ; People (resume, acteur produit) ; Deal Health (Impact compris) ; Strategic -> Valeur |
| **TechStack**                | `techstack:<catalog_id>` | `usage_department` ; `decision_cycle` null/set             | Themes (cluster tech) ; Deal Health (Confiance solution si concurrent)                                 |
| **Frein** (Blocker)          | (pas de cluster)         | acteur (contact/dept) — **humaine**                        | People (sous l'acteur qui resiste) ; Strategic -> Cout ; Discovery Gaps                                |
| **Contrainte** (Constraint)  | (deal/dept)              | `target_department` + `rigidity` ; porte le **Metric (M)** | People (acteur process) ; Strategic -> Contraintes ; Deal Health (Volonte d'agir)                      |
| **People** (StakeholderRole) | (par contact/dept)       | role MEDDPICC + influence                                  | People (structure les roles) ; bandeau (alertes role manquant)                                         |
| **Next Step**                | (pas de cluster)         | —                                                          | cree activites / acteurs (ex. CFO via task)                                                            |

### 1.3 Les trois projections de la meme matiere

Point de faisabilite crucial : **un seul corpus de signaux valides, trois angles de lecture** — pas de duplication.

```
        SIGNAUX VALIDES (corpus unique)
                    |
   +----------------+----------------+
   v                v                v
 PAR canonical_key  PAR target_dept  PAR niveau (scope) + type
 = Themes           = People         = Strategic / Leviers
 "quels sujets"     "qui est         "sur quoi
 (detail)            concerne"        j'appuie"
                    (resume + role/
                     criteres/
                     resistances)
```

- **Themes** = pivot par `canonical_key` (what x dimension) -> **detail complet** de la qualif.
- **People** = pivot par `target_department` -> **resume** + couche exclusive (role, criteres/contraintes, resistances).
- **Strategic (leviers)** = pivot par `scope_level` + type -> Desirs / Contraintes / Valeur / Cout.

Aucune donnee n'est recopiee. Chaque vue est une requete differente sur le meme ensemble. Le **detail de la qualif n'est montre qu'une fois (Themes)** ; People y renvoie. C'est ce qui rend l'architecture tenable et non redondante.

### 1.4 Ce qui depend du LLM vs ce qui est deterministe

| Element                     | Origine                                             | Sans LLM                                     |
| --------------------------- | --------------------------------------------------- | -------------------------------------------- |
| Signaux (extraction)        | pipeline qualification-signals                      | saisie manuelle possible                     |
| Clusters Themes             | agregation deterministe sur canonical_key           | disponible des qu'il y a des signaux valides |
| Page People                 | agregation deterministe (target_department + roles) | disponible                                   |
| Onglet Signals              | liste directe                                       | disponible                                   |
| Readiness score             | calcul deterministe                                 | disponible                                   |
| **Diagnostic 7 dimensions** | pipeline deal-health                                | **vide + CTA**                               |
| **Discovery Gaps**          | pipeline deal-health                                | **vide + CTA**                               |
| **Leviers priorises**       | pipeline deal-health                                | affichables a plat (non priorises)           |

### 1.5 Regles d'attribution a l'extraction (a encoder dans le prompt)

- **source =/= concerne** : la source (qui parle) est derivee de `source_activity.contacts` ; le `target_department` (qui est concerne) est attribue par le LLM en best-effort, independamment du speaker (le DSI peut parler d'un pain du Marketing).
- **human_impact = self-report uniquement** : posee seulement si le speaker est la personne concernee par l'impact human. Sinon, pas de dimension human.
- **resistance = humaine** : un Frein est toujours rattache a un acteur, jamais « business » abstrait.
- **concurrent** : un TechStack dont l'entree catalogue porte `is_competitor` ; `decision_cycle` null = en place / set = en lice sur ce deal.
- **dependance honnete** : la qualite de l'attribution depend de la presence de speakers nommes dans le transcript. Transcript anonyme (« Speaker 1/2 ») -> attribution au niveau departement au mieux.

---

## Partie 2 — Resume des vues du DC Workspace

Pour chaque vue : objectif, message porte, valeur ajoutee, comment elle aide le sales, a quel moment.

### 2.1 Bandeau d'identite

- **Objectif** : situer le deal en 3 secondes.
- **Message** : « Voici ce deal, sa valeur, son etape, sa prochaine action. »
- **Valeur ajoutee** : ancrage permanent.
- **Aide le sales** : repere immediat ; lance Deal Health d'ici.
- **Quand** : en continu, en-tete de toutes les vues.

### 2.2 Timeline

- **Objectif** : voir l'execution operationnelle + les criteres de passage de chaque etape.
- **Message** : « Voici ce qui s'est passe, ce qui est prevu, et ce qu'il faut accomplir pour valider chaque etape. »
- **Valeur ajoutee** : chronologie claire + attentes de step (clic sur en-tete de colonne).
- **Aide le sales** : sait ou en est l'avancement et ce qui valide l'etape en cours.
- **Quand** : suivi quotidien, planification.

### 2.3 People (par departement + roles filtrables)

- **Objectif** : comprendre la cartographie humaine et savoir comment aborder chacun.
- **Message** : « Voici qui decide, son role, son code, ce qui le touche ou ses criteres, ses resistances. »
- **Valeur ajoutee** : organise par acteur ; resume la qualif (renvoie a Themes) + couche exclusive (role, criteres, resistances) ; signale les roles critiques manquants.
- **Aide le sales** : adapte son pitch a chaque persona ; trouve le bon point d'entree.
- **Quand** : avant un call avec un interlocuteur donne.

### 2.4 Products & Financial

- **Objectif** : cadrer le perimetre commercial.
- **Message** : « Voici ce qui est en jeu, en produits et volume. »
- **Valeur ajoutee** : taille du deal explicite, sans amplification.
- **Aide le sales** : dimensionne sa proposition.
- **Quand** : construction de l'offre.

### 2.5 Strategic — Deal Health

- **Objectif** : diagnostiquer la maturite d'achat et donner les leviers.
- **Message** : « Voici ou en est leur conviction, ce qu'on ne sait pas encore, et sur quoi appuyer. »
- **Valeur ajoutee** : transforme les signaux en lecture strategique honnete (preuves capturees) ; diagnostic PUIS leviers.
- **Aide le sales** : sait s'il faut creuser, convaincre, rassurer ou pousser.
- **Quand** : preparation d'un call strategique ; revue de deal ; supervision.

### 2.6 Strategic — Themes

- **Objectif** : descendre dans le detail par problematique business.
- **Message** : « Voici, sujet par sujet, les douleurs, objectifs, impacts et freins. »
- **Valeur ajoutee** : le seul endroit ou vit le detail complet de la qualif (cross-type).
- **Aide le sales** : approfondit un sujet avant de l'aborder ; voit les signaux sources.
- **Quand** : deep dive ; construction d'un argumentaire cible.

### 2.7 Signals (a plat)

- **Objectif** : acceder a la matiere premiere.
- **Message** : « Voici tous les signaux bruts, editables. »
- **Valeur ajoutee** : transparence, controle, gestion fine (valider/rejeter/archiver).
- **Aide le sales** : verifie une source, corrige une attribution.
- **Quand** : maintenance de la donnee ; doute sur un element du diagnostic.

---

## Partie 3 — Preparation de la vue Prep Call : contrat JSON

### 3.1 Principe

Avant chaque RDV important, le pipeline **prep-call** (futur) lit ce que le deal a accumule et produit un game plan cible sur l'interlocuteur du prochain call. Il consomme un **Prep Input Pack** assemble depuis les signaux valides, le dernier Deal Health, et le contexte du call a venir. L'objectif : guider l'AE — meilleurs leviers, arguments, strategie, questions a poser.

### 3.2 Ce que le Prep Call doit pouvoir recuperer

Structure pour repondre a : « pour CE call, avec CETTE personne, a CETTE etape — sur quoi j'appuie, que je creuse, que je rassure, et qu'est-ce que je propose comme next step ? »

```json
{
  "prep_context": {
    "decision_cycle_id": "dc_123",
    "account_name": "<sanitized>",
    "current_step": "SOLUTION_VALIDATION",
    "step_expectations": {
      "goal": "Valider le fit fonctionnel",
      "criterias": ["PoC concluant", "Validation IT"]
    },
    "upcoming_activity": {
      "type": "meeting",
      "date": "2026-06-03",
      "primary_contact": {
        "id": "ct_45",
        "role": "CHAMPION",
        "department": "Sales Ops"
      }
    },
    "deal_value": "180000",
    "last_deal_health_snapshot_date": "2026-05-22"
  },

  "maturity_snapshot": {
    "global_reading": "Probleme reconnu, mais douleur ressentie et urgence non prouvees.",
    "dimensions": [
      { "key": "problem_recognized", "status": "confirmed" },
      { "key": "felt_pain", "status": "missing_evidence" },
      { "key": "impact_understood", "status": "unclear" },
      { "key": "desired_gain", "status": "suggested" },
      { "key": "urgency", "status": "missing_evidence" },
      { "key": "willingness_to_act", "status": "unclear" },
      { "key": "solution_trust", "status": "suggested" }
    ]
  },

  "levers": {
    "desires": [
      {
        "summary": "Meilleure visibilite reporting",
        "department": "Sales Ops",
        "theme": "DATA x TIME"
      }
    ],
    "value": [
      {
        "summary": "10h/semaine recuperables",
        "department": "Sales Ops",
        "theme": "OPS x TIME"
      }
    ],
    "cost_frictions": [
      { "summary": "Budget non porte par le champion", "actor": "ct_45" }
    ],
    "constraints": [
      {
        "summary": "ROI > 20% sous 18 mois",
        "department": "Finance",
        "rigidity": "ferme",
        "is_metric": true
      },
      {
        "summary": "Deploiement avant cloture Q3",
        "department": "Finance",
        "rigidity": "flexible"
      }
    ]
  },

  "stakeholder_focus": {
    "contact_id": "ct_45",
    "role": "CHAMPION",
    "department": "Sales Ops",
    "their_desires": ["Meilleure visibilite reporting"],
    "their_pains": ["Reporting manuel 10h/semaine"],
    "their_resistances": ["Ne porte pas le budget"],
    "human_impact": [{ "type": "OVERLOAD", "self_reported": true }],
    "_note": "MVP : ciblage par departement (le contact precis arrive en V2)"
  },

  "discovery_gaps": [
    {
      "kind": "qualification",
      "dimension": "felt_pain",
      "public_text": "Le poids reel du reporting manuel n'est pas qualifie dans les preuves capturees.",
      "suggested_questions": [
        "Quand votre equipe passe 10h sur ce reporting, qu'est-ce que ca l'empeche de faire ?",
        "Est-ce vecu comme un vrai probleme en interne, ou comme une routine acceptee ?"
      ],
      "related_theme": "OPS x TIME"
    },
    {
      "kind": "procedural",
      "dimension": "decision_process",
      "public_text": "Le process de validation Finance est inconnu (duree, criteres, qui signe).",
      "suggested_questions": [
        "Une fois le PoC valide, quelles sont les etapes cote Finance avant signature ?",
        "Combien de temps prend habituellement cette validation chez vous ?"
      ],
      "related_actor": "Finance"
    }
  ],

  "competitive_context": {
    "incumbents": [{ "tool": "<catalog_name>", "is_competitor": true }],
    "competing_on_deal": []
  },

  "evidence_scope": {
    "validated_signals_count": 18,
    "transcripts_count": 4,
    "manual_context_count": 0,
    "coverage_note": "Base sur les preuves capturees."
  }
}
```

### 3.3 Comment chaque bloc guide l'AE

| Bloc JSON                              | Ce qu'il permet au Prep Call de produire                                                                                                |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `prep_context` (+ `step_expectations`) | Cadrer le call : etape, personne, valeur, et ce qu'il faut accomplir pour valider l'etape.                                              |
| `maturity_snapshot`                    | Savoir si on est en mode « creuser » (gaps) ou « pousser » (maturite haute).                                                            |
| `levers`                               | Construire l'argumentaire : amplifier les desirs, demontrer la valeur, lever les freins, respecter les contraintes / criteres (Metric). |
| `stakeholder_focus`                    | Personnaliser pour l'interlocuteur : ses desirs, ses resistances, son impact perso (si self-report) -> mobilisation ciblee.             |
| `discovery_gaps`                       | Generer les questions a poser — distinction qualif (creuser le besoin) vs procedural (clarifier le process). C'est le coeur tactique.   |
| `competitive_context`                  | Preparer la differenciation et le switching cost si concurrent en lice.                                                                 |
| `evidence_scope`                       | Cadrer l'honnetete : le game plan est base sur ce qui est capture.                                                                      |

### 3.4 Sortie attendue du Prep Call (esquisse)

A partir de ce pack, le Prep Call produira : objectifs du call, questions de decouverte prioritaires (issues des gaps), proposition de valeur a pousser (leviers), risques/objections a anticiper (freins + concurrent), criteres a satisfaire pour avancer l'etape (step_expectations), next step suggere. Conception detaillee hors scope ici.

### 3.5 Validation de faisabilite

Tous les champs sont **derivables de ce qu'on capture deja** :

- `levers`, `stakeholder_focus`, `competitive_context` -> signaux valides + `target_department` + Contrainte (Metric) + `human_impact` self-report.
- `maturity_snapshot`, `discovery_gaps` -> dernier snapshot Deal Health (gaps qualif + procéduraux).
- `prep_context` (+ step_expectations) -> DecisionStep + activite a venir.
- `evidence_scope` -> metadonnees.

**Reserve honnete** : `stakeholder_focus` s'appuie sur le ciblage **contact**, reporte en V2 (MVP = departement). En MVP, ce bloc cible le departement de l'interlocuteur, pas la personne. Le contrat est pret ; une partie ne se remplit finement qu'en V2.

-> **Faisabilite de bout en bout confirmee.**

---

_Fin du document v2. Valide le voyage des signaux du transcript au DC Workspace, resume la valeur de chaque vue, et etablit le contrat de donnees pour la future vue Prep Call._
