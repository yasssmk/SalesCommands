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

---

## Doctrine couleurs

Doctrine validée au fil du chantier UX Activity. Elle s'applique à **tout**
nouvel écran : couleur, texte, surfaces, icônes se décident ici, sans re-débat.

### Principe d'or
Toute couleur vient d'un **RÔLE DE THÈME** (token), **jamais** d'une valeur en
dur (hex / rgba). Ainsi, quand le branding aphoriQ passera `primary` au bleu,
**toute l'UI se met à jour** sans retoucher un seul composant.

### Rôles sémantiques
- **primary** = l'**action principale** d'un écran (Save, Complete, action
  clé). *Aujourd'hui vert, demain bleu (aphoriQ) — on raisonne en rôle, jamais
  « vert ».*
- **success** = la **validation / l'état validé** (bouton Validate, pill
  « Validated »). Distinct de `primary`.
- **error** = **problème / rejet / action requise** (Reject, overdue).
- **warning** = **en attente / à traiter** (Pending, « N to validate »).
- **text.secondary** (= `aphoriQ.text.muted`) = le **GRIS NEUTRE STANDARD** :
  texte muted, ligne info, labels, placeholders, bouton **Edit** (lecture),
  **✎**, éléments secondaires.
- **text.primary** = **texte principal**.

### Texte & liens
- Le texte important se met en valeur par le **GRAS** (`fontWeight` bold), pas
  par une couleur.
- Les **liens** : **gras neutre au repos** → au **HOVER**, `primary` + souligné
  (pattern des contacts du Context / noms account-DC du header). Un lien ne se
  signale **pas** par une couleur au repos.

### Surfaces (fonds)
- **3 niveaux** : fond de **PAGE** (`background.default`), **CARTES /
  conteneurs**, **BLOC MIS EN VALEUR**. Tout fond vient d'un **token surface**
  (`surface.level*`), **JAMAIS** une couleur ad hoc (ex. `action.hover`) qui
  « ressemble ».
- Le **padding / les marges** des drawers sont imposés par la **coque** +
  `DrawerContentLayout`, **jamais** par les vues.

### Icônes
- Les icônes vivent dans les **CONSTANTES** du module (source unique),
  importées partout — ex. `SIGNAL_ICON` (`utils/signalTypes.js`) réutilisé par
  la bande Signals, le header, la fiche contact. **Jamais** d'import d'icône
  dupliqué en dur dans chaque composant.

### Interdits
- Pas de couleur **DÉCORATIVE** : une teinte ne s'utilise que pour porter un
  **SENS** (action, statut, alerte).
- Pas de couleur / valeur **EN DUR** (hex, px, rem) dans les composants —
  toujours un token / une constante. Si un token manque, il se **crée dans le
  thème**, il ne se hardcode pas.

### Exceptions assumées (tracées)
- Les **9 couleurs de type de signal** (`aphoriQ.signalColors`) sont des hex
  fixes dédiés, à re-tinter au branding — exception documentée.
- `background.default` (`grey.A50`) ne s'inverse pas encore proprement
  clair / sombre → à corriger au sprint aphoriQ.
