# 🚀 WORKFLOW IMPLÉMENTATION NOUVEAU MODULE

## 📋 Vue d'Ensemble

**Durée estimée**: 5-8 jours pour un module complet  
**Pré-requis**: Lire [MODULE_STANDARDIZATION_GUIDE.md](./MODULE_STANDARDIZATION_GUIDE.md)

---
## PHASE 0: CONCEPTION DU FRONT END  
- [ ] Choix des composants - Composant MUI qui vient du modele
- [ ] Design UX - A quoi le page va ressembler
- [ ] User experience - comportement de TOUT les composants (pagination, tri, search, modale, ...)
- [ ] i18n & Breadcrumb
          
## PHASE 1: CONCEPTION & SETUP (Jour 1 - 4h)

### 1.1 Architecture & Modèles
**Référence**: Guide §1.5 Models, §6.1 Registry

```bash
# Créer structure
mkdir -p backend/{module_name}/{models,views,serializers,signals,tests}
mkdir -p frontend/src/{sections/admin/{module},views/admin/{module},api/admin}
```

**✅ Checklist:**
- [ ] Schéma base de données défini
- [ ] Relations identifiées (FKs, M2M)
- [ ] Champs obligatoires: `id` (UUID), `client_account`, `owner`, `created_by`, timestamps
- [ ] Indexes définis pour performance
- [ ] Matrice permissions créée (qui peut faire quoi)

**🎯 Livrable**: Document architecture + ERD

---

## PHASE 2: BACKEND CORE (Jour 1-2 - 8h)

### 2.1 Models & Migrations
**Référence**: Guide §1.5 Models

**✅ Actions:**
```python
# backend/{module_name}/models/{entity}.py
- Créer model avec UUID primary key
- FK client_account (obligatoire)
- FK owner, created_by (permissions)
- Timestamps created_at, updated_at
- Meta: db_table, ordering, indexes
```

**✅ Checklist:**
- [ ] Migrations créées et testées
- [ ] Relations FK correctes
- [ ] `__str__()` implémenté
- [ ] No N+1 queries potentiels

### 2.2 Serializers
**Référence**: Guide §12.1 Backend Validation

**✅ Actions:**
```python
# backend/{module_name}/serializers/{entity}_serializer.py
- Créer {Entity}Serializer (detail)
- Créer {Entity}ListSerializer (optimisé)
- Validation custom (validate_field, validate)
- read_only_fields définis
```

**✅ Checklist:**
- [ ] Validation métier implémentée
- [ ] Messages d'erreur dans error_messages.py
- [ ] Serializers list/detail différenciés

### 2.3 ViewSets CRUD
**Référence**: Guide §1.2 ViewSets Standards

**✅ Actions:**
```python
# backend/{module_name}/views/{entity}_view.py
- Hériter de ScopedQuerysetMixin + ModelViewSet
- permission_classes = [IsAuthenticated, ScopedPermission]
- throttle_classes = [StandardRateThrottle]
- module = '{module_name}'  # ⚠️ CRITICAL
- Filters: DjangoFilterBackend, SearchFilter, OrderingFilter
- Cache sur list() avec cache_get_set()
```

**✅ Checklist:**
- [ ] CRUD complet (list, create, retrieve, update, destroy)
- [ ] Logging avec ctx_from_request()
- [ ] Caching sur list
- [ ] Filters configurés
- [ ] Logiques metiers validées - Edge case et crash test

### 2.4 Bulk Operations
**Référence**: Guide §1.3 Bulk Operations

**✅ Actions:**
```python
# backend/{module_name}/views/{entity}_view_bulk.py
- Créer {Entity}BulkViewSet hérité de {Entity}ViewSet
- throttle_classes = [BulkOperationThrottle]
- Implémenter bulk_create, bulk_update, bulk_delete
- Set-based SQL (filter(id__in=ids).update())
- disable_signals_with_invalidation()
```

**✅ Checklist:**
- [ ] Idempotency géré
- [ ] Modes strict/partial
- [ ] Validation input (taille max 500)
- [ ] Set-based operations (NO loops)
- [ ] Toute les logiques metiers sont presentes
- [ ] Permision

### 2.5 URLs Configuration
**Référence**: Guide §1.4 URLs

**✅ Actions:**
```python
# backend/{module_name}/urls.py
- app_name défini
- Routes CRUD standard
- Routes bulk: /bulk-create/, /bulk-update/, /bulk-delete/
- Custom actions si nécessaire
```

**✅ Checklist:**
- [ ] Toutes routes nommées
- [ ] UUID dans paths: <uuid:pk>
- [ ] Registered dans urls.py principal

---

## PHASE 3: SÉCURITÉ & OPTIMISATION (Jour 2-3 - 6h)

### 3.1 Race Conditions & TOCTOU
**Référence**: Guide §2.3 TOCTOU Prevention

**✅ Actions:**
- Identifier validations critiques
- Ajouter `select_for_update()` dans `transaction.atomic()`
- Tests concurrence (100 threads)

**✅ Checklist:**
- [ ] Validations protégées par lock
- [ ] Tests race conditions passent
- [ ] Distributed lock Redis si nécessaire

### 3.2 Query Optimization
**Référence**: Guide §4.2 Query Optimization

**✅ Actions:**
```python
# Optimiser queries
- select_related() pour FKs
- prefetch_related() pour M2M
- only() pour réduire colonnes
- Indexes DB vérifiés
```

**✅ Checklist:**
- [ ] NO N+1 queries (django-debug-toolbar)
- [ ] Indexes sur (client_account, created_at, owner)
- [ ] Pagination testée avec 10k+ records

### 3.3 Input Validation & Sanitization
**Référence**: Guide §12 Validation & Sanitization

**✅ Actions:**
- Validation Serializer (backend)
- Validation Yup (frontend)
- Sanitization inputs (HTML tags, SQL, XSS)

**✅ Checklist:**
- [ ] Tous inputs validés
- [ ] Messages d'erreur clairs
- [ ] Edge cases testés (null, empty, huge)

---

## PHASE 4: PERMISSIONS & AUTHORIZATION (Jour 3 - 4h)

### 4.1 Registry Configuration
**Référence**: Guide §6.1 Registry

**✅ Actions:**
```python
# backend/permissions/registry/{module_name}_registry.py
- Définir matrice CRUD × Tier → Scope
- Admin: client / Manager: team / Individual: mine
- Ajouter à REGISTRY dans __init__.py
```

**✅ Checklist:**
- [ ] Matrice complète (create, read, update, delete)
- [ ] Testé avec tous tiers (admin, manager, individual)
- [ ] Edge cases (superuser, cross-tenant)

### 4.2 Ownership Mapping
**Référence**: Guide §6.4 Ownership

**✅ Actions:**
```python
# backend/permissions/ownership.py
- Ajouter mapping avec FK fields
- client_account_fk, owner_user, owner_team, created_by
```

**✅ Checklist:**
- [ ] Ownership fields définis
- [ ] Scoping testé (mine, team, client)

### 4.3 Tests Permissions
**Référence**: Guide §10.3 Test Template

**✅ Checklist:**
- [ ] Admin peut tout (client-wide)
- [ ] Manager limité à team
- [ ] Individual limité à mine
- [ ] Cross-tenant bloqué (404)
- [ ] Tester les methodes seules et bulk

---

## PHASE 5: CACHE & REDIS (Jour 3 - 3h)

### 5.1 Cache Strategy
**Référence**: Guide §5.1 Cache Strategy

**✅ Actions:**
```python
# Dans ViewSet.list()
cache_key = build_drf_cache_key(...)
return cache_get_set(key, producer, ttl=300, tag=(client_id, 'entities'))
```

**✅ Checklist:**
- [ ] Cache sur list() - 5min TTL
- [ ] Tag versioning configuré
- [ ] Client-scoped keys

### 5.2 Cache Invalidation
**Référence**: Guide §5.2-5.4 Invalidation

**✅ Actions:**
```python
# backend/{module_name}/signals/cache_invalidation.py
- Signal post_save
- Signal post_delete
- transaction.on_commit() pour invalidation
- are_signals_disabled() check
```

**✅ Checklist:**
- [ ] Signals créés pour create/update/delete
- [ ] Bulk operations avec disable_signals_with_invalidation()
- [ ] Invalidation APRÈS commit (transaction.on_commit)

### 5.3 Tests Cache
**✅ Checklist:**
- [ ] Cache hit sur 2ème requête
- [ ] Invalidation après update
- [ ] Rollback ne invalide pas

---

## PHASE 6: FRONTEND REACT (Jour 4-5 - 10h)

### 6.1 API Hooks (SWR)
**Référence**: Guide §8.3 Hooks Pattern

**✅ Actions:**
```javascript
// frontend/src/api/admin/{module}.js
- useGet{Entities}(params)
- create{Entity}(data)
- update{Entity}(id, data)
- delete{Entity}(id)
- bulk operations functions
```

**✅ Checklist:**
- [ ] tenantKey() utilisé
- [ ] swrFetcher configuré
- [ ] Memoization avec useMemo

### 6.2 Table Component
**Référence**: Guide §8.2 Component Pattern

**✅ Actions:**
```javascript
// frontend/src/sections/admin/{module}/{Entity}Table.jsx
- useGet{Entities}() hook
- useLocalStorage pour pagination
- useErrorWithRetry pour erreurs
- Columns avec sort/filter
- ErrorDisplay pour erreurs
- Skeleton loading states
```

**✅ Template**: Copier `UserTable.jsx` et adapter

**✅ Checklist:**
- [ ] Pagination avec localStorage
- [ ] Search/filter fonctionnels
- [ ] Row selection (checkbox)
- [ ] Actions (edit, delete, bulk)
- [ ] Error states avec retry
- [ ] Loading states (Skeleton)
- [ ] Empty states

### 6.3 Modals (Create/Edit)
**Référence**: Guide §8.4 Modal Pattern

**✅ Actions:**
```javascript
// frontend/src/sections/admin/{module}/{Entity}Modal.jsx
- Formik + Yup validation
- Create/Edit mode
- displaySuccessSnackbar() on success
- displayErrorSnackbar() on error
```

**✅ Checklist:**
- [ ] Validation Yup complète
- [ ] Loading states (disabled submit)
- [ ] Success/error feedback
- [ ] onSuccess() callback

### 6.4 Delete Alerts
**✅ Actions:**
```javascript
// Alert{Entity}Delete.jsx - Single delete
// Alert{Entity}BulkDelete.jsx - Bulk delete
- Confirmation dialog
- Warning icon
- "Cannot be undone" message
```

**✅ Checklist:**
- [ ] Confirmation requise
- [ ] Warning visible
- [ ] Bulk: affiche count

### 6.5 View Page
**✅ Actions:**
```javascript
// frontend/src/views/admin/{module}/list.jsx
- Import {Entity}Table
- Import modals
- État pour modals (open/close)
- Handlers pour actions
```

**✅ Checklist:**
- [ ] Layout correct
- [ ] Modals intégrés
- [ ] Navigation fonctionnelle

---

## PHASE 7: GESTION DES ERREURS (Jour 5 - 3h)

### 7.1 Error Messages Backend
**Référence**: Guide §3.1 Backend Error Messages

**✅ Actions:**
```python
# backend/core/error_messages.py
class {Module}ErrorMessages:
    {ENTITY}_NOT_FOUND = _("{Entity} not found")
    # ... autres messages
```

**✅ Checklist:**
- [ ] Messages centralisés
- [ ] Traductions préparées
- [ ] Utilisés dans validations

### 7.2 Error Handling Frontend
**Référence**: Guide §3.2-3.3 Frontend Errors

**✅ Actions:**
```javascript
// Dans tous composants
import { displayErrorSnackbar } from 'utils/displayError';

try {
  await operation();
} catch (error) {
  displayErrorSnackbar(error);
}
```

**✅ Checklist:**
- [ ] displayErrorSnackbar() utilisé partout
- [ ] ErrorDisplay dans tables
- [ ] Retry buttons fonctionnels
- [ ] Messages clairs pour utilisateurs

---

## PHASE 8: LOGGING (Jour 5 - 2h)

### 8.1 Logs Backend (NO PII!)
**Référence**: Guide §7 Logging

**✅ Actions:**
```python
from core.logging import get_logger, ctx_from_request
from core.logging.helpers import safe_user_context

logger = get_logger(__name__)

# Dans chaque view
ctx = ctx_from_request(request)
ctx.update({
    'event': 'entity_created',
    **safe_user_context(user)
})
logger.info("Entity created", extra=ctx)
```

**⚠️ CRITICAL Checklist:**
- [ ] ❌ AUCUN user.email dans logs
- [ ] ❌ AUCUN user.get_full_name() dans logs
- [ ] ❌ AUCUN PII (phone, address, etc.)
- [ ] ✅ Utiliser safe_user_context() TOUJOURS
- [ ] ✅ UUID uniquement
- [ ] ✅ Structured logging avec ctx

### 8.2 Logs Frontend
**Référence**: Guide §7.4 Frontend Logging

**✅ Actions:**
```javascript
import { safeConsole } from 'utils/logSanitizer';

if (process.env.NODE_ENV === 'development') {
  safeConsole.log('Operation completed', { 
    entityId: entity.id  // ✅ UUID OK
    // NO email, NO name
  });
}
```

**✅ Checklist:**
- [ ] Development only
- [ ] NO PII exposé
- [ ] safeConsole utilisé

---

## PHASE 9: TESTS (Jour 6-7 - 12h)

### 9.1 Tests Backend
**Référence**: Guide §10 Tests

**✅ Tests obligatoires:**
```python
# tests/integration/{module_name}/

✅ test_{entity}_crud.py
- test_list_success
- test_create_success
- test_update_success
- test_delete_success
- test_retrieve_success

✅ test_{entity}_permissions.py
- test_admin_can_access_client
- test_manager_can_access_team
- test_individual_can_access_mine
- test_cross_tenant_blocked

✅ test_{entity}_bulk.py
- test_bulk_create_success
- test_bulk_update_set_based
- test_bulk_delete_set_based
- test_strict_mode_rollback
- test_partial_mode_continues

✅ test_{entity}_concurrency.py
- test_race_condition_prevented (100 threads)
- test_toctou_with_lock

✅ test_{entity}_cache.py
- test_cache_hit_second_request
- test_invalidation_after_update
- test_bulk_invalidation
```

**✅ Checklist:**
- [ ] Coverage > 80%
- [ ] Tous edge cases couverts
- [ ] Tests concurrence passent
- [ ] Multi-tenant isolation vérifié

### 9.2 Tests Frontend (Manuel)
**✅ Scénarios:**
- [ ] CRUD operations complètes
- [ ] Bulk create/update/delete
- [ ] Error handling (network, 500, 429)
- [ ] Pagination (100+ records)
- [ ] Search/filter
- [ ] Permissions (différents tiers)

---

## PHASE 10: COMPLIANCE & VALIDATION FINALE (Jour 7 - 4h)

### 10.1 Security Audit
**Référence**: Guide §2 Sécurité

**⚠️ CRITICAL Checklist:**
- [ ] ❌ NO PII dans logs (audit complet)
- [ ] ❌ NO print() ou traceback exposé
- [ ] ✅ select_for_update() sur validations critiques
- [ ] ✅ Input validation complète
- [ ] ✅ SQL injection impossible (ORM only)
- [ ] ✅ XSS prevention (React escape)
- [ ] ✅ CSRF protection (credentials: true)

### 10.2 Performance Audit
**✅ Checklist:**
- [ ] NO N+1 queries
- [ ] Bulk operations set-based
- [ ] Cache hit rate > 50%
- [ ] Pagination < 100ms
- [ ] List endpoint < 500ms

### 10.3 Documentation
**Référence**: Guide §13 Documentation

**✅ Actions:**
```markdown
# backend/{module_name}/README.md
- Overview
- Models
- Endpoints
- Permissions
- Caching strategy
- Testing commands
```

**✅ Checklist:**
- [ ] README créé
- [ ] Docstrings sur fonctions complexes
- [ ] API Swagger à jour
- [ ] Architecture documentée

### 10.4 Review Checklist Globale
**✅ Backend:**
- [ ] Structure fichiers conforme
- [ ] Models avec UUID, client_account, timestamps
- [ ] ViewSets avec Scoped* mixins
- [ ] Bulk operations séparé
- [ ] Permissions registry + ownership
- [ ] Signals cache invalidation
- [ ] Tests coverage > 80%

**✅ Frontend:**
- [ ] Table avec ErrorDisplay
- [ ] Modals Formik + Yup
- [ ] API hooks SWR
- [ ] Error handling avec displayErrorSnackbar
- [ ] Loading/empty states

**✅ Sécurité:**
- [ ] NO PII in logs (audit complet)
- [ ] TOCTOU prevention
- [ ] Input validation
- [ ] Rate limiting

**✅ Performance:**
- [ ] Set-based operations
- [ ] Query optimization
- [ ] Caching
- [ ] Pagination

---

## 📊 MÉTRIQUES DE SUCCÈS

### Code Quality
- Coverage tests: **> 80%**
- Linting: **0 errors**
- Type errors: **0**

### Performance
- List endpoint: **< 500ms**
- Pagination 1000 records: **< 100ms**
- Cache hit rate: **> 50%**
- Bulk 100 items: **< 2s**

### Security
- PII in logs: **0 occurrences**
- TOCTOU vulnerabilities: **0**
- Failed security scans: **0**

### UX
- Error messages: **100% en anglais clair**
- Loading states: **100% des actions**
- Success feedback: **100% des mutations**

---

## 🔄 WORKFLOW RÉSUMÉ (1 page)

```
JOUR 1 (12h)
├─ Phase 1: Conception (4h)
│  └─ Architecture, ERD, Matrice permissions
├─ Phase 2: Backend Core (8h)
│  ├─ Models + Migrations
│  ├─ Serializers
│  ├─ ViewSets CRUD
│  ├─ ViewSet Bulk
│  └─ URLs

JOUR 2-3 (14h)
├─ Phase 3: Sécurité & Optimisation (6h)
│  ├─ Race conditions (TOCTOU)
│  ├─ Query optimization
│  └─ Validation/Sanitization
├─ Phase 4: Permissions (4h)
│  ├─ Registry
│  ├─ Ownership
│  └─ Tests permissions
└─ Phase 5: Cache & Redis (3h)
   ├─ Cache strategy
   ├─ Signals invalidation
   └─ Tests cache

JOUR 4-5 (15h)
├─ Phase 6: Frontend React (10h)
│  ├─ API hooks
│  ├─ Table component
│  ├─ Modals (Create/Edit/Delete)
│  └─ View page
├─ Phase 7: Gestion Erreurs (3h)
└─ Phase 8: Logging (2h)

JOUR 6-7 (16h)
├─ Phase 9: Tests (12h)
│  ├─ Tests backend (CRUD, permissions, bulk, concurrency)
│  └─ Tests frontend (manuel)
└─ Phase 10: Compliance & Validation (4h)
   ├─ Security audit
   ├─ Performance audit
   ├─ Documentation
   └─ Review checklist globale

TOTAL: 7 jours (~57h)
```

---

## 🚨 POINTS DE BLOCAGE FRÉQUENTS

### ⚠️ #1: Oublier `module = '{module_name}'` dans ViewSet
**Impact**: Permissions ne fonctionnent pas  
**Fix**: Toujours définir l'attribut `module`

### ⚠️ #2: PII dans logs
**Impact**: Violation SOC I/GDPR  
**Fix**: Utiliser `safe_user_context()` TOUJOURS

### ⚠️ #3: Cache invalidation AVANT commit
**Impact**: Cache stale si rollback  
**Fix**: `transaction.on_commit(lambda: invalidate_tag(...))`

### ⚠️ #4: Loops au lieu de set-based operations
**Impact**: N queries au lieu de 1  
**Fix**: `filter(id__in=ids).update()` au lieu de boucle

### ⚠️ #5: Oublier select_for_update() sur validations
**Impact**: Race conditions TOCTOU  
**Fix**: `select_for_update()` dans `transaction.atomic()`

---

## 📚 RÉFÉRENCES RAPIDES

| Besoin | Chapitre Guide |
|--------|---------------|
| ViewSet template | §1.2 |
| Bulk operations | §1.3 |
| PII protection | §2.1 |
| TOCTOU prevention | §2.3 |
| Cache strategy | §5.1 |
| Permissions | §6 |
| Logging | §7 |
| React components | §8 |
| Tests | §10 |
| Validation | §12 |

**Guide complet**: [MODULE_STANDARDIZATION_GUIDE.md](./MODULE_STANDARDIZATION_GUIDE.md)

---

**Version**: 1.0  
**Date**: 2025-01-06  
**Durée estimée**: 5-8 jours pour module complet

