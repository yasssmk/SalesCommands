# SalesCommands — UX / UI Guidelines

Conventions d'interface durables, indépendantes des sprints. Le ROADMAP
journalise ce qui est livré ; ce fichier fige **comment** l'UI doit se
comporter, pour que chaque nouvel écran s'y conforme sans re-débat.

---

## Contrat UI — Drawers

Le drawer (la « coque » unique du workspace) est un **espace de travail
persistant**, pas une modale jetable. Tous les drawers — lecture d'un signal,
édition, fiche contact/activité/user, outcome — suivent les 7 règles
ci-dessous. **Pattern de référence : les drawers Objective (détail + edit).**

### 1. En-tête (uniforme)
Une seule ligne : **Titre** (grand, gras, à gauche) + **pill statut** (si
l'objet porte un statut — en **LECTURE seulement**) + **×** (à droite).
- Beaucoup de modèles ont un statut → le pill statut apparaît en en-tête des
  drawers de **lecture**.
- Les drawers **édition n'ont PAS de pill statut**.
- Le titre est porté de façon **cohérente** : jamais de double titre (soit la
  coque, soit le contenu — pas les deux).

### 2. Structure
- **Signaux** (détail + edit) : sections **NUMÉROTÉES** (badge index + titre).
- **Objets simples** (contact, activité, user) : groupes séparés par des
  **FILETS**, sans numéros.

### 3. Label / valeur
- **Détail (lecture)** :
  - valeur **MONO-LIGNE** → **2 colonnes** (label à gauche / valeur à droite) ;
  - valeur **MULTI-LIGNE** (summary, description, notes, quote, critères) →
    **PLEINE LARGEUR** (label au-dessus, valeur en dessous).
- **Édition** : toujours **EMPILÉ** (label au-dessus, champ en dessous).

### 4. Sous-titres
Uniquement pour les **signaux / modèles complexes-ambigus**, et uniquement en
**ÉDITION** (pour guider la saisie). Jamais sur contact / activité / user ;
jamais en lecture.

### 5. Fond de bloc
**UN SEUL** bloc-clé par drawer mis en valeur par un fond : l'information
principale, « c'est quoi cet objet ».
- Objective → **Goal** ; Contact → **identité** ; Outcome → **sélecteur**.
- Jamais décoratif, jamais multiple.

### 6. Barre d'actions
En **bas à droite**, position + composants + couleurs **FIXES** (un composant
unique).
- **Lecture signal** : Edit (neutre) · Reject (error, outline) · Validate
  (success, plein).
- **Édition** : Cancel (texte) · Save / Complete (plein, désactivé si
  invalide).

### 7. Coque
Arrondie, sticky, fond anthracite, **×**.

### Comportement de navigation (règle forte)
**Seuls le × et le changement de page ferment le drawer.** Toutes les autres
actions — Validate, Reject, Save, Cancel — **gardent le drawer OUVERT** et
**ramènent au DÉTAIL** (statut et valeurs mis à jour). Le drawer est un espace
de travail persistant : on y enchaîne les gestes sans jamais perdre le
contexte.

### Composants partagés qui incarnent le contrat
À consolider (une seule implémentation, réutilisée partout) :
- **En-tête de drawer unifié** (titre + pill statut optionnel + ×).
- **SectionHeader partagé** (badge index + titre + sous-titre optionnel).
- **Barre d'actions unique** (jeux de boutons + couleurs fixes par régime).
- **LabeledValue** (2 colonnes / pleine largeur automatique selon mono- ou
  multi-ligne).
