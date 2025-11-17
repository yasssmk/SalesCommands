# 🚀 WORKFLOW IMPLÉMENTATION NOUVEAU MODULE

**Version**: 2.0  
**Date**: 2025-01-14  
**Pré-requis**: Lire [MODULE_STANDARDIZATION_GUIDE.md](./MODULE_STANDARDIZATION_GUIDE.md) V2.0  
**Durée estimée**: 3-5 jours pour module complet

---

## 📋 VUE D'ENSEMBLE

**Contexte**: Les modèles Django et serializers de base EXISTENT déjà et sont bien pensés. Le workflow se concentre sur:

1. **Conception Frontend** (UX/UI) - 1 jour
2. **Standardisation Backend** (patterns, cache, audit) - 1 jour  
3. **Implémentation Frontend** (React components) - 1-2 jours
4. **Tests & Validation** - 0.5-1 jour

**Principe**: Frontend-first. On conçoit l'expérience utilisateur AVANT d'implémenter.

---

## 🎯 PHASE 0: ANALYSE DE L'EXISTANT (2h)

### Objectif
Auditer le code existant et identifier les gaps vs guide de standardisation.

### 0.1 Audit Modèle Django

**Fichier**: `backend/{module_name}/models/{entity}.py`

**✅ Checklist Modèle:**
```bash
# Lancer l'audit avec project_knowledge_search
```

- [ ] Champ `id` = UUID (primary_key=True)
- [ ] Champ `client_account` = FK vers ClientAccount (obligatoire)
- [ ] Champs `created_at`, `updated_at` (auto_now_add, auto_now)
- [ ] Champs `owner`, `created_by` (optionnels selon permissions)
- [ ] Meta: `db_table`, `ordering`, `indexes`
- [ ] Méthode `__str__()` définie
- [ ] Relations FK avec `related_name` cohérent

**Référence Guide**: §1.1 Structure Fichiers

**Action si gaps**: Noter les modifications à faire (Phase 2).

### 0.2 Audit Serializers

**Fichier**: `backend/{module_name}/serializers/{entity}_serializers.py`

**✅ Checklist Serializer:**

- [ ] Hérite de `ClientScopeManager.SerializerMixin`
- [ ] Serializer principal (`{Entity}Serializer`) complet
- [ ] Serializer list optimisé (`{Entity}ListSerializer`)
- [ ] Serializer create (`{Entity}CreateSerializer`) si validations spécifiques
- [ ] Serializer update (`{Entity}UpdateSerializer`) si validations spécifiques
- [ ] Validation `validate_name()` avec unicité par client
- [ ] Méthode `validate()` pour validations inter-champs
- [ ] `Meta.read_only_fields` définis correctement

**Référence Guide**: §2 Serializers

**Action si gaps**: Noter les méthodes à ajouter/corriger.

### 0.3 Audit ViewSet (si existant)

**Fichier**: `backend/{module_name}/views/{entity}_view.py`

**✅ Checklist ViewSet:**

- [ ] Hérite de `ScopedQuerysetMixin + BaseAPIView + ModelViewSet`
- [ ] Attribut `entity_name` défini
- [ ] Attribut `module` défini (pour permissions)
- [ ] `authentication_classes = [CustomJWTAuthentication]`
- [ ] `permission_classes = [IsAuthenticated, ScopedPermission]`
- [ ] `get_queryset()` avec annotations (éviter N+1)
- [ ] `list()` avec cache Redis
- [ ] `create()` avec `audit_log()` + cache invalidation
- [ ] Helper `_invalidate_all_related_caches()`

**Référence Guide**: §1 Architecture Backend

**Action si gaps**: C'est la Phase 2 qui corrigera.

### 0.4 Cartographie Dépendances

**CRITICAL**: Identifier TOUS les modules dépendants pour cache invalidation.

**Questions:**
1. Quels modules affichent un count de ce module ? → Invalider lors mutation
2. Quels modules ont une FK vers ce module ? → Invalider lors mutation
3. Ce module est-il affiché dans un dashboard/widget ? → Invalider

**Exemple**:
- Module `roles` → Invalider `users` (users_count, permissions)
- Module `users` → Invalider `roles`, `teams`, `organizations`
- Module `contacts` → Invalider `accounts`, `activities`

**Livrables Phase 0:**
- [ ] Document "Gaps Analysis" (liste modifications nécessaires)
- [ ] Cartographie dépendances (diagramme relations)

---

## 🎨 PHASE 1: CONCEPTION FRONTEND (1 jour - 8h)

### Objectif
Concevoir l'expérience utilisateur AVANT d'implémenter quoi que ce soit.

### 1.1 Questions UX Fondamentales (1h)

**Répondre PRÉCISÉMENT à ces questions:**

#### 1.1.1 Navigation & Accès

**Q1**: Où se situe ce module dans la navigation ?
- [ ] Menu drawer principal → Section quel niveau ? (ex: Administration, Sales, etc.)
- [ ] Breadcrumb path ? (ex: `Home / Administration / {Module}`)
- [ ] URL route ? (ex: `/admin/{module}`)

**Q2**: Qui peut accéder à ce module ?
- [ ] Admins uniquement
- [ ] Admins + Managers
- [ ] Tous les utilisateurs authentifiés
- [ ] Permission registry défini ? (Référence: Guide §6.1)

**Q3**: Feature flag nécessaire ?
- [ ] Oui → Nom du flag : `FEATURE_{MODULE_NAME}` dans `config/features.js`
- [ ] Non → Actif par défaut

#### 1.1.2 Liste / Table Principale

**Q4**: Quelles colonnes afficher dans la table ?

Lister **5-7 colonnes max** pour UX optimale:

1. **Nom/Titre** (toujours colonne 1, triable, searchable)
2. **Champ métier 1** (ex: Status, Type, Tier)
3. **Champ métier 2** (ex: Count, Montant, Date)
4. **Relation** (ex: Organization, Team, Owner)
5. **Timestamp** (Created ou Updated, triable)
6. **Actions** (View/Edit/Delete, non triable)

**Référence**: `frontend/src/views/admin/roles/list.jsx` (colonnes définies ligne ~150)

**Q5**: Quelles colonnes sont triables ?
- [ ] Nom/Titre
- [ ] Champs métier (lesquels ?)
- [ ] Timestamps
- [ ] Relations (nom relation triable ? ex: `role__name`, `team__name`)

**Mapping backend obligatoire**: Créer `COLUMN_TO_BACKEND_FIELD` (Référence: Guide §8.2)

**Q6**: Pagination ?
- [ ] Oui (OBLIGATOIRE)
- [ ] Taille par défaut : **10** (roles) ou **50** (users) ?
- [ ] Max page size : **100** (OBLIGATOIRE pour performance)
- [ ] Persistance dans localStorage ? → Oui (OBLIGATOIRE)

**Q7**: Recherche ?
- [ ] Oui → Champs searchables backend : (ex: `name`, `email`, `description`)
- [ ] Non (rare, justifier)

**Q8**: Filtres additionnels ? (au-delà de search)
- [ ] Oui → Quels filtres ? (ex: Status, Type, Date range)
- [ ] Non → Search suffit

#### 1.1.3 Actions Utilisateur

**Q9**: Quelles actions sur les entités ?

**Actions standard** (cocher ce qui s'applique):
- [ ] **View** (Read-only modal) → Créer `{Entity}ViewModal.jsx`
- [ ] **Add/Create** → Créer `Form{Entity}Add.jsx`
- [ ] **Edit** → Créer `Form{Entity}Edit.jsx`
- [ ] **Delete** → Créer `Alert{Entity}Delete.jsx`

**Actions bulk** (optionnel MVP):
- [ ] **Bulk Edit** → Créer `Form{Entity}BulkEdit.jsx`
- [ ] **Bulk Delete** → Créer `Alert{Entity}BulkDelete.jsx`
- [ ] **CSV Import/Export** → Créer `{Entity}CSVImportModal.jsx`

**Actions custom** (business logic):
- [ ] Action custom 1 : ___________ → Backend endpoint `@action`
- [ ] Action custom 2 : ___________ → Backend endpoint `@action`

**Q10**: Protections/Validations sur actions ?

Exemples:
- [ ] **Delete** interdit si entité a relations (ex: role avec users assignés)
- [ ] **Edit** interdit si entité système (ex: role Admin locked)
- [ ] **Create** limité (ex: max 10 roles par tenant)

**Référence Backend**: Guide §1.8 create(), §2.5 Update Serializer

#### 1.1.4 Formulaires

**Q11**: Formulaire Create - Quels champs ?

Lister champs avec:
- Type (text, select, date, etc.)
- Requis/Optionnel
- Validation (ex: min/max length, regex, etc.)
- Valeur par défaut

**Exemple**:
```
1. Name (text, requis, 2-100 chars)
2. Type (select, requis, options: [Type1, Type2])
3. Description (textarea, optionnel, max 500 chars)
4. Related Entity (autocomplete, optionnel, FK vers autre table)
5. Active (toggle, optionnel, default: true)
```

**Q12**: Formulaire Edit - Différences vs Create ?
- [ ] Identique
- [ ] Certains champs read-only en edit (lesquels ?)
- [ ] Validations différentes (lesquelles ?)

**Q13**: Formulaire - Sections multiples ?
- [ ] Non → Formulaire simple
- [ ] Oui → Lister sections:
  1. Section 1: ___________ (champs: ...)
  2. Section 2: ___________ (champs: ...)

**Exemple** (Role management):
- Section 1: Basic Info (name, tier)
- Section 2: Permissions Preview (read-only, computed)

#### 1.1.5 Modals & Dialogs

**Q14**: Taille des modals ?
- [ ] `sm` (small) - Confirmations simples
- [ ] `md` (medium) - Formulaires standards
- [ ] `lg` (large) - Formulaires complexes / Preview
- [ ] `xl` (extra-large) - Très rares

**Q15**: Delete confirmation - Message spécifique ?

**Standard**: "Are you sure you want to delete {entity_name}?"

**Custom si**:
- [ ] Relations existantes (ex: "Cannot delete. X users assigned to this role.")
- [ ] Dernière entité critique (ex: "Cannot delete last admin role.")

**Référence Backend**: Guide §2.5 Update Serializer (protections)

#### 1.1.6 États Spéciaux

**Q16**: Empty state - Message ?

**Standard**: "No {entities} found. Create your first {entity}."

**Custom message** ? ___________

**Q17**: Loading state - Type ?
- [ ] Skeleton (PRÉFÉRÉ) → Utiliser `<Skeleton />` MUI
- [ ] Spinner (fallback)

**Q18**: Error state - Actions ?
- [ ] Retry button (OBLIGATOIRE)
- [ ] Message friendly (OBLIGATOIRE)
- [ ] Link support/docs (optionnel)

**Référence Frontend**: Guide §8 Frontend React

### 1.2 Choix Composants Material-UI (1h)

**Référence MUI**: https://mui.com/material-ui/

**Pour chaque champ formulaire, choisir composant MUI:**

| Champ Type | Composant MUI | Props Importants |
|------------|---------------|------------------|
| Texte simple | `TextField` | variant, required, helperText |
| Texte long | `TextField` multiline | rows, maxRows |
| Select simple | `Select` + `MenuItem` | label, value, onChange |
| Autocomplete | `Autocomplete` | options, getOptionLabel, renderInput |
| Date | `DatePicker` (@mui/x-date-pickers) | format, disablePast/Future |
| Toggle | `Switch` | checked, onChange |
| Checkbox | `Checkbox` | checked, onChange |
| Radio group | `RadioGroup` + `Radio` | value, onChange |
| File upload | `Button` + input[type=file] | accept, onChange |

**Composants liste/table:**

| Usage | Composant | Notes |
|-------|-----------|-------|
| Table principale | `ReusableTable` (custom) | **NE PAS réinventer** |
| Actions row | `IconButton` | Avec icons Ant Design |
| Badge status | `Chip` | color, size, variant |
| Empty state | `Box` + `Typography` | textAlign center |
| Skeleton | `Skeleton` | variant="rectangular" |

**Layout:**

| Usage | Composant | Notes |
|-------|-----------|-------|
| Page container | `Box` | sx={{ p: 3 }} |
| Card wrapper | `Card` + `CardContent` | Pour sections |
| Modal | `Dialog` | maxWidth="md" |
| Form layout | `Grid` container/item | spacing={3} |
| Button group | `Stack` direction="row" | spacing={2} |

### 1.3 Wireframes / Maquettes (2h)

**Créer wireframes pour:**

1. **Page liste principale** (layout complet)
   - Header avec titre + bouton "Add"
   - Table avec colonnes définies
   - Pagination footer
   - Empty state si aucune donnée

2. **Modal Create** (formulaire)
   - Tous les champs
   - Boutons Cancel/Save
   - Validation messages placement

3. **Modal Edit** (si différent de Create)

4. **Modal Delete confirmation**
   - Message
   - Boutons Cancel/Delete

5. **Modal View** (read-only, si applicable)

**Outils suggérés**:
- Figma (collaborative)
- Excalidraw (rapide)
- Papier/crayon (MVP rapide)

**Livrables**:
- [ ] Wireframes annotés (fichiers image/PDF)
- [ ] Document "UX Specifications" avec réponses aux 18 questions

### 1.4 Définir Comportements (2h)

**Documenter PRÉCISÉMENT les comportements:**

#### 1.4.1 Pagination

**Comportement**:
1. Utilisateur arrive sur page → Charger page 1, pageSize depuis localStorage (défaut 10)
2. Utilisateur change page → Appel API avec nouveau page number
3. Utilisateur change pageSize → Persister dans localStorage, reset page à 1, appel API
4. Recherche → Reset page à 1

**State management**:
```javascript
const [page, setPage] = useState(1);
const [pageSize, setPageSize] = useLocalStorage('{entity}TablePageSize', 10);
```

**Référence**: Guide §8.2, fichier `frontend/src/views/admin/roles/list.jsx` ligne ~70

#### 1.4.2 Recherche

**Comportement**:
1. Utilisateur tape dans search → Debounce 300ms
2. Après debounce → Appel API avec param `search`, reset page à 1
3. Search vide → Appel API sans param search

**State management**:
```javascript
const [search, setSearch] = useState('');
```

#### 1.4.3 Tri (Sorting)

**Comportement**:
1. Click colonne header → Toggle sort direction (asc → desc → none)
2. Multi-sort ? Non (MVP) → Un seul tri actif
3. TanStack Table format → Convertir en Django ordering string

**State management**:
```javascript
const [sorting, setSorting] = useState([]); // Format: [{ id: 'name', desc: false }]

const ordering = useMemo(() => {
  if (!sorting?.length) return '';
  const { id, desc } = sorting[0];
  const backendField = COLUMN_TO_BACKEND_FIELD[id] || id;
  return desc ? `-${backendField}` : backendField;
}, [sorting]);
```

**Référence**: Guide §8.2, fichier `list.jsx` ligne ~90-100

#### 1.4.4 Modals

**Comportement Add/Edit**:
1. Click "Add" button → Open modal, formulaire vide
2. Click "Edit" icon row → Open modal, pré-remplir avec data row
3. Submit valid → Appel API, close modal, revalidate SWR, snackbar success
4. Submit invalid → Afficher errors inline, modal reste ouverte
5. Click Cancel → Close modal, reset form

**State management**:
```javascript
const [addModal, setAddModal] = useState(false);
const [editModal, setEditModal] = useState(false);
const [selectedEntity, setSelectedEntity] = useState(null);
```

**Comportement Delete**:
1. Click "Delete" icon → Open confirmation dialog
2. Validation backend (ex: relations) → Afficher warning, disable Delete button
3. Confirm delete → Appel API, close dialog, revalidate, snackbar
4. Cancel → Close dialog

#### 1.4.5 Error Handling

**Comportement**:
1. API error → Afficher error state dans table avec:
   - Message friendly (pas technique)
   - Bouton "Retry"
   - Optionnel: Countdown auto-retry

2. Form validation error → Afficher inline sous champs

3. Network error → Snackbar error global

**Référence**: `frontend/src/utils/displayError.js`, `useErrorWithRetry` hook

### 1.5 i18n & Breadcrumb (1h)

#### 1.5.1 Clés i18n

**Fichier**: `frontend/src/utils/locales/en.json`

**Ajouter clés nécessaires**:
```json
{
  "{module-name}": "{Module Display Name}",
  "{entity}": "{Entity Display Name}",
  "{entities}": "{Entities Display Name}",
  "add-{entity}": "Add {Entity}",
  "edit-{entity}": "Edit {Entity}",
  "delete-{entity}": "Delete {Entity}",
  "{entity}-deleted-successfully": "{Entity} deleted successfully"
}
```

**Vérifier fichier existant**:
```bash
# Rechercher clés existantes
grep "{module}" frontend/src/utils/locales/en.json
```

#### 1.5.2 Breadcrumb

**Configuration**:
```
Home / {Section} / {Module}
```

**Exemple**:
- Roles: `Home / Administration / Roles & Permissions`
- Contacts: `Home / Sales / Contacts`

**Implémentation**: Breadcrumb component dans page `list.jsx`

### 1.6 Feature Flag (si nécessaire) (15min)

**Fichier**: `frontend/src/config/features.js`

**Ajouter**:
```javascript
export const FEATURES = {
  // ... existing features
  {MODULE_NAME}: true,  // ✅ Activer feature
};
```

**Usage dans menu**:
```javascript
// frontend/src/menu-items/admin.js
{
  id: '{module-id}',
  title: <FormattedMessage id="{module-name}" />,
  type: 'item',
  url: '/admin/{module}',
  icon: icons.{IconName},
  disabled: !FEATURES.{MODULE_NAME},  // ✅ Link basé sur flag
}
```

**Livrables Phase 1**:
- [ ] Document "UX Specifications" complet (18 questions répondues)
- [ ] Wireframes annotés
- [ ] Document "Comportements" détaillé (pagination, tri, modals, etc.)
- [ ] Clés i18n listées
- [ ] Feature flag configuré (si applicable)

---

## 🔧 PHASE 2: STANDARDISATION BACKEND (1 jour - 8h)

### Objectif
Standardiser le backend existant selon patterns du guide (§1-7).

**Principe**: On NE CRÉE PAS les modèles/serializers, on les STANDARDISE.

### 2.1 Standardiser ViewSet (3h)

**Fichier**: `backend/{module_name}/views/{entity}_view.py`

#### 2.1.1 Sous-étape: Imports & Héritage

**AVANT** (probablement):
```python
from rest_framework import viewsets
from ..models import {Entity}
from ..serializers import {Entity}Serializer

class {Entity}ViewSet(viewsets.ModelViewSet):
    queryset = {Entity}.objects.all()
    serializer_class = {Entity}Serializer
```

**APRÈS** (standard):
```python
# ✅ Imports complets selon Guide §1.2
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Prefetch
from django.db import transaction
from django.utils import timezone
from django.http import Http404

from core.cache_utils import (
    build_drf_cache_key,
    cache_get_set,
    invalidate_tag,
    _is_redis_backend,
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

from ..models import {Entity}
from ..serializers.{entity}_serializers import (
    {Entity}Serializer,
    {Entity}ListSerializer,
    {Entity}CreateSerializer,
    {Entity}UpdateSerializer,
)

logger = get_logger(__name__)

# ✅ Héritage standard (ORDRE IMPORTANT)
class {Entity}ViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing {entities}
    
    Features:
    - Client-scoped data isolation
    - Permission-based access control
    - Redis caching with tag versioning
    - SOC 2 audit logging
    """
    
    queryset = {Entity}.objects.all()
    serializer_class = {Entity}Serializer
    
    # ✅ OBLIGATOIRE: Attributs pour BaseAPIView + Permissions
    entity_name = '{entity}'
    module = '{module_name}'
    
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    
    # ✅ Filters configuration
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['field1', 'field2', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'field1']
    ordering = ['-created_at']
```

**Référence Guide**: §1.2, §1.3

**Temps**: 30min

#### 2.1.2 Sous-étape: get_serializer_class()

**Ajouter méthode**:
```python
def get_serializer_class(self):
    """Sélection serializer selon action"""
    if self.action == 'list':
        return {Entity}ListSerializer
    elif self.action == 'create':
        return {Entity}CreateSerializer
    elif self.action in ['update', 'partial_update']:
        return {Entity}UpdateSerializer
    return {Entity}Serializer
```

**Référence Guide**: §1.4

**Temps**: 10min

#### 2.1.3 Sous-étape: get_queryset() avec annotations

**Ajouter méthode**:
```python
def get_queryset(self):
    """
    Optimisations queryset selon action.
    Annotations pour éviter N+1 queries.
    """
    queryset = super().get_queryset().select_related('client_account')
    
    # ✅ Annotations (ajuster selon votre modèle)
    queryset = queryset.annotate(
        related_count=Count('related_model', distinct=True),
        # Autres annotations...
    )
    
    # ✅ Optimisations par action
    if self.action == 'list':
        queryset = queryset.select_related('fk_field1', 'fk_field2')
        
    elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
        queryset = queryset.select_related('fk_field1', 'fk_field2')
        queryset = queryset.prefetch_related(
            Prefetch(
                'related_model',
                queryset=RelatedModel.objects.select_related('nested'),
                to_attr='prefetched_related'
            )
        )
    
    return queryset
```

**Référence Guide**: §1.5

**Temps**: 30min

#### 2.1.4 Sous-étape: list() avec cache

**Remplacer méthode list() standard**:
```python
def list(self, request, *args, **kwargs):
    """Liste avec cache Redis (300s)"""
    client_id = self.get_client_id()
    
    # Skip cache si pas Redis
    if not _is_redis_backend():
        queryset = self.filter_queryset(self.get_queryset())
        response = self._serialize_list_queryset(queryset, client_id)
        return Response(response)
    
    # Build cache key
    cache_key = build_drf_cache_key(
        view_name=self.__class__.__name__,
        action='list',
        client_id=client_id,
        query_params=request.query_params
    )
    
    # Cache producer
    def fetch_data():
        queryset = self.filter_queryset(self.get_queryset())
        return self._serialize_list_queryset(queryset, client_id)
    
    # Cache get/set
    cached_response = cache_get_set(
        key=cache_key,
        producer=fetch_data,
        ttl=300,
        tag=(client_id, '{module_name}')
    )
    
    return Response(cached_response)

def _serialize_list_queryset(self, queryset, client_id):
    """Helper serialization avec pagination"""
    timestamp = timezone.now().isoformat()
    metadata = {
        'client_id': str(client_id) if client_id else None,
        'generated_at': timestamp,
    }
    
    page = self.paginate_queryset(queryset)
    
    if page is not None:
        serializer = self.get_serializer(page, many=True)
        total_count = self.paginator.page.paginator.count
        metadata['total_count'] = total_count
        
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': total_count,
                'next': self.paginator.get_next_link(),
                'previous': self.paginator.get_previous_link(),
            },
            'metadata': metadata,
        }
    
    serializer = self.get_serializer(queryset, many=True)
    metadata['total_count'] = len(serializer.data)
    
    return {
        'success': True,
        'data': {
            'results': serializer.data,
            'count': len(serializer.data),
        },
        'metadata': metadata,
    }
```

**Référence Guide**: §1.6, §1.7

**Temps**: 45min

#### 2.1.5 Sous-étape: create() avec audit + cache invalidation

**Remplacer méthode create()**:
```python
def create(self, request, *args, **kwargs):
    """Create avec audit log + cache invalidation"""
    try:
        serializer = self.get_serializer(
            data=request.data,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        
        # ✅ Transaction atomique
        with transaction.atomic():
            instance = serializer.save()
            
            # ✅ CRITICAL: Cache invalidation APRÈS commit
            client_id = instance.client_account_id
            transaction.on_commit(
                lambda: self._invalidate_all_related_caches(client_id)
            )
        
        # ✅ OBLIGATOIRE: Audit log SOC 2
        audit_log(
            event='{entity}_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(instance.client_account_id),
            target_type='{entity}',
            target_id=str(instance.id),
            outcome='success',
            extra={'name': instance.name}
        )
        
        # ✅ Logging applicatif
        ctx = ctx_from_request(request)
        ctx.update({
            'event': '{entity}_created',
            'entity_id': str(instance.id),
            'entity_name': instance.name
        })
        logger.info('{entity}_created', extra=ctx)
        
        # Retourner avec serializer complet
        full_serializer = {Entity}Serializer(
            instance,
            context=self.get_serializer_context()
        )
        
        return Response({
            'success': True,
            'message': f"{Entity} created successfully",
            'data': full_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return self.handle_exception(e)
```

**Référence Guide**: §1.8

**Temps**: 30min

#### 2.1.6 Sous-étape: Cache invalidation helper

**Ajouter méthode** (CRITICAL):
```python
def _invalidate_all_related_caches(self, client_id):
    """
    Invalider module principal + modules dépendants.
    
    IMPORTANT: Compléter avec TOUS modules dépendants.
    Référer à cartographie Phase 0.
    """
    if not client_id:
        return
    
    # Module principal
    invalidate_tag(client_id, '{module_name}')
    
    # ✅ Modules dépendants (compléter selon Phase 0)
    invalidate_tag(client_id, 'users')      # Si users display count
    invalidate_tag(client_id, 'roles')      # Si roles display count
    # ... autres modules
    
    logger.info('cache_invalidation_{module}_related', extra={
        'event': 'cache_invalidation',
        'client_id': str(client_id),
        'tags': ['{module_name}', 'users', 'roles']
    })
```

**Référence Guide**: §1.9, §5 Cache

**Temps**: 30min

**Total Sous-étape 2.1**: 3h

### 2.2 Standardiser Serializers (2h)

**Fichier**: `backend/{module_name}/serializers/{entity}_serializers.py`

#### 2.2.1 Sous-étape: Ajouter mixin + méthodes calculées

**AVANT**:
```python
class {Entity}Serializer(serializers.ModelSerializer):
    class Meta:
        model = {Entity}
        fields = ['id', 'name', 'field1']
```

**APRÈS**:
```python
# ✅ Ajouter imports
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.logging import get_logger, ctx_from_request

logger = get_logger(__name__)

class {Entity}Serializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer principal avec validation complète"""
    
    # ✅ Champs calculés
    client_account_name = serializers.CharField(
        source='client_account.name',
        read_only=True
    )
    
    related_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = {Entity}
        fields = [
            'id', 'name', 'field1',
            'client_id', 'client_account', 'client_account_name',
            'related_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'client_account', 'client_id', 'client_account_name',
            'related_count', 'created_at', 'updated_at'
        ]
    
    def get_related_count(self, obj):
        """Récupère count depuis annotation si disponible"""
        if hasattr(obj, 'related_count'):
            return obj.related_count
        return obj.related_model.count()
```

**Référence Guide**: §2.3

**Temps**: 30min

#### 2.2.2 Sous-étape: Validation name avec unicité

**Ajouter méthode**:
```python
def validate_name(self, value):
    """Validation name avec unicité par client"""
    if not value or not value.strip():
        raise StandardizedValidationError(
            CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
        )
    
    value = value.strip()
    
    # Client ID
    client_id = self._get_client_id_from_context()
    
    # Unicité case-insensitive
    queryset = {Entity}.objects.filter(
        client_account_id=client_id,
        name__iexact=value
    )
    
    # Exclure instance actuelle si update
    if self.instance:
        queryset = queryset.exclude(id=self.instance.id)
    
    if queryset.exists():
        raise StandardizedValidationError(
            CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                fields=f"name '{value}'"
            )
        )
    
    return value
```

**Référence Guide**: §2.3

**Temps**: 20min

#### 2.2.3 Sous-étape: Créer ListSerializer optimisé

**Ajouter classe**:
```python
class {Entity}ListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer optimisé pour listes"""
    
    # Relations sous forme objets
    related_field = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = {Entity}
        fields = [
            'id', 'name', 'field1',
            'related_field', 'related_field_name',
            'is_active',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_related_field(self, obj):
        """Retourner relation sous forme d'objet minimal"""
        if obj.related_field:
            return {
                'id': str(obj.related_field_id),
                'name': obj.related_field.name
            }
        return None
```

**Référence Guide**: §2.4

**Temps**: 20min

#### 2.2.4 Sous-étape: CreateSerializer (si validations spécifiques)

Si validations création différentes de update, créer:
```python
class {Entity}CreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer spécialisé création"""
    
    class Meta:
        model = {Entity}
        fields = ['name', 'field1', 'field2']
        extra_kwargs = {
            'name': {'required': True},
            'field1': {'required': False, 'default': 'default_value'},
        }
    
    def validate(self, attrs):
        """Validations spécifiques création"""
        client_id = self._get_client_id_from_context()
        attrs['client_account_id'] = client_id
        
        # Validations métier...
        
        return attrs
```

**Référence Guide**: §2.5

**Temps**: 30min

#### 2.2.5 Sous-étape: UpdateSerializer (si protections)

```python
class {Entity}UpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer pour modifications"""
    
    class Meta:
        model = {Entity}
        fields = ['name', 'field1', 'field2']
        extra_kwargs = {
            'name': {'required': False},
        }
    
    def update(self, instance, validated_data):
        """Update avec protections"""
        # Protection entités système
        if getattr(instance, 'is_locked', False):
            raise StandardizedValidationError(
                CoreErrorMessages.PERMISSION_DENIED + " - Locked entity"
            )
        
        # Appliquer modifications
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance
```

**Référence Guide**: §2.5

**Temps**: 20min

**Total Sous-étape 2.2**: 2h

### 2.3 Permissions Registry (1h)

**Fichier**: `backend/permissions/registry/{module_name}_registry.py`

**Créer fichier**:
```python
# backend/permissions/registry/{module_name}_registry.py

from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']

{MODULE_NAME}_REGISTRY: Dict[str, Dict[Action, Dict[Tier, Scope]]] = {
    '{entities}': {
        'create': {
            'admin': 'client',
            'manager': 'team',
            'individual': 'none'
        },
        'read': {
            'admin': 'client',
            'manager': 'team',
            'individual': 'mine'
        },
        'update': {
            'admin': 'client',
            'manager': 'team',
            'individual': 'mine'
        },
        'delete': {
            'admin': 'client',
            'manager': 'none',
            'individual': 'none'
        }
    }
}
```

**Puis ajouter à** `backend/permissions/registry/__init__.py`:
```python
from .{module_name}_registry import {MODULE_NAME}_REGISTRY

REGISTRY.update({MODULE_NAME}_REGISTRY)
```

**Référence Guide**: §6.1

**Temps**: 1h

### 2.4 URLs Configuration (30min)

**Fichier**: `backend/{module_name}/urls.py`

**Créer/Compléter**:
```python
from django.urls import path
from .views import {Entity}ViewSet

app_name = '{module_name}'

urlpatterns = [
    # CRUD
    path('{entities}/', {Entity}ViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='{entity}-list'),
    
    path('{entities}/<uuid:pk>/', {Entity}ViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='{entity}-detail'),
]
```

**Enregistrer dans** `backend/salescommands/urls.py`:
```python
urlpatterns = [
    # ...
    path('client/', include('{module_name}.urls')),
]
```

**Référence Guide**: §1.10

**Temps**: 30min

### 2.5 Bulk Operations (Optionnel, 2h)

**Si nécessaire** (Phase 1 Q9), créer:

**Fichier**: `backend/{module_name}/views/{entity}_view_bulk.py`

**Référence Guide**: §3 Bulk Operations

**Temps**: 2h (si nécessaire)

**Livrables Phase 2**:
- [ ] ViewSet standardisé (cache, audit, logging)
- [ ] Serializers standardisés (mixin, validation, list/create/update)
- [ ] Permissions registry créé
- [ ] URLs configurés
- [ ] Bulk operations (si applicable)

---

## 💻 PHASE 3: IMPLÉMENTATION FRONTEND (1-2 jours)

### Objectif
Implémenter le frontend selon design Phase 1.

### 3.1 API Hooks SWR (2h)

**Fichier**: `frontend/src/api/admin/{module}.js`

#### 3.1.1 Sous-étape: Structure base + helper

```javascript
// frontend/src/api/admin/{module}.js

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// Endpoints
const endpoints = {
  {entities}: '/client/{entities}/',
  {entity}Detail: (id) => `/client/{entities}/${id}/`,
};

// Helper URL builder
const buildUrlWithParams = (baseUrl, params = {}) => {
  const { page, pageSize, search, ordering } = params;
  const queryParams = new URLSearchParams();
  
  if (page) queryParams.append('page', page);
  if (pageSize) queryParams.append('page_size', pageSize);
  if (search) queryParams.append('search', search);
  if (ordering) queryParams.append('ordering', ordering);
  
  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};
```

**Référence Guide**: §9.1

**Temps**: 15min

#### 3.1.2 Sous-étape: Hook GET list

```javascript
/**
 * GET ALL ENTITIES
 */
export function useGet{Entities}(params = {}) {
  const { tenantId } = useAuth();
  
  const swrKey = useMemo(() => {
    const url = buildUrlWithParams(endpoints.{entities}, params);
    return tenantKey(url, tenantId);
  }, [params.page, params.pageSize, params.search, params.ordering, tenantId]);
  
  const { data, error, isLoading, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 2000,
  });
  
  const memoizedValue = useMemo(
    () => ({
      {entities}: data?.data?.results || [],
      {entities}Count: data?.data?.count || 0,
      {entities}Loading: isLoading,
      {entities}Error: error,
      {entities}Validating: isValidating,
      {entities}Empty: !isLoading && (!data?.data?.results?.length)
    }),
    [data, isLoading, error, isValidating]
  );
  
  return memoizedValue;
}
```

**Référence Guide**: §9.1

**Temps**: 20min

#### 3.1.3 Sous-étape: Mutations (create/update/delete)

```javascript
/**
 * CREATE ENTITY
 */
export async function create{Entity}(data) {
  // Validation UUID fields
  const uuidFields = ['related_field_id']; // Ajuster selon modèle
  for (const field of uuidFields) {
    const value = data[field];
    if (value && !isValidUUID(value)) {
      return { success: false, error: `Invalid ${field} format` };
    }
  }
  
  // Sanitize strings
  const sanitized = sanitizeObject(data, ['name', 'description']);
  
  const result = await api.post(endpoints.{entities}, sanitized);
  
  if (result.success) {
    // ✅ CRITICAL: Revalidation croisée
    revalidateMultiple([
      endpoints.{entities},
      // Ajouter modules dépendants (Phase 0 cartographie)
      '/client/users/',
      '/client/roles/'
    ]);
    
    return { success: true, data: result.data };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0
  };
}

/**
 * UPDATE ENTITY
 */
export async function update{Entity}(entityId, data) {
  if (!entityId || !isValidUUID(entityId)) {
    return { success: false, error: 'Invalid entity ID format' };
  }
  
  const uuidFields = ['related_field_id'];
  for (const field of uuidFields) {
    const value = data[field];
    if (value && !isValidUUID(value)) {
      return { success: false, error: `Invalid ${field} format` };
    }
  }
  
  const sanitized = sanitizeObject(data, ['name', 'description']);
  
  const result = await api.patch(endpoints.{entity}Detail(entityId), sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.{entities},
      endpoints.{entity}Detail(entityId),
      '/client/users/',
      '/client/roles/'
    ]);
    
    return { success: true, data: result.data };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0
  };
}

/**
 * DELETE ENTITY
 */
export async function delete{Entity}(entityId) {
  if (!entityId || !isValidUUID(entityId)) {
    return { success: false, error: 'Invalid entity ID format', status: 400 };
  }
  
  const result = await api.delete(endpoints.{entity}Detail(entityId));
  
  if (result.success || result.status === 204) {
    revalidateMultiple([
      endpoints.{entities},
      '/client/users/',
      '/client/roles/'
    ]);
    
    return { success: true, status: result.status ?? 204 };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0
  };
}
```

**Référence Guide**: §9.1

**Temps**: 1h

**Total 3.1**: 2h

### 3.2 Page Container (3h)

**Fichier**: `frontend/src/views/admin/{module}/list.jsx`

**Template complet** (référence Guide §8.2):

```javascript
// frontend/src/views/admin/{module}/list.jsx

'use client';
import { useMemo, useState, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// icons
import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';

// project imports
import ReusableTable from 'components/table/Table';
import Form{Entity}Add from 'sections/admin/{module}/Form{Entity}Add';
import Form{Entity}Edit from 'sections/admin/{module}/Form{Entity}Edit';
import Alert{Entity}Delete from 'sections/admin/{module}/Alert{Entity}Delete';
import IconButton from 'components/@extended/IconButton';

// hooks
import useLocalStorage from 'hooks/useLocalStorage';
import { useAuth } from 'hooks/useAuth';

// api
import { useGet{Entities} } from 'api/admin/{module}';
import { tenantKey } from 'api/_swr';

// utils
import { formatDateTime } from 'config/formatters';

// ==============================|| SORT MAPPING ||============================== //

/**
 * ✅ CRITICAL: Map frontend IDs to backend fields
 * Compléter selon colonnes Phase 1 Q5
 */
const COLUMN_TO_BACKEND_FIELD = {
  name: 'name',
  created_at: 'created_at',
  field1: 'field1',
  // Ajouter autres colonnes triables
};

// ==============================|| {MODULE} LIST PAGE ||============================== //

export default function {Entities}ListPage() {
  const { tenantId } = useAuth();
  
  const MAX_PAGE_SIZE = 100;
  
  // ==============================|| STATE ||============================== //
  
  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('{entity}TablePageSize', 10); // Phase 1 Q6
  
  const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 10;
    return Math.min(parsed, MAX_PAGE_SIZE);
  }, [pageSize]);
  
  // Search
  const [search, setSearch] = useState('');
  
  // Sorting
  const [sorting, setSorting] = useState([]);
  
  // Modals (Phase 1 Q9)
  const [addModal, setAddModal] = useState(false);
  const [editModal, setEditModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);
  
  // ==============================|| COMPUTED ||============================== //
  
  const ordering = useMemo(() => {
    if (!sorting || !Array.isArray(sorting) || sorting.length === 0) {
      return '';
    }
    
    return sorting
      .map(({ id, desc }) => {
        const backendField = COLUMN_TO_BACKEND_FIELD[id] || id;
        return desc ? `-${backendField}` : backendField;
      })
      .join(',');
  }, [sorting]);
  
  // ==============================|| DATA FETCHING ||============================== //
  
  const { 
    {entities}Loading, 
    {entities}, 
    {entities}Count, 
    {entities}Error 
  } = useGet{Entities}({ 
    page, 
    pageSize: validPageSize, 
    search,
    ordering  
  }) || {};
  
  const swrKey = useMemo(() => {
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('page_size', validPageSize);
    if (search) params.append('search', search);
    if (ordering) params.append('ordering', ordering);
    const url = `/client/{entities}/${params.toString() ? `?${params}` : ''}`;
    return tenantKey(url, tenantId);
  }, [page, validPageSize, search, ordering, tenantId]);
  
  // ==============================|| HANDLERS ||============================== //
  
  const handlePaginationChange = useCallback(({ page: newPage, pageSize: newPageSize }) => {
    setPage(newPage);
    
    const size = Number(newPageSize);
    if (!isNaN(size) && size > 0 && size !== validPageSize) {
      setPageSize(size);
    }
  }, [validPageSize, setPageSize]);
  
  const handleSearchChange = useCallback((searchTerm) => {
    setSearch(searchTerm);
    setPage(1);
  }, []);
  
  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prev) => {
      const newSorting = typeof updaterOrValue === 'function' 
        ? updaterOrValue(prev) 
        : updaterOrValue;
      
      if (JSON.stringify(newSorting) !== JSON.stringify(prev)) {
        setPage(1);
      }
      
      return newSorting;
    });
  }, []);
  
  const handleAdd = useCallback(() => {
    setSelectedEntity(null);
    setAddModal(true);
  }, []);
  
  const handleEdit = useCallback((entity) => {
    setSelectedEntity(entity);
    setEditModal(true);
  }, []);
  
  const handleDelete = useCallback((entity) => {
    setSelectedEntity(entity);
    setDeleteModal(true);
  }, []);
  
  // ==============================|| COLUMNS ||============================== //
  
  /**
   * ✅ CRITICAL: Colonnes définies ICI selon Phase 1 Q4
   */
  const columns = useMemo(() => [
    {
      id: 'name',
      accessorKey: 'name',
      header: 'Name',
      enableSorting: true,
      cell: ({ getValue }) => getValue()
    },
    {
      id: 'field1',
      accessorKey: 'field1',
      header: 'Field 1',
      enableSorting: true
    },
    {
      id: 'created_at',
      accessorKey: 'created_at',
      header: 'Created',
      enableSorting: true,
      cell: ({ getValue }) => formatDateTime(getValue())
    },
    {
      id: 'actions',
      header: 'Actions',
      enableSorting: false,
      cell: ({ row }) => (
        <Stack direction="row" spacing={0} alignItems="center">
          <IconButton color="primary" onClick={() => handleEdit(row.original)}>
            <EditOutlined />
          </IconButton>
          <IconButton color="error" onClick={() => handleDelete(row.original)}>
            <DeleteOutlined />
          </IconButton>
        </Stack>
      )
    }
    // Ajouter autres colonnes selon Phase 1 Q4
  ], [handleEdit, handleDelete]);
  
  // ==============================|| RENDER ||============================== //
  
  return (
    <>
      <Box>
        <Stack direction="row" justifyContent="space-between" mb={2}>
          <Typography variant="h3">{Entities}</Typography>
          <Button variant="contained" onClick={handleAdd}>
            Add {Entity}
          </Button>
        </Stack>
        
        {/* ✅ ReusableTable directly */}
        <ReusableTable
          data={{entities} || []}
          columns={columns}
          loading={{entities}Loading}
          error={{entities}Error}
          swrKey={swrKey}
          
          totalCount={{entities}Count || 0}
          currentPage={page}
          initialPageSize={validPageSize}
          onPaginationChange={handlePaginationChange}
          onSearchChange={handleSearchChange}
          
          sorting={sorting}
          onSortingChange={handleSortingChange}
          
          modalToggler={handleAdd}
        />
      </Box>
      
      {/* Modals */}
      {addModal && (
        <Form{Entity}Add
          open={addModal}
          closeModal={() => setAddModal(false)}
        />
      )}
      
      {editModal && selectedEntity && (
        <Form{Entity}Edit
          entity={selectedEntity}
          open={editModal}
          closeModal={() => setEditModal(false)}
        />
      )}
      
      {deleteModal && selectedEntity && (
        <Alert{Entity}Delete
          entity={selectedEntity}
          open={deleteModal}
          closeModal={() => setDeleteModal(false)}
        />
      )}
    </>
  );
}
```

**Référence Guide**: §8.2

**Temps**: 3h

### 3.3 Modal Add (2h)

**Fichier**: `frontend/src/sections/admin/{module}/Form{Entity}Add.jsx`

**Template Formik + Yup** (selon Phase 1 Q11):

```javascript
// frontend/src/sections/admin/{module}/Form{Entity}Add.jsx

import { useEffect } from 'react';
import { Formik } from 'formik';
import * as Yup from 'yup';

// material-ui
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Grid from '@mui/material/Grid';
import CircularProgress from '@mui/material/CircularProgress';

// project
import { create{Entity} } from 'api/admin/{module}';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formikHelpers';
import { isValidUUID } from 'utils/validators';

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  name: Yup.string()
    .required('Name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be less than 100 characters'),
  
  field1: Yup.string()
    .nullable()
    .max(200, 'Field 1 must be less than 200 characters'),
  
  related_field_id: Yup.string()
    .nullable()
    .test('is-valid-uuid', 'Invalid selection', function(value) {
      if (!value) return true;
      return isValidUUID(value);
    })
  
  // Ajouter autres champs selon Phase 1 Q11
});

// ==============================|| FORM ADD ENTITY ||============================== //

export default function Form{Entity}Add({ open, closeModal }) {
  
  const handleSubmit = async (values, { setSubmitting, setErrors }) => {
    try {
      const result = await create{Entity}(values);
      
      if (result.success) {
        displaySuccessSnackbar('{Entity} created successfully');
        closeModal();
      } else {
        handleFormikError(result, setErrors, displayErrorSnackbar);
      }
    } catch (error) {
      displayErrorSnackbar('An unexpected error occurred');
      console.error('Create {entity} error:', error);
    } finally {
      setSubmitting(false);
    }
  };
  
  return (
    <Dialog
      open={open}
      onClose={closeModal}
      maxWidth="md"
      fullWidth
    >
      <Formik
        initialValues={{
          name: '',
          field1: '',
          related_field_id: null
          // Ajouter autres champs
        }}
        validationSchema={validationSchema}
        onSubmit={handleSubmit}
      >
        {({ values, errors, touched, handleChange, handleBlur, handleSubmit, isSubmitting }) => (
          <form onSubmit={handleSubmit}>
            <DialogTitle>Add {Entity}</DialogTitle>
            
            <DialogContent dividers>
              <Grid container spacing={3}>
                {/* Champ Name */}
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    id="name"
                    name="name"
                    label="Name *"
                    value={values.name}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    error={touched.name && Boolean(errors.name)}
                    helperText={touched.name && errors.name}
                  />
                </Grid>
                
                {/* Ajouter autres champs selon Phase 1 Q11 */}
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    id="field1"
                    name="field1"
                    label="Field 1"
                    value={values.field1}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    error={touched.field1 && Boolean(errors.field1)}
                    helperText={touched.field1 && errors.field1}
                  />
                </Grid>
                
                {/* Pour selects, autocomplete, etc. voir Phase 1.2 */}
              </Grid>
            </DialogContent>
            
            <DialogActions>
              <Button onClick={closeModal} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="contained"
                disabled={isSubmitting}
                startIcon={isSubmitting && <CircularProgress size={20} />}
              >
                Create
              </Button>
            </DialogActions>
          </form>
        )}
      </Formik>
    </Dialog>
  );
}
```

**Référence Guide**: §10.2

**Temps**: 2h

### 3.4 Modal Edit (1h)

**Fichier**: `frontend/src/sections/admin/{module}/Form{Entity}Edit.jsx`

**Structure similaire à Add**, avec:
- `initialValues` pré-remplis depuis `entity` prop
- Appel `update{Entity}(entity.id, values)`
- Champs read-only si applicable (Phase 1 Q12)

**Temps**: 1h

### 3.5 Alert Delete (1h)

**Fichier**: `frontend/src/sections/admin/{module}/Alert{Entity}Delete.jsx`

```javascript
// frontend/src/sections/admin/{module}/Alert{Entity}Delete.jsx

import { useState } from 'react';

// material-ui
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';

// project
import { delete{Entity} } from 'api/admin/{module}';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

export default function Alert{Entity}Delete({ entity, open, closeModal }) {
  const [deleting, setDeleting] = useState(false);
  
  // ✅ Validation métier (Phase 1 Q10, Q15)
  const hasBlockingRelations = false; // Implémenter selon logique métier
  const blockingMessage = ''; // Message spécifique si bloqué
  
  const handleDelete = async () => {
    setDeleting(true);
    
    try {
      const result = await delete{Entity}(entity.id);
      
      if (result.success) {
        displaySuccessSnackbar('{Entity} deleted successfully');
        closeModal();
      } else {
        displayErrorSnackbar(result.error || 'Failed to delete {entity}');
      }
    } catch (error) {
      displayErrorSnackbar('An unexpected error occurred');
      console.error('Delete {entity} error:', error);
    } finally {
      setDeleting(false);
    }
  };
  
  return (
    <Dialog open={open} onClose={closeModal} maxWidth="sm" fullWidth>
      <DialogTitle>Delete {Entity}</DialogTitle>
      
      <DialogContent dividers>
        {hasBlockingRelations ? (
          <Alert severity="error">
            {blockingMessage || 'Cannot delete this {entity} due to existing relations.'}
          </Alert>
        ) : (
          <Typography>
            Are you sure you want to delete <strong>{entity.name}</strong>?
            This action cannot be undone.
          </Typography>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={closeModal} disabled={deleting}>
          Cancel
        </Button>
        <Button
          onClick={handleDelete}
          color="error"
          variant="contained"
          disabled={deleting || hasBlockingRelations}
          startIcon={deleting && <CircularProgress size={20} />}
        >
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

**Référence Guide**: §8.2

**Temps**: 1h

### 3.6 Navigation & i18n (1h)

#### 3.6.1 Activer menu drawer

**Fichier**: `frontend/src/menu-items/admin.js` (ou section appropriée)

```javascript
// Imports
import { FormattedMessage } from 'react-intl';
import { {IconName} } from '@ant-design/icons';

// Features
import { FEATURES } from 'config/features';

// Menu item
{
  id: '{module-id}',
  title: <FormattedMessage id="{module-name}" />,
  type: 'item',
  url: '/admin/{module}',
  icon: {IconName},
  disabled: !FEATURES.{MODULE_NAME},  // Si feature flag Phase 1.6
  breadcrumbs: true
}
```

#### 3.6.2 Compléter i18n

**Fichier**: `frontend/src/utils/locales/en.json`

Ajouter toutes clés Phase 1.5.1

**Temps total 3.6**: 1h

**Livrables Phase 3**:
- [ ] API hooks (get + mutations avec revalidation croisée)
- [ ] Page container avec state management
- [ ] Modal Add (Formik + Yup validation)
- [ ] Modal Edit
- [ ] Alert Delete avec validations
- [ ] Menu drawer activé
- [ ] i18n clés complètes

---

## ✅ PHASE 4: TESTS & VALIDATION (0.5-1 jour)

### 4.1 Tests Manuels Frontend (2h)

**Checklist complète**:

**Navigation**:
- [ ] Menu drawer link actif et cliquable
- [ ] Breadcrumb correct
- [ ] URL route fonctionnelle

**Table**:
- [ ] Chargement initial → Skeleton puis données
- [ ] Pagination → Changement de page fonctionnel
- [ ] Pagination → Changement pageSize persisté
- [ ] Recherche → Filtrage server-side
- [ ] Tri → Click header toggle direction
- [ ] Tri → Conversion backend field correcte
- [ ] Empty state → Si aucune donnée
- [ ] Error state → Si erreur API, bouton Retry

**Modal Add**:
- [ ] Open → Formulaire vide
- [ ] Validation → Errors inline si invalide
- [ ] Submit → Success → Modal close + table refresh + snackbar
- [ ] Submit → Error → Affichage error + modal reste ouverte
- [ ] Cancel → Modal close sans action

**Modal Edit**:
- [ ] Open → Pré-remplissage correct
- [ ] Champs read-only respectés (si applicable)
- [ ] Submit → Success → Mise à jour visible
- [ ] Submit → Error → Gestion appropriée

**Modal Delete**:
- [ ] Validation métier → Si bloqué, message + bouton disabled
- [ ] Confirm → Success → Entité disparaît table
- [ ] Confirm → Error → Message explicite

**Performance**:
- [ ] Pas de re-render inutiles (React DevTools)
- [ ] Pas de memory leaks (useEffect cleanup)
- [ ] SWR cache fonctionne (vérifier Network tab)

### 4.2 Tests Backend (2h)

**Créer**: `backend/tests/integration/{module_name}/test_{entity}_crud.py`

**Template minimal**:
```python
import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db(transaction=True)

class Test{Entity}CRUD:
    def test_list_success(self, api, users, tenants):
        """Test listing entities"""
        # Implémenter selon Guide §11
        pass
    
    def test_create_success(self, api, users, tenants):
        """Test creating entity"""
        pass
    
    def test_update_success(self, api, users, tenants):
        """Test updating entity"""
        pass
    
    def test_delete_success(self, api, users, tenants):
        """Test deleting entity"""
        pass
    
    def test_cross_tenant_isolation(self, api, users, tenants):
        """Test multi-tenant isolation"""
        pass
```

**Référence Guide**: §11 Tests

**Lancer tests**:
```bash
pytest backend/tests/integration/{module_name}/ -v
```

**Temps**: 2h

### 4.3 Audit Final Checklist (1h)

**Reprendre checklist Guide §12** et valider TOUS les points:

**Backend**:
- [ ] PII protection (NO PII in logs)
- [ ] Audit log SOC 2 sur mutations
- [ ] Cache invalidation complète
- [ ] Permissions registry
- [ ] TOCTOU prevention (si applicable)

**Frontend**:
- [ ] Architecture respectée (columns dans page)
- [ ] Validation UUID
- [ ] revalidateMultiple avec TOUS modules dépendants
- [ ] Error handling robuste

**Livrables Phase 4**:
- [ ] Tests frontend passés (checklist complète)
- [ ] Tests backend passés (coverage > 80%)
- [ ] Audit final validé

---

## 📚 RÉSUMÉ WORKFLOW

| Phase | Durée | Livrables |
|-------|-------|-----------|
| 0. Analyse Existant | 2h | Gaps analysis, Cartographie dépendances |
| 1. Conception Frontend | 1 jour | UX Specs (18 questions), Wireframes, Comportements |
| 2. Standardisation Backend | 1 jour | ViewSet, Serializers, Permissions, URLs |
| 3. Implémentation Frontend | 1-2 jours | API hooks, Page, Modals, Navigation |
| 4. Tests & Validation | 0.5-1 jour | Tests passés, Audit final |
| **TOTAL** | **3-5 jours** | **Module complet opérationnel** |

---

## 🎯 POINTS CRITIQUES À NE PAS OUBLIER

1. **Cache invalidation croisée**: Cartographier TOUTES dépendances (Phase 0)
2. **Columns dans page container**: PAS dans table component (Phase 3.2)
3. **COLUMN_TO_BACKEND_FIELD**: Mapping obligatoire pour sorting (Phase 3.2)
4. **Audit log SOC 2**: Obligatoire sur create/update/delete (Phase 2.1.5)
5. **NO PII in logs**: Utiliser `safe_user_context()` systématiquement (Phase 2)
6. **revalidateMultiple**: Inclure TOUS modules impactés (Phase 3.1.3)
7. **Validation UUID**: Client-side ET server-side (Phase 3.1.3)

---

**Fin du workflow. Bon courage pour votre implémentation ! 🚀**