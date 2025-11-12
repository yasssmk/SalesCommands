# 📘 GUIDE DE STANDARDISATION - IMPLÉMENTATION DE MODULES

## 🎯 OBJECTIF
Document de référence exhaustif pour l'implémentation de nouveaux modules dans l'application. Basé sur le module `end_users` (user management) qui sert de **golden standard** pour tous les futurs développements.

**Principe**: Chaque nouveau module doit suivre EXACTEMENT les mêmes patterns, conventions et standards pour garantir cohérence, maintenabilité et sécurité.

---

## 📋 TABLE DES MATIÈRES

1. [Architecture Backend](#1-architecture-backend)
2. [Sécurité & Compliance](#2-sécurité--compliance)
3. [Gestion des Erreurs](#3-gestion-des-erreurs)
4. [Performance & Optimisation](#4-performance--optimisation)
5. [Cache & Redis](#5-cache--redis)
6. [Permissions & Authorization](#6-permissions--authorization)
7. [Logging](#7-logging)
8. [Frontend React](#8-frontend-react)
9. [API & Axios](#9-api--axios)
10. [Tests](#10-tests)
11. [UX/UI Standards](#11-uxui-standards)
12. [Validation & Sanitization](#12-validation--sanitization)
13. [Documentation](#13-documentation)

---

## 1. ARCHITECTURE BACKEND

### 1.1 Structure des Fichiers

```
backend/
├── {module_name}/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── {entity}.py          # Un model par fichier
│   ├── serializers/
│   │   ├── __init__.py
│   │   └── {entity}_serializer.py
│   ├── views/
│   │   ├── __init__.py
│   │   ├── {entity}_view.py     # CRUD standard
│   │   └── {entity}_view_bulk.py  # Opérations bulk séparées
│   ├── signals/
│   │   ├── __init__.py
│   │   └── cache_invalidation.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_{entity}_crud.py
│   │   └── test_{entity}_permissions.py
│   └── urls.py
```

**✅ RÈGLES OBLIGATOIRES:**
- Séparer les vues CRUD et bulk dans des fichiers distincts
- Un serializer par entité
- Signals dans fichier dédié
- Tests organisés par fonctionnalité

### 1.2 ViewSets Standards

**Pattern de base:**
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from core.throttling import StandardRateThrottle
from core.cache_utils import build_drf_cache_key, cache_get_set
from core.logging import get_logger, ctx_from_request
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

logger = get_logger(__name__)


class {Entity}ViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing {entities}
    
    Features:
    - Client-scoped data isolation
    - Permission-based access control
    - Caching with Redis invalidation
    - Structured logging
    """
    
    queryset = {Entity}.objects.all()
    serializer_class = {Entity}Serializer
    permission_classes = [IsAuthenticated, ScopedPermission]
    throttle_classes = [StandardRateThrottle]
    module = '{module_name}'  # For permissions system
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['field1', 'field2']
    search_fields = ['field1', 'field2']
    ordering_fields = ['field1', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail"""
        if self.action == 'list':
            return {Entity}ListSerializer
        return {Entity}Serializer
    
    def list(self, request):
        """List with caching"""
        ctx = ctx_from_request(request)
        logger.info("Listing entities", extra=ctx)
        
        # Build cache key
        cache_key = build_drf_cache_key(
            view_name=self.__class__.__name__,
            action='list',
            client_id=request.client_id,
            query_params=request.query_params
        )
        
        def fetch_data():
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        
        # Cache for 5 minutes
        return cache_get_set(
            key=cache_key,
            producer=fetch_data,
            ttl=300,
            tag=(request.client_id, '{module_name}')
        )
```

**✅ CHECKLIST VIEWSET:**
- [ ] Hérite de `ScopedQuerysetMixin` pour isolation multi-tenant
- [ ] Permissions avec `ScopedPermission`
- [ ] Throttling approprié (Standard ou custom)
- [ ] Attribute `module` défini pour permissions
- [ ] Filters (DjangoFilterBackend, SearchFilter, OrderingFilter)
- [ ] Serializer différencié list/detail si nécessaire
- [ ] Logging structuré avec `ctx_from_request()`
- [ ] Caching sur list avec `cache_get_set()`

### 1.3 Bulk Operations (ViewSet séparé)

**Pattern obligatoire:**
```python
class {Entity}BulkViewSet({Entity}ViewSet):
    """
    Bulk operations for {entities}
    
    Features:
    - Idempotency via Idempotency-Key header
    - Set-based SQL operations (1 query vs N)
    - Strict and partial modes
    - Comprehensive error handling
    """
    
    throttle_classes = [BulkOperationThrottle]
    
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """Bulk create with idempotency"""
        # Idempotency wrapper
        pass
    
    @action(detail=False, methods=['patch'], url_path='bulk-update')
    def bulk_update(self, request):
        """Bulk update with set-based SQL"""
        pass
    
    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """Bulk delete with set-based SQL"""
        pass
    
    def _bulk_create_impl(self, request):
        """Internal implementation"""
        ctx = ctx_from_request(request)
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        
        # 1. Validation
        # 2. Business logic with transaction.atomic()
        # 3. disable_signals_with_invalidation() for cache
        # 4. Build response with _build_bulk_success_response()
        pass
```

**✅ RÈGLES BULK OPERATIONS:**
- Toujours dans ViewSet séparé (`{Entity}BulkViewSet`)
- `BulkOperationThrottle` spécifique
- Idempotency via header `Idempotency-Key`
- Set-based operations: `{Model}.objects.filter(id__in=ids).update()` au lieu de boucles
- Modes `strict` (all-or-nothing) et `partial` (best-effort)
- Response format standardisé avec `detailed` parameter
- `disable_signals_with_invalidation()` pour gérer cache

### 1.4 URLs Configuration

```python
# apps/{module_name}/urls.py

from django.urls import path
from .views import {Entity}ViewSet, {Entity}BulkViewSet

app_name = '{module_name}'

urlpatterns = [
    # Standard CRUD
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
    
    # Custom actions
    path('{entities}/<uuid:pk>/custom-action/', {Entity}ViewSet.as_view({
        'post': 'custom_action'
    }), name='{entity}-custom-action'),
    
    # Bulk operations
    path('{entities}/bulk-create/', {Entity}BulkViewSet.as_view({
        'post': 'bulk_create'
    }), name='{entity}-bulk-create'),
    
    path('{entities}/bulk-update/', {Entity}BulkViewSet.as_view({
        'patch': 'bulk_update'
    }), name='{entity}-bulk-update'),
    
    path('{entities}/bulk-delete/', {Entity}BulkViewSet.as_view({
        'delete': 'bulk_delete'
    }), name='{entity}-bulk-delete'),
]
```

**✅ CONVENTIONS URLs:**
- Utiliser `app_name` pour namespace
- Plural pour les entités (`users/`, `contacts/`)
- Bulk operations en suffixe: `bulk-create`, `bulk-update`, `bulk-delete`
- UUID primary keys: `<uuid:pk>`
- Custom actions descriptives

### 1.5 Models

**Pattern de base:**
```python
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

class {Entity}(models.Model):
    """
    {Entity} model documentation
    
    Relationships:
    - FK to ClientAccount (multi-tenant isolation)
    - FK to Owner (permissions scoping)
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Multi-tenant isolation
    client_account = models.ForeignKey(
        'end_users.ClientAccount',
        on_delete=models.CASCADE,
        related_name='{entities}'
    )
    
    # Ownership fields (for permissions)
    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='{entities}_owned'
    )
    
    created_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='{entities}_created'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = '{module_name}_{entity}'
        ordering = ['-created_at']
        verbose_name = _('{Entity}')
        verbose_name_plural = _('{Entities}')
        indexes = [
            models.Index(fields=['client_account', 'created_at']),
            models.Index(fields=['owner']),
        ]
    
    def __str__(self):
        return f"{self.__class__.__name__} {self.id}"
```

**✅ RÈGLES MODELS:**
- UUID primary keys (jamais d'auto-increment)
- FK `client_account` obligatoire pour isolation
- FK `owner` et `created_by` pour permissions
- Timestamps `created_at` / `updated_at`
- Meta avec `db_table`, `ordering`, `verbose_name`
- Indexes stratégiques (client_account, owner, created_at)

---

## 2. SÉCURITÉ & COMPLIANCE

### 2.1 PII Protection (SOC I/II Compliance)

**RÈGLE ABSOLUE: Jamais de PII dans les logs**

**✅ CORRECT:**
```python
from core.logging.helpers import safe_user_context

logger.info("User updated", extra=safe_user_context(user))
# Output: user_id=abc-123 is_active=True role_name=Admin
```

**❌ INCORRECT:**
```python
logger.info(f"User {user.email} updated")  # PII LEAK
logger.info("User created", extra={'email': user.email})  # PII LEAK
```

**Helpers obligatoires:**
```python
from core.logging.helpers import (
    safe_user_context,        # Pour User instances
    safe_user_data_context,    # Pour dicts user_data
    safe_batch_context         # Pour opérations bulk
)

# Usage
ctx = {
    'event': 'user_created',
    **safe_user_context(user)
}
logger.info("User created", extra=ctx)
```

**✅ CHECKLIST PII:**
- [ ] Aucun `user.email` dans logs
- [ ] Aucun `user.get_full_name()` dans logs
- [ ] Aucun `user.phone_number` dans logs
- [ ] Utiliser `safe_user_context()` systématiquement
- [ ] UUID uniquement (pas de PII)

### 2.2 Exception Handling (NO PII Exposure)

**Pattern obligatoire:**
```python
from core.apps_shared_methods import handle_exception

try:
    # Operations
    pass
except Exception as e:
    # ✅ CRITICAL: Use handle_exception() - NO print() or traceback
    return handle_exception(e, request, default_message="Operation failed")
```

**❌ INTERDIT:**
```python
import traceback

try:
    # Operations
    pass
except Exception as e:
    print(f"Error: {e}")  # ❌ PII peut être dans message
    traceback.print_exception(type(e), e, e.__traceback__)  # ❌❌ FUITE MASSIVE
```

### 2.3 Race Conditions (TOCTOU Prevention)

**Pattern obligatoire pour validations critiques:**
```python
from django.db import transaction

def validate_and_update(request):
    with transaction.atomic():
        # ✅ CORRECT: Lock row during validation
        entity = Entity.objects.select_for_update().get(id=entity_id)
        
        # Validation
        if not entity.can_be_modified():
            raise ValidationError("Cannot modify")
        
        # Update (protected by lock)
        entity.status = 'updated'
        entity.save()
```

**❌ INCORRECT (TOCTOU vulnerability):**
```python
# Validation
entity = Entity.objects.get(id=entity_id)
if not entity.can_be_modified():  # ❌ Check
    raise ValidationError()

# Time window here - another process can modify!

entity.status = 'updated'  # ❌ Use (data may have changed)
entity.save()
```

**✅ RÈGLES:**
- `select_for_update()` pour validations avec side-effects
- Toujours dans `transaction.atomic()`
- Lock distribué Redis si coordination inter-process nécessaire

### 2.4 Input Validation & Sanitization

**Toujours valider AVANT utilisation:**
```python
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

def validate_bulk_input(data):
    """Validate input before processing"""
    
    # Type validation
    if not isinstance(data, dict):
        raise StandardizedValidationError("Request must be a JSON object")
    
    ids = data.get('ids', [])
    
    # Presence validation
    if not ids:
        raise StandardizedValidationError(
            CoreErrorMessages.BULK_NO_DATA.format(entity="IDs")
        )
    
    # Format validation
    if not isinstance(ids, list):
        raise StandardizedValidationError(
            CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="IDs")
        )
    
    # Size validation
    if len(ids) > 500:
        raise StandardizedValidationError(
            CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="items")
        )
    
    # UUID validation
    valid_ids = set()
    for id_str in ids:
        try:
            valid_ids.add(uuid.UUID(id_str))
        except (ValueError, AttributeError):
            raise StandardizedValidationError(f"Invalid UUID: {id_str}")
    
    return valid_ids
```

---

## 3. GESTION DES ERREURS

### 3.1 Backend Error Messages (Centralisés)

**Tous les messages dans `backend/core/error_messages.py`:**
```python
# core/error_messages.py

from django.utils.translation import gettext_lazy as _

class CoreErrorMessages:
    """Core error messages (reusable across modules)"""
    
    # Validation
    REQUIRED_FIELD = _("The field '{field}' is required")
    INVALID_FORMAT = _("Invalid format for '{field}'")
    
    # Bulk operations
    BULK_NO_DATA = _("No {entity} data provided for bulk operation")
    BULK_SIZE_EXCEEDED = _("Maximum {max_size} {entity} allowed per bulk operation")
    BULK_MODE_INVALID = _("Bulk mode must be 'partial' or 'strict'")


class {Module}ErrorMessages:
    """Module-specific error messages"""
    
    {ENTITY}_NOT_FOUND = _("{Entity} with ID '{id}' not found")
    {ENTITY}_ALREADY_EXISTS = _("{Entity} with {field} '{value}' already exists")
```

**Usage:**
```python
from core.error_messages import CoreErrorMessages, {Module}ErrorMessages
from core.exceptions import StandardizedValidationError

raise StandardizedValidationError(
    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="users")
)
```

### 3.2 Frontend Error Handling

**Centralisé dans `utils/displayError.js`:**
```javascript
// Import UNIQUE point d'entrée
import { 
  displayErrorSnackbar, 
  displaySuccessSnackbar,
  displayWarningSnackbar,
  displayInfoSnackbar
} from 'utils/displayError';

// Usage dans composants
try {
  await api.updateUser(data);
  displaySuccessSnackbar('User updated successfully');
} catch (error) {
  displayErrorSnackbar(error);  // Automatic message extraction
}
```

**✅ RÈGLES:**
- Jamais de `console.error()` direct
- Toujours utiliser `displayErrorSnackbar()`
- Messages utilisateurs en anglais, clairs, actionnables
- Pas de détails techniques exposés

### 3.3 Error Display Component (Tables)

**Composant réutilisable `ErrorDisplay.jsx`:**
```javascript
import ErrorDisplay from 'components/table/ErrorDisplay';

// Usage dans tables
{error && (
  <ErrorDisplay
    error={error}
    onRetry={mutate}
    columns={columns}
    cachedData={data}
    globalFilter={globalFilter}
    emptyMessage="No users found"
  />
)}
```

**Features:**
- Adaptation UI selon type d'erreur (500, 404, 429, timeout)
- Support cached data (affiche cache pendant erreur temporaire)
- Countdown Retry-After pour 429
- Bouton retry intelligent

---

## 4. PERFORMANCE & OPTIMISATION

### 4.1 Set-Based SQL Operations

**✅ CORRECT (1 query):**
```python
# Bulk update
User.objects.filter(id__in=valid_ids).update(is_active=False)

# Bulk delete
User.objects.filter(id__in=valid_ids).delete()
```

**❌ INCORRECT (N queries):**
```python
for user_id in valid_ids:
    user = User.objects.get(id=user_id)
    user.is_active = False
    user.save()  # ❌ N queries
```

### 4.2 Query Optimization

**Patterns obligatoires:**
```python
# select_related pour FKs
users = User.objects.select_related('role', 'team', 'organization').all()

# prefetch_related pour M2M
users = User.objects.prefetch_related('permissions').all()

# only() pour réduire colonnes
users = User.objects.only('id', 'email', 'is_active')

# Éviter N+1
# ❌ BAD
for user in users:
    print(user.role.name)  # N queries

# ✅ GOOD
users = User.objects.select_related('role')
for user in users:
    print(user.role.name)  # 1 query
```

### 4.3 Pagination (Obligatoire)

**Configuration globale:**
```python
# settings.py
REST_FRAMEWORK = {
    'PAGE_SIZE': 50,
    'MAX_PAGE_SIZE': 100,
}
```

**Usage dans ViewSet:**
```python
from rest_framework.pagination import PageNumberPagination

class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

class {Entity}ViewSet(viewsets.ModelViewSet):
    pagination_class = StandardPagination
```

### 4.4 Throttling

**Patterns par type d'endpoint:**
```python
from core.throttling import (
    StandardRateThrottle,       # 30/min - GET endpoints
    BulkOperationThrottle,      # 3/min - Bulk operations
    SensitiveActionThrottle,    # 10/hour - Sensitive actions
    PasswordChangeThrottle      # 5/hour - Password changes
)

class {Entity}ViewSet(viewsets.ModelViewSet):
    throttle_classes = [StandardRateThrottle]

class {Entity}BulkViewSet({Entity}ViewSet):
    throttle_classes = [BulkOperationThrottle]

@action(detail=True, methods=['post'])
def sensitive_action(self, request, pk=None):
    self.throttle_classes = [SensitiveActionThrottle]
    # ...
```

---

## 5. CACHE & REDIS

### 5.1 Cache Strategy (Tag Versioning)

**Pattern obligatoire:**
```python
from core.cache_utils import (
    build_drf_cache_key,
    cache_get_set,
    invalidate_tag,
    disable_signals_with_invalidation
)

# Cache GET endpoint
def list(self, request):
    cache_key = build_drf_cache_key(
        view_name=self.__class__.__name__,
        action='list',
        client_id=request.client_id,
        query_params=request.query_params
    )
    
    def fetch_data():
        # Fetch from DB
        pass
    
    return cache_get_set(
        key=cache_key,
        producer=fetch_data,
        ttl=300,  # 5 minutes
        tag=(request.client_id, 'users')
    )
```

**✅ RÈGLES:**
- Tag versioning (O(1) invalidation)
- Namespace par module ('users', 'contacts', etc.)
- Client-scoped keys
- TTL adapté au type de données

### 5.2 Cache Invalidation

**Après modifications:**
```python
from core.cache_utils import invalidate_tag

def update(self, request, pk=None):
    with transaction.atomic():
        # Update entity
        entity.save()
        
        # Invalidate cache AFTER commit
        transaction.on_commit(
            lambda: invalidate_tag(request.client_id, 'entities')
        )
```

**✅ CRITICAL:**
- `transaction.on_commit()` pour invalidation
- Jamais invalidate AVANT commit (si rollback, cache stale)

### 5.3 Bulk Operations + Cache

**Pattern avec disable_signals:**
```python
from core.cache_utils import disable_signals_with_invalidation

def bulk_update(self, request):
    client_id = request.client_id
    
    with disable_signals_with_invalidation(client_id, ['users']):
        with transaction.atomic():
            # Bulk operations
            User.objects.filter(id__in=ids).update(is_active=False)
        
        # Cache invalidated automatically after commit
```

**✅ RÈGLES:**
- `disable_signals_with_invalidation()` pour bulk
- Évite N signal calls
- Invalidation automatique après commit
- Multi-namespace support: `['users', 'teams']`

### 5.4 Signal-Based Invalidation

**Configuration dans `signals/cache_invalidation.py`:**
```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from core.cache_utils import invalidate_tag, are_signals_disabled

@receiver(post_save, sender='{module_name}.{Entity}')
def invalidate_cache_on_save(sender, instance, created, **kwargs):
    if are_signals_disabled():
        return
    
    client_id = getattr(instance, "client_account_id", None)
    if not client_id:
        return
    
    # Invalidate after commit
    def _invalidate():
        invalidate_tag(client_id, '{module_name}')
    
    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_invalidate)
    else:
        _invalidate()

@receiver(post_delete, sender='{module_name}.{Entity}')
def invalidate_cache_on_delete(sender, instance, **kwargs):
    # Same pattern
    pass
```

### 5.5 Cross-Module Cache Invalidation

**RÈGLE CRITIQUE: Toujours invalider les caches des modules dépendants**

**Concept:**
Quand une entité change dans le module A et que le module B affiche des informations dérivées de A (counts, stats, listes filtrées), le cache de B DOIT être invalidé.

**Pattern Frontend (SWR):**
```javascript
// frontend/src/api/admin/{module}.js

import { revalidateMultiple } from 'api/_swr';

// ✅ CORRECT: Revalidation croisée
export async function updateUser(userId, userData) {
  const result = await api.patch(`${endpoints.users}${userId}/`, userData);

  if (result.success) {
    // Invalider TOUS les modules impactés
    revalidateMultiple([
      endpoints.users,                     // Module principal
      `${endpoints.users}${userId}/`,      // Entité spécifique
      '/client/client-accounts/',          // Stats seats
      '/client/roles/'                     // ✅ Roles.users_count impacté
    ]);

    return { success: true, user: result.data };
  }
  
  return { success: false, error: result.error };
}
```

**❌ INCORRECT: Oublier modules dépendants**
```javascript
// ❌ BAD: Seulement module principal
export async function updateUser(userId, userData) {
  const result = await api.patch(`${endpoints.users}${userId}/`, userData);

  if (result.success) {
    revalidateMultiple([
      endpoints.users
      // ❌ OUBLI: /client/roles/ reste stale!
    ]);
  }
}
```

**Scénarios typiques nécessitant revalidation croisée:**

**Scénario 1: Compteurs (counts)**
```javascript
// User a FK role → Page Roles affiche users_count
// ✅ Mutation User DOIT invalider /client/roles/

export async function createUser(userData) {
  const result = await api.post(endpoints.users, userData);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.users,
      '/client/roles/'          // ✅ users_count change
    ]);
  }
}
```

**Scénario 2: Foreign Keys**
```javascript
// Task a FK assigned_to (User) → Changer assigned_to
// ✅ Mutation Task DOIT invalider /client/users/

export async function updateTask(taskId, taskData) {
  const result = await api.patch(`${endpoints.tasks}${taskId}/`, taskData);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.tasks,
      '/client/users/'          // ✅ User.tasks_count peut changer
    ]);
  }
}
```

**Scénario 3: Filtres/Recherches**
```javascript
// Contact change → Activities filtrées par contact stale
// ✅ Mutation Contact DOIT invalider /client/activities/

export async function updateContact(contactId, contactData) {
  const result = await api.patch(`${endpoints.contacts}${contactId}/`, contactData);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.contacts,
      '/client/activities/'     // ✅ Filtres contact à jour
    ]);
  }
}
```

**Scénario 4: Quotas/Stats Globales**
```javascript
// User créé → Stats global seats_used change
// ✅ Mutation User DOIT invalider /client/client-accounts/

export async function createUser(userData) {
  const result = await api.post(endpoints.users, userData);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.users,
      '/client/client-accounts/'  // ✅ seats_used incrémenté
    ]);
  }
}
```

**✅ CHECKLIST Revalidation Croisée:**
- [ ] Cartographier TOUTES les relations FK sortantes
- [ ] Identifier modules affichant COUNT de mes entités
- [ ] Identifier modules filtrant/recherchant mes entités
- [ ] Ajouter revalidation dans create{Entity}()
- [ ] Ajouter revalidation dans update{Entity}()
- [ ] Ajouter revalidation dans delete{Entity}()
- [ ] Ajouter revalidation dans TOUTES bulk operations
- [ ] Tester: modifier entité → vérifier autres pages à jour

**Pattern Backend (Optionnel):**
Si invalidation côté backend, signal peut aussi invalider modules croisés:
```python
# backend/{module}/signals/cache_invalidation.py

@receiver(post_save, sender='{module}.{Entity}')
def invalidate_cache_on_save(sender, instance, **kwargs):
    if are_signals_disabled():
        return
    
    client_id = getattr(instance, "client_account_id", None)
    if not client_id:
        return
    
    def _invalidate():
        # Module principal
        invalidate_tag(client_id, '{module_name}')
        
        # ✅ Modules dépendants
        if hasattr(instance, 'role_id'):
            invalidate_tag(client_id, 'roles')
```

---

## 6. PERMISSIONS & AUTHORIZATION

### 6.1 Registry Configuration

**Créer `backend/permissions/registry/{module_name}_registry.py`:**
```python
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

**Puis ajouter à `backend/permissions/registry/__init__.py`:**
```python
from .{module_name}_registry import {MODULE_NAME}_REGISTRY

REGISTRY.update({MODULE_NAME}_REGISTRY)
```

### 6.2 ViewSet Integration

```python
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

class {Entity}ViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = '{module_name}'  # ✅ CRITICAL
```

### 6.3 Custom Actions Policies

**Pour actions non-CRUD:**
```python
class {Entity}ViewSet(viewsets.ModelViewSet):
    module = '{module_name}'
    
    action_policies = {
        'custom_action': {
            'crud': 'update',
            'tier': 'admin',
            'scope': 'client'
        },
        'export': {
            'crud': 'read',
            'tier': 'manager',
            'scope': 'team'
        }
    }
    
    @action(detail=False, methods=['post'])
    def custom_action(self, request):
        # Permissions checked automatically via action_policies
        pass
```

### 6.4 Ownership Mapping

**Ajouter à `backend/permissions/ownership.py`:**
```python
OWNERSHIP_MAP = {
    '{module_name}.{Entity}': {
        'type': 'standard',
        'client_account_fk': 'client_account_id',
        'owner_user': 'owner_id',
        'owner_team': 'team_id',
        'created_by': 'created_by_id',
        'assigned_to_user': None,
        'account_fk': None
    }
}
```

---

## 7. LOGGING

### 7.1 Structured Logging Pattern

**Toujours utiliser contexte structuré:**
```python
from core.logging import get_logger, ctx_from_request
from core.logging.helpers import safe_user_context

logger = get_logger(__name__)

def my_view(request):
    ctx = ctx_from_request(request)
    ctx.update({
        'event': 'entity_created',
        'entity_type': 'user',
        **safe_user_context(request.user)
    })
    
    logger.info("Entity created successfully", extra=ctx)
```

**✅ Context obligatoire:**
- `event`: Nom de l'événement
- `client_id`: Tenant ID
- `user_id`: UUID (jamais email)
- `correlation_id`: Auto-ajouté par middleware
- Métriques: `duration_ms`, `count`, etc.

### 7.2 Log Levels

**Utilisation appropriée:**
```python
# DEBUG - Dev only, verbose details
logger.debug("Processing item", extra={'item_id': item_id})

# INFO - Normal operations, audit trail
logger.info("User created", extra=ctx)

# WARNING - Unexpected but handled
logger.warning("Rate limit hit", extra=ctx)

# ERROR - Errors requiring attention
logger.error("Operation failed", extra=ctx, exc_info=True)

# CRITICAL - System failures
logger.critical("Database connection lost", extra=ctx)
```

### 7.3 NO PII in Logs (Rappel)

**✅ CORRECT:**
```python
logger.info("User updated", extra={
    'user_id': str(user.id),
    'is_active': user.is_active
})
```

**❌ INCORRECT:**
```python
logger.info(f"User {user.email} updated")  # PII
logger.info("User data", extra={'email': user.email})  # PII
```

### 7.4 Frontend Logging (Console Safe)

**Pattern avec sanitization:**
```javascript
import { safeConsole } from 'utils/logSanitizer';

// Development only
if (process.env.NODE_ENV === 'development') {
  safeConsole.log('User data loaded', { 
    userId: user.id,  // ✅ UUID OK
    // email: user.email  // ❌ PII - removed
  });
}
```

---

## 8. FRONTEND REACT

### 8.1 Structure Fichiers

```
frontend/src/
├── sections/
│   └── admin/
│       └── {module}/
│           ├── {Entity}Table.jsx
│           ├── {Entity}Modal.jsx
│           ├── {Entity}BulkEditModal.jsx
│           ├── Alert{Entity}Delete.jsx
│           ├── Alert{Entity}BulkDelete.jsx
│           └── {Entity}CSVImportModal.jsx
├── views/
│   └── admin/
│       └── {module}/
│           └── list.jsx
├── api/
│   └── admin/
│       └── {module}.js
├── hooks/
│   ├── useErrorWithRetry.js
│   ├── useLocalStorage.js
│   └── useRetryCountdown.js
└── utils/
    ├── displayError.js
    ├── snackbar.js
    ├── errorMessages.js
    └── retryLogic.js
```

### 8.2 Component Pattern (Table)

**Template standard:**
```javascript
import { useMemo, useState, useCallback } from 'react';
import { useSWRConfig } from 'swr';
import { useReactTable, getCoreRowModel, /* ... */ } from '@tanstack/react-table';

// Components
import MainCard from 'components/MainCard';
import ScrollX from 'components/ScrollX';
import ErrorDisplay from 'components/table/ErrorDisplay';
import { TableHeaderActions, DebouncedInput, HeaderSort, TablePagination } from 'components/third-party/react-table';

// API & Hooks
import { useGet{Entities} } from 'api/admin/{module}';
import useLocalStorage from 'hooks/useLocalStorage';
import { useErrorWithRetry } from 'hooks/useErrorWithRetry';

// Utils
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';
import { formatDateTime } from 'config/formatters';

export default function {Entity}Table() {
  // ===== STATE =====
  const [globalFilter, setGlobalFilter] = useState('');
  const [sorting, setSorting] = useState([]);
  const [pagination, setPagination] = useLocalStorage(
    '{entity}TablePagination',
    { pageIndex: 0, pageSize: 50 }
  );
  
  // ===== DATA FETCHING =====
  const { data, error, isLoading, isValidating, mutate } = useGet{Entities}({
    page: pagination.pageIndex + 1,
    page_size: pagination.pageSize,
    search: globalFilter,
    ordering: /* ... */
  });
  
  // Error handling with retry
  useErrorWithRetry(error, isValidating);
  
  // ===== TABLE COLUMNS =====
  const columns = useMemo(() => [
    {
      id: 'select',
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllRowsSelected()}
          onChange={table.getToggleAllRowsSelectedHandler()}
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
        />
      )
    },
    {
      accessorKey: 'name',
      header: 'Name',
      cell: ({ getValue }) => getValue()
    },
    // ...
  ], []);
  
  // ===== TABLE INSTANCE =====
  const table = useReactTable({
    data: data?.results || [],
    columns,
    state: { globalFilter, sorting, pagination },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    manualPagination: true,
    pageCount: data?.total_pages || 0,
  });
  
  // ===== RENDER =====
  return (
    <MainCard content={false}>
      <TableHeaderActions
        table={table}
        globalFilter={globalFilter}
        setGlobalFilter={setGlobalFilter}
        onAdd={() => setOpenModal(true)}
      />
      
      <ScrollX>
        <Table>
          <TableHead>
            {/* Headers */}
          </TableHead>
          <TableBody>
            {error ? (
              <ErrorDisplay
                error={error}
                onRetry={mutate}
                columns={columns}
                cachedData={data}
              />
            ) : isLoading ? (
              <TableRow>
                <TableCell colSpan={columns.length}>
                  <Skeleton />
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map(row => (
                <TableRow key={row.id}>
                  {/* Cells */}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </ScrollX>
      
      <TablePagination table={table} />
    </MainCard>
  );
}
```

**✅ CHECKLIST COMPONENT:**
- [ ] `useLocalStorage` pour pagination persistence
- [ ] `useErrorWithRetry` pour gestion erreurs
- [ ] `ErrorDisplay` component pour erreurs
- [ ] `Skeleton` loading states
- [ ] Memoization avec `useMemo` / `useCallback`
- [ ] Columns avec sort/filter
- [ ] Row selection avec checkbox
- [ ] TableHeaderActions avec search

### 8.3 Hooks Pattern (SWR)

**Template API hook:**
```javascript
// api/admin/{module}.js
import useSWR from 'swr';
import { useMemo } from 'react';
import { tenantKey, swrFetcher } from 'api/_swr';

export function useGet{Entities}(params = {}) {
  const key = useMemo(() => {
    const baseKey = tenantKey('/{module}/{entities}/');
    
    const queryParams = new URLSearchParams();
    if (params.page) queryParams.append('page', params.page);
    if (params.page_size) queryParams.append('page_size', params.page_size);
    if (params.search) queryParams.append('search', params.search);
    if (params.ordering) queryParams.append('ordering', params.ordering);
    
    return queryParams.toString() 
      ? `${baseKey}?${queryParams}` 
      : baseKey;
  }, [params.page, params.page_size, params.search, params.ordering]);
  
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    key,
    swrFetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 2000,
    }
  );
  
  return {
    data,
    error,
    isLoading,
    isValidating,
    mutate
  };
}

/**
 * CREATE ENTITY
 * ✅ CRITICAL: Always revalidate related modules
 */
export async function create{Entity}(data) {
  try {
    const url = tenantKey('/{module}/{entities}/');
    const result = await api.post(url, data);

    if (result.success) {
      // ✅ Revalidate main module + related modules
      revalidateMultiple([
        '/{module}/{entities}/',        // Main module
        '/client/related-module/'       // Related modules (if any)
      ]);
      
      return { success: true, data: result.data };
    }

    return { success: false, error: result.error };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * UPDATE ENTITY
 * ✅ CRITICAL: Revalidate specific entity + list + related modules
 */
export async function update{Entity}(id, data) {
  try {
    const url = tenantKey(`/{module}/{entities}/${id}/`);
    const result = await api.patch(url, data);

    if (result.success) {
      // ✅ Revalidate main module + specific entity + related modules
      revalidateMultiple([
        '/{module}/{entities}/',        // List
        `/{module}/{entities}/${id}/`,  // Specific entity
        '/client/related-module/'       // Related modules (if any)
      ]);
      
      return { success: true, data: result.data };
    }

    return { success: false, error: result.error };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * DELETE ENTITY
 * ✅ CRITICAL: Revalidate main module + related modules
 */
export async function delete{Entity}(id) {
  try {
    const url = tenantKey(`/{module}/{entities}/${id}/`);
    const result = await api.delete(url);

    if (result.success || result.status === 204) {
      // ✅ Revalidate main module + related modules
      revalidateMultiple([
        '/{module}/{entities}/',        // Main module
        '/client/related-module/'       // Related modules (if any)
      ]);
      
      return { success: true };
    }

    return { success: false, error: result.error };
  } catch (error) {
    return { success: false, error: error.message };
  }
}
```

### 8.4 Modal Pattern (Create/Edit)

```javascript
import { useState, useEffect } from 'react';
import { 
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Button, Grid 
} from '@mui/material';
import { Formik, Form, Field } from 'formik';
import * as Yup from 'yup';

export default function {Entity}Modal({ open, onClose, entity, onSuccess }) {
  const isEdit = Boolean(entity);
  
  const initialValues = {
    name: entity?.name || '',
    // ...
  };
  
  const validationSchema = Yup.object({
    name: Yup.string().required('Name is required'),
    // ...
  });
  
  const handleSubmit = async (values, { setSubmitting }) => {
    try {
      if (isEdit) {
        await update{Entity}(entity.id, values);
        displaySuccessSnackbar('{Entity} updated');
      } else {
        await create{Entity}(values);
        displaySuccessSnackbar('{Entity} created');
      }
      
      onSuccess();
      onClose();
    } catch (error) {
      displayErrorSnackbar(error);
    } finally {
      setSubmitting(false);
    }
  };
  
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {isEdit ? 'Edit {Entity}' : 'Create {Entity}'}
      </DialogTitle>
      
      <Formik
        initialValues={initialValues}
        validationSchema={validationSchema}
        onSubmit={handleSubmit}
      >
        {({ errors, touched, isSubmitting }) => (
          <Form>
            <DialogContent>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Field
                    as={TextField}
                    name="name"
                    label="Name"
                    fullWidth
                    error={touched.name && Boolean(errors.name)}
                    helperText={touched.name && errors.name}
                  />
                </Grid>
              </Grid>
            </DialogContent>
            
            <DialogActions>
              <Button onClick={onClose}>Cancel</Button>
              <Button 
                type="submit" 
                variant="contained"
                disabled={isSubmitting}
              >
                {isEdit ? 'Update' : 'Create'}
              </Button>
            </DialogActions>
          </Form>
        )}
      </Formik>
    </Dialog>
  );
}
```

**✅ RÈGLES MODAL:**
- Formik + Yup validation
- Disabled submit pendant loading
- Success snackbar
- Error handling avec `displayErrorSnackbar()`
- `onSuccess()` callback pour refresh

---

## 9. API & AXIOS

### 9.1 Axios Configuration (Profiles)

**Utiliser profils de timeout appropriés:**
```javascript
import { api } from 'utils/axiosClient';

// GET requests - 8s timeout (critical profile)
const response = await api.get('/users/');

// Bulk operations - 18s timeout
const response = await api.post(
  '/users/bulk-create/',
  data,
  { profile: 'bulk' }
);

// Mutations - 10s timeout (default)
const response = await api.post('/users/', data);
```

**Profils disponibles:**
- `critical`: 8s - GET principal (users, contacts)
- `widget`: 4s - Widgets dashboard
- `mutation`: 10s - POST/PUT/PATCH (default)
- `bulk`: 18s - Bulk operations
- `auth`: 5s - Login, refresh

### 9.2 Error Handling Pattern

```javascript
import { api } from 'utils/axiosClient';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

async function performOperation() {
  try {
    const response = await api.post('/users/', data);
    
    if (response.success) {
      displaySuccessSnackbar('Operation successful');
      return response.data;
    } else {
      displayErrorSnackbar(response);
      return null;
    }
  } catch (error) {
    displayErrorSnackbar(error);
    return null;
  }
}
```

### 9.3 Retry Logic (Automatic)

**Configuré globalement dans axios interceptor:**
- Network errors: 3 retries with exponential backoff
- 5xx errors: 3 retries
- 429 Rate Limit: Wait `Retry-After` header
- 408 Timeout: 3 retries
- 401 Unauthorized: Auto token refresh

**Pas d'action requise dans composants**

### 9.4 Idempotency (Automatic)

**Auto-injection Idempotency-Key:**
```javascript
// Automatique pour POST/PATCH/DELETE
await api.post('/users/', data);
// Header: Idempotency-Key: uuid-auto-generated

// Override manuel si nécessaire
await api.post('/users/', data, {
  headers: { 'Idempotency-Key': 'custom-key' }
});
```

---

## 10. TESTS

### 10.1 Structure Tests Backend

```
backend/tests/
├── integration/
│   └── {module_name}/
│       ├── test_{entity}_crud.py
│       ├── test_{entity}_permissions.py
│       ├── test_{entity}_bulk.py
│       └── test_{entity}_concurrency.py
└── unit/
    └── {module_name}/
        ├── test_{entity}_model.py
        ├── test_{entity}_serializer.py
        └── test_logging_helpers.py
```

### 10.2 Fixtures Pattern (pytest)

```python
# tests/integration/{module_name}/conftest.py

import pytest
import uuid
from django.urls import reverse
from rest_framework.test import APIClient

@pytest.fixture
def api():
    """API client without CSRF"""
    return APIClient(enforce_csrf_checks=False)

@pytest.fixture
def tenants(db):
    """Create test tenants"""
    return {
        "A": uuid.uuid4(),
        "B": uuid.uuid4()
    }

@pytest.fixture
def client_accounts(db, tenants):
    """Create client accounts"""
    from end_users.models import ClientAccount
    return {
        "A": ClientAccount.objects.create(
            id=tenants["A"],
            name="Company A"
        ),
        "B": ClientAccount.objects.create(
            id=tenants["B"],
            name="Company B"
        )
    }

@pytest.fixture
def users(db, tenants, client_accounts):
    """Create test users"""
    from end_users.models import User
    
    admin = User.objects.create(
        email="admin@company-a.test",
        client_account_id=tenants["A"],
        is_superuser=True
    )
    
    return {
        "admin": admin,
        # ...
    }

def authenticate_user(api, user, client_id):
    """Helper to authenticate user"""
    claims = {
        "origin": "end_users",
        "user_id": str(user.id),
        "client_account": str(client_id),
    }
    api.force_authenticate(user=user, token=claims)
```

### 10.3 Test Template (CRUD)

```python
import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db(transaction=True)

class Test{Entity}CRUD:
    """Test CRUD operations for {Entity}"""
    
    def test_list_success(self, api, users, tenants):
        """Test listing entities"""
        authenticate_user(api, users["admin"], tenants["A"])
        
        url = reverse('{module}:{entity}-list')
        response = api.get(f"{url}?client_id={tenants['A']}")
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
    
    def test_create_success(self, api, users, tenants):
        """Test creating entity"""
        authenticate_user(api, users["admin"], tenants["A"])
        
        data = {
            "name": "Test Entity",
            # ...
        }
        
        url = reverse('{module}:{entity}-list')
        response = api.post(
            f"{url}?client_id={tenants['A']}", 
            data, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == "Test Entity"
    
    def test_cross_tenant_isolation(self, api, users, tenants):
        """Test multi-tenant isolation"""
        # Create entity in tenant A
        entity_a = {Entity}.objects.create(
            name="Entity A",
            client_account_id=tenants["A"]
        )
        
        # Admin from tenant B cannot access entity A
        authenticate_user(api, users["admin_b"], tenants["B"])
        
        url = reverse('{module}:{entity}-detail', args=[entity_a.id])
        response = api.get(f"{url}?client_id={tenants['B']}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
```

### 10.4 Test Coverage Requirements

**Minimum coverage: 80%**

**Tests obligatoires:**
- [ ] CRUD operations (list, create, retrieve, update, delete)
- [ ] Permissions (admin, manager, individual)
- [ ] Multi-tenant isolation
- [ ] Bulk operations (create, update, delete)
- [ ] Validation errors
- [ ] Race conditions (TOCTOU)
- [ ] Cache invalidation
- [ ] PII sanitization in logs

**✅ Test Cross-Module Revalidation (Frontend):**
```javascript
// Test manuel critique - À faire pour chaque nouveau module

describe('Cross-Module Cache Revalidation', () => {
  test('Creating {entity} invalidates related module cache', async () => {
    // 1. Charger page du module dépendant (ex: Roles)
    // 2. Noter la valeur d'un count (ex: users_count = 5)
    // 3. Créer une entité qui impacte ce count (ex: User avec role X)
    // 4. Retourner sur page du module dépendant
    // 5. ✅ VÉRIFIER: users_count = 6 (mise à jour automatique)
    // 6. ❌ SI users_count = 5 → revalidation manquante!
  });

  test('Updating {entity} invalidates related module cache', async () => {
    // Même pattern pour update
  });

  test('Deleting {entity} invalidates related module cache', async () => {
    // Même pattern pour delete
  });
});
```

**Scénario de test typique:**
1. Ouvrir page Roles → Noter `users_count` pour "Manager" = 10
2. Créer nouveau User avec role="Manager"
3. Retourner sur page Roles
4. ✅ ATTENDU: `users_count` pour "Manager" = 11 (sans F5)
5. ❌ SI = 10 → Bug: revalidation `/client/roles/` manquante

---

## 11. UX/UI STANDARDS

### 11.1 Loading States

**Pattern standard:**
```javascript
{isLoading ? (
  <TableRow>
    <TableCell colSpan={columns.length}>
      <Skeleton variant="rectangular" height={50} />
    </TableCell>
  </TableRow>
) : (
  // Data rows
)}
```

### 11.2 Empty States

```javascript
{data?.results?.length === 0 && (
  <TableRow>
    <TableCell colSpan={columns.length} align="center">
      <Stack spacing={1} alignItems="center" py={6}>
        <Typography variant="h6" color="text.secondary">
          No {entities} found
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {globalFilter 
            ? 'Try adjusting your search terms' 
            : 'Create your first {entity} to get started'}
        </Typography>
      </Stack>
    </TableCell>
  </TableRow>
)}
```

### 11.3 Confirmation Dialogs

```javascript
<Dialog open={openDelete} onClose={() => setOpenDelete(false)}>
  <DialogTitle>
    <WarningOutlined style={{ color: 'error.main', fontSize: 24 }} />
    Confirm Delete
  </DialogTitle>
  <DialogContent>
    <Typography>
      Are you sure you want to delete <strong>{entity.name}</strong>?
      This action cannot be undone.
    </Typography>
  </DialogContent>
  <DialogActions>
    <Button onClick={() => setOpenDelete(false)}>
      Cancel
    </Button>
    <Button 
      onClick={handleDelete} 
      color="error" 
      variant="contained"
      disabled={isDeleting}
    >
      Delete
    </Button>
  </DialogActions>
</Dialog>
```

### 11.4 Snackbar Messages

**Conventions:**
- Success: "Entity created successfully"
- Update: "Entity updated successfully"
- Delete: "Entity deleted successfully"
- Bulk: "3 entities updated successfully"
- Error: Clear, actionable message

```javascript
displaySuccessSnackbar('User created successfully');
displayErrorSnackbar('Failed to create user. Please try again.');
displayWarningSnackbar('Some users could not be updated');
displayInfoSnackbar('Export in progress. You will be notified when complete.');
```

---

## 12. VALIDATION & SANITIZATION

### 12.1 Backend Validation (Serializers)

```python
from rest_framework import serializers

class {Entity}Serializer(serializers.ModelSerializer):
    class Meta:
        model = {Entity}
        fields = ['id', 'name', 'email', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate_email(self, value):
        """Custom email validation"""
        if {Entity}.objects.filter(
            email=value,
            client_account=self.context['request'].client_id
        ).exists():
            raise serializers.ValidationError(
                "Entity with this email already exists"
            )
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        if data.get('start_date') > data.get('end_date'):
            raise serializers.ValidationError(
                "Start date must be before end date"
            )
        return data
```

### 12.2 Frontend Validation (Yup)

```javascript
import * as Yup from 'yup';

const validationSchema = Yup.object({
  name: Yup.string()
    .required('Name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be less than 100 characters'),
  
  email: Yup.string()
    .required('Email is required')
    .email('Invalid email format'),
  
  phone: Yup.string()
    .matches(/^[0-9+\-() ]+$/, 'Invalid phone format')
    .nullable(),
  
  date: Yup.date()
    .min(new Date(), 'Date must be in the future')
    .required('Date is required'),
});
```

### 12.3 Input Sanitization

**Backend:**
```python
def sanitize_input(value):
    """Remove HTML tags and trim whitespace"""
    if not isinstance(value, str):
        return value
    
    # Remove HTML tags
    value = re.sub(r'<[^>]+>', '', value)
    
    # Trim whitespace
    value = value.strip()
    
    return value
```

**Frontend:**
```javascript
const sanitizeInput = (value) => {
  if (typeof value !== 'string') return value;
  
  // Trim whitespace
  value = value.trim();
  
  // Remove potentially dangerous characters
  value = value.replace(/[<>]/g, '');
  
  return value;
};
```

---

## 13. DOCUMENTATION

### 13.1 Code Documentation

**Docstrings obligatoires:**
```python
def complex_function(param1, param2):
    """
    Short description of what the function does.
    
    Longer explanation if needed, including:
    - Business logic details
    - Performance considerations
    - Security implications
    
    Args:
        param1 (str): Description of param1
        param2 (int): Description of param2
    
    Returns:
        dict: Description of return value
        
    Raises:
        ValidationError: When validation fails
        PermissionDenied: When user lacks permission
    
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result)
        {'status': 'success'}
    """
    pass
```

### 13.2 API Documentation (OpenAPI/Swagger)

**Décorateurs pour auto-documentation:**
```python
from drf_spectacular.utils import extend_schema, OpenApiParameter

@extend_schema(
    summary="List all entities",
    description="Returns paginated list of entities with optional filtering",
    parameters=[
        OpenApiParameter(
            name='search',
            description='Search term for filtering',
            required=False,
            type=str
        ),
    ],
    responses={
        200: {Entity}Serializer(many=True),
        400: 'Bad Request',
        401: 'Unauthorized',
    }
)
def list(self, request):
    pass
```

### 13.3 README Module

**Template `backend/{module_name}/README.md`:**
```markdown
# {Module Name}

## Overview
Brief description of the module's purpose and features.

## Models
- **{Entity}**: Description
  - Fields: ...
  - Relationships: ...

## Endpoints
- `GET /{entities}/` - List entities
- `POST /{entities}/` - Create entity
- `GET /{entities}/{id}/` - Retrieve entity
- `PATCH /{entities}/{id}/` - Update entity
- `DELETE /{entities}/{id}/` - Delete entity
- `POST /{entities}/bulk-create/` - Bulk create
- `PATCH /{entities}/bulk-update/` - Bulk update
- `DELETE /{entities}/bulk-delete/` - Bulk delete

## Permissions
- Admin: Full access
- Manager: Team-scoped
- Individual: Own records only

## Caching
- List endpoints: 5 minutes TTL
- Detail endpoints: 10 minutes TTL
- Invalidation: On create/update/delete

## Testing
```bash
pytest tests/integration/{module_name}/ -v
```
```

---

## ✅ CHECKLIST COMPLÈTE NOUVEAU MODULE

### Backend
- [ ] Structure fichiers respectée
- [ ] Models avec UUID, client_account, timestamps
- [ ] ViewSet avec ScopedQuerysetMixin + ScopedPermission
- [ ] Bulk operations dans ViewSet séparé
- [ ] Serializers avec validation
- [ ] URLs configurées
- [ ] Permissions registry créé
- [ ] Ownership mapping défini
- [ ] Signals cache invalidation
- [ ] Logging avec safe_user_context()
- [ ] Aucune PII dans logs
- [ ] Tests CRUD complets
- [ ] Tests permissions
- [ ] Tests multi-tenant
- [ ] Tests bulk operations
- [ ] Coverage > 80%

### Frontend
- [ ] Structure fichiers respectée
- [ ] Table component avec ErrorDisplay
- [ ] Modal Create/Edit avec Formik + Yup
- [ ] Alert Delete avec confirmation
- [ ] Bulk operations modals
- [ ] API hooks avec SWR
- [ ] useErrorWithRetry pour error handling
- [ ] useLocalStorage pour pagination
- [ ] displayErrorSnackbar pour erreurs
- [ ] Loading states (Skeleton)
- [ ] Empty states
- [ ] Retry buttons
- [ ] CSV import/export si nécessaire

### Sécurité
- [ ] PII protection (NO PII in logs)
- [ ] TOCTOU prevention (select_for_update)
- [ ] Input validation (backend + frontend)
- [ ] Input sanitization
- [ ] SQL injection protection (ORM usage)
- [ ] XSS prevention (React escape)
- [ ] CSRF protection (credentials: true)
- [ ] Rate limiting (throttles)

### Performance
- [ ] Set-based SQL (bulk operations)
- [ ] select_related / prefetch_related
- [ ] Pagination obligatoire
- [ ] Caching avec tag versioning
- [ ] Cache invalidation post-commit
- [ ] Indexes DB stratégiques
- [ ] Query optimization

### Documentation
- [ ] Code docstrings
- [ ] README module
- [ ] API documentation (Swagger)
- [ ] Permission matrix
- [ ] Architecture decisions

---

## 📚 RÉFÉRENCES CLÉS

### Fichiers de référence (end_users)
- Backend: `backend/end_users/views/user_view_bulk.py`
- Frontend: `frontend/src/sections/admin/users/UserTable.jsx`
- Tests: `backend/tests/integration/end_users/test_perm.py`
- API: `frontend/src/api/admin/users.js`

### Utilitaires centralisés
- Logging: `backend/core/logging/`
- Cache: `backend/core/cache_utils.py`
- Permissions: `backend/permissions/`
- Errors: `frontend/src/utils/displayError.js`
- Axios: `frontend/src/utils/axiosClient.js`

---

## 🎓 FORMATION ÉQUIPE

**Pour chaque nouveau développeur:**
1. Lire ce document en entier
2. Étudier le module `end_users` (golden standard)
3. Comprendre les patterns de sécurité (PII, TOCTOU)
4. Maîtriser le système de permissions
5. Pratiquer avec un module simple avant production

**Revue code obligatoire:**
- Vérifier conformité avec ce guide
- Vérifier absence PII dans logs
- Vérifier tests coverage > 80%
- Vérifier documentation complète

---

**Version**: 1.0  
**Date**: 2025-01-06  
**Basé sur**: Module `end_users` (User Management)  
**Mainteneur**: Architecture Team

