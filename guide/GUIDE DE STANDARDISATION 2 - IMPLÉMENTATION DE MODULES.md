# 📘 GUIDE DE STANDARDISATION - IMPLÉMENTATION DE MODULES

**Version**: 2.0  
**Date**: 2025-01-14  
**Basé sur**: Audit exhaustif des modules `end_users` (User & Role Management)  
**Mainteneur**: Architecture Team

---

## 🎯 OBJECTIF

Document de référence **EXACT** pour l'implémentation de nouveaux modules. Basé sur l'audit rigoureux des fichiers réels `user_view.py`, `role_views.py`, `user_view_bulk.py`, serializers, et frontend.

**Principe**: Chaque nouveau module doit suivre **EXACTEMENT** ces patterns pour garantir cohérence, maintenabilité et sécurité.

---

## 📋 TABLE DES MATIÈRES

1. [Architecture Backend](#1-architecture-backend)
2. [Serializers](#2-serializers)
3. [Bulk Operations](#3-bulk-operations)
4. [Sécurité & Compliance](#4-sécurité--compliance)
5. [Cache & Redis](#5-cache--redis)
6. [Permissions & Authorization](#6-permissions--authorization)
7. [Logging & Audit](#7-logging--audit)
8. [Frontend React](#8-frontend-react)
9. [API Hooks SWR](#9-api-hooks-swr)
10. [Validation & Sanitization](#10-validation--sanitization)
11. [Tests](#11-tests)
12. [Checklist Complète](#12-checklist-complète)

---

## 1. ARCHITECTURE BACKEND

### 1.1 Structure Fichiers

```
backend/
├── {module_name}/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── {entity}.py
│   ├── serializers/
│   │   ├── __init__.py
│   │   └── {entity}_serializers.py    # Tous serializers dans 1 fichier
│   ├── views/
│   │   ├── __init__.py
│   │   ├── {entity}_view.py          # CRUD standard
│   │   └── {entity}_view_bulk.py     # Bulk operations SÉPARÉ
│   ├── signals/
│   │   ├── __init__.py
│   │   └── cache_invalidation.py
│   ├── tests/
│   │   └── integration/
│   │       └── {module_name}/
│   │           ├── test_{entity}_crud.py
│   │           ├── test_{entity}_permissions.py
│   │           └── test_{entity}_bulk.py
│   └── urls.py
```

### 1.2 Imports OBLIGATOIRES - ViewSet

```python
# backend/{module_name}/views/{entity}_view.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Exists, OuterRef, Prefetch
from django.db import transaction
from django.utils import timezone
from django.http import Http404

# ✅ Core utilities
from core.cache_utils import (
    build_drf_cache_key,
    cache_get_set,
    get_permissions_version,
    invalidate_tag,
    _is_redis_backend,
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication

# ✅ Logging & Audit SOC 2
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

# ✅ Permissions
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

# ✅ Models & Serializers
from ..models import {Entity}
from ..serializers.{entity}_serializers import (
    {Entity}Serializer,
    {Entity}ListSerializer,
    {Entity}CreateSerializer,
    {Entity}UpdateSerializer,
)

logger = get_logger(__name__)
```

### 1.3 Déclaration ViewSet - PATTERN EXACT

```python
class {Entity}ViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing {entities}
    
    Features:
    - Client-scoped data isolation (multi-tenant)
    - Permission-based access control
    - Caching with Redis tag versioning
    - Structured logging + SOC 2 audit trail
    - Query optimization with annotations
    
    Endpoints:
        - GET    /{entities}/           - List all entities
        - POST   /{entities}/           - Create entity
        - GET    /{entities}/{id}/      - Retrieve entity
        - PUT    /{entities}/{id}/      - Update entity (full)
        - PATCH  /{entities}/{id}/      - Update entity (partial)
        - DELETE /{entities}/{id}/      - Delete entity
    
    Permissions:
        - Read: authenticated users (scoped to client/team/mine)
        - Write/Update/Delete: according to permission registry
    """
    
    # ✅ OBLIGATOIRE: Queryset de base
    queryset = {Entity}.objects.all()
    
    # ✅ OBLIGATOIRE: Serializer par défaut
    serializer_class = {Entity}Serializer
    
    # ✅ OBLIGATOIRE: entity_name pour BaseAPIView
    entity_name = '{entity}'
    
    # ✅ OBLIGATOIRE: Authentication
    authentication_classes = [CustomJWTAuthentication]
    
    # ✅ OBLIGATOIRE: Permissions
    permission_classes = [IsAuthenticated, ScopedPermission]
    
    # ✅ OBLIGATOIRE: Module pour permissions registry
    module = '{module_name}'
    
    # ✅ OPTIONNEL: Policies pour custom actions (non-CRUD)
    action_policies = {
        'custom_action': {
            'crud': 'update',    # read/create/update/delete
            'tier': 'admin',     # admin/manager/individual (optionnel)
            'scope': 'client'    # client/team/mine
        },
        'export': {
            'crud': 'read',
            'scope': 'client'
        }
    }
    
    # ✅ OBLIGATOIRE: Filters configuration
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['field1', 'field2', 'is_active']
    search_fields = ['name', 'field1', 'field2']
    ordering_fields = ['name', 'field1', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    # ✅ OPTIONNEL: Throttling (seulement si nécessaire)
    # throttle_classes = [StandardRateThrottle]  # NE PAS mettre sur ViewSet standard
```

### 1.4 get_serializer_class() - PATTERN

```python
def get_serializer_class(self):
    """
    Sélection du serializer selon l'action.
    Optimise les performances et applique les bonnes validations.
    """
    if self.action == 'list':
        return {Entity}ListSerializer
    elif self.action == 'create':
        return {Entity}CreateSerializer  # Si validations spécifiques
    elif self.action in ['update', 'partial_update']:
        return {Entity}UpdateSerializer  # Si validations spécifiques
    return {Entity}Serializer
```

### 1.5 get_queryset() - PATTERN AVEC ANNOTATIONS

```python
def get_queryset(self):
    """
    Récupère les entités avec optimisations selon l'action.
    Applique le client scoping et annotations pour performance.
    """
    # ✅ Appeler super() pour client scoping
    queryset = super().get_queryset().select_related('client_account')
    
    # ✅ IMPORTANT: Annotations pour éviter N queries dans serializers
    queryset = queryset.annotate(
        related_count=Count('related_model', distinct=True),
        active_count=Count(
            'related_model',
            filter=Q(related_model__is_active=True),
            distinct=True
        ),
        # Autres annotations selon besoins...
    )
    
    # ✅ Optimisations spécifiques par action
    if self.action == 'list':
        # Liste: select_related uniquement (pas de prefetch pour performance)
        queryset = queryset.select_related('fk_field1', 'fk_field2')
        
    elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
        # Détails: select_related + prefetch_related
        queryset = queryset.select_related('fk_field1', 'fk_field2')
        queryset = queryset.prefetch_related(
            Prefetch(
                'related_model',
                queryset=RelatedModel.objects.select_related('nested_fk'),
                to_attr='prefetched_related'
            )
        )
    
    return queryset
```

### 1.6 list() - PATTERN AVEC CACHE REDIS

```python
def list(self, request, *args, **kwargs):
    """
    Liste toutes les entités du client avec cache.
    
    Cache:
        - TTL: 300s (5 minutes)
        - Tag versioning: (client_id, '{module_name}')
        - Skip si pas Redis disponible
    """
    client_id = self.get_client_id()
    
    # ✅ Skip cache si pas Redis
    if not _is_redis_backend():
        queryset = self.filter_queryset(self.get_queryset())
        response = self._serialize_list_queryset(queryset, client_id)
        return Response(response)
    
    # ✅ Build cache key avec query params
    cache_key = build_drf_cache_key(
        view_name=self.__class__.__name__,
        action='list',
        client_id=client_id,
        query_params=request.query_params
    )
    
    # ✅ Cache producer function
    def fetch_data():
        queryset = self.filter_queryset(self.get_queryset())
        return self._serialize_list_queryset(queryset, client_id)
    
    # ✅ Cache get/set avec tag versioning
    cached_response = cache_get_set(
        key=cache_key,
        producer=fetch_data,
        ttl=300,  # 5 minutes
        tag=(client_id, '{module_name}')
    )
    
    return Response(cached_response)
```

### 1.7 _serialize_list_queryset() - HELPER METHOD

```python
def _serialize_list_queryset(self, queryset, client_id):
    """
    Serialize le queryset avec metadata pour list responses (cache friendly).
    
    Returns:
        dict: {
            'success': True,
            'data': {
                'results': [...],
                'count': int,
                'next': str|null,
                'previous': str|null
            },
            'metadata': {
                'client_id': str,
                'generated_at': str
            }
        }
    """
    timestamp = timezone.now().isoformat()
    metadata = {
        'client_id': str(client_id) if client_id else None,
        'generated_at': timestamp,
    }
    
    # ✅ Pagination
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
    
    # ✅ Sans pagination
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

### 1.8 create() - PATTERN AVEC AUDIT LOG

```python
def create(self, request, *args, **kwargs):
    """
    Créer une nouvelle entité.
    
    Features:
        - Transaction atomique
        - Cache invalidation après commit
        - Audit log SOC 2
        - Validation stricte via serializer
    """
    try:
        # ✅ Validation et création
        serializer = self.get_serializer(
            data=request.data,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        
        # ✅ Transaction atomique pour intégrité
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
            extra={'name': instance.name}  # Champs métier pertinents
        )
        
        # ✅ Logging application
        ctx = ctx_from_request(request)
        ctx.update({
            'event': '{entity}_created',
            'entity_id': str(instance.id),
            'entity_name': instance.name
        })
        logger.info('{entity}_created', extra=ctx)
        
        # ✅ Retourner avec serializer complet
        full_serializer = {Entity}Serializer(
            instance,
            context=self.get_serializer_context()
        )
        
        return Response({
            'success': True,
            'message': f"{Entity} '{instance.name}' created successfully",
            'data': full_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return self.handle_exception(e)
```

### 1.9 _invalidate_all_related_caches() - HELPER

```python
def _invalidate_all_related_caches(self, client_id):
    """
    Invalider TOUS les caches liés à ce module.
    
    CRITICAL: Inclure TOUS les modules dépendants (FK, counts, etc.)
    
    Args:
        client_id: Client UUID
    """
    if not client_id:
        return
    
    # ✅ Module principal
    invalidate_tag(client_id, '{module_name}')
    
    # ✅ IMPORTANT: Modules dépendants
    # Si ce module a des FK vers d'autres modules, les invalider aussi
    invalidate_tag(client_id, 'related_module1')  # Ex: users si rôle changé
    invalidate_tag(client_id, 'related_module2')  # Ex: teams si user changé
    
    # ✅ Log pour debugging
    logger.info('cache_invalidation_{module}_related', extra={
        'event': 'cache_invalidation',
        'client_id': str(client_id),
        'tags': ['{module_name}', 'related_module1', 'related_module2']
    })
```

### 1.10 URLs Configuration

**Fichier**: `backend/{module_name}/urls.py`

```python
# backend/{module_name}/urls.py

from django.urls import path
from .views import {Entity}ViewSet, {Entity}BulkViewSet

app_name = '{module_name}'

urlpatterns = [
    # ✅ Standard CRUD
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
    
    # ✅ Custom actions (si nécessaire)
    path('{entities}/<uuid:pk>/custom-action/', {Entity}ViewSet.as_view({
        'post': 'custom_action'
    }), name='{entity}-custom-action'),
    
    # ✅ Bulk operations (ViewSet séparé)
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

**Puis register dans** `backend/salescommands/urls.py`:
```python
urlpatterns = [
    # ...
    path('client/', include('end_users.urls')),
    path('client/', include('{module_name}.urls')),  # ✅ Ajouter cette ligne
]
```

---

## 2. SERIALIZERS

### 2.1 Structure Fichier Serializer

**UN SEUL fichier** `{entity}_serializers.py` contenant:
- `{Entity}Serializer` (principal, complet)
- `{Entity}ListSerializer` (optimisé pour list)
- `{Entity}CreateSerializer` (validations création)
- `{Entity}UpdateSerializer` (validations modification)
- `{Entity}BulkCreateSerializer` (bulk operations)

### 2.2 Imports OBLIGATOIRES - Serializer

```python
# backend/{module_name}/serializers/{entity}_serializers.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

# ✅ OBLIGATOIRE: ClientScopeManager mixin
from core.client_scope import ClientScopeManager

# ✅ Exceptions & Messages
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

# ✅ Logging
from core.logging import get_logger, ctx_from_request

# ✅ Models
from ..models import {Entity}

logger = get_logger(__name__)
```

### 2.3 Serializer Principal - PATTERN EXACT

```python
class {Entity}Serializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer principal pour {Entity} avec validation complète.
    
    Features:
        - Client scoping automatique via mixin
        - Champs calculés pour performance
        - Validation métier robuste
        - Read-only fields protection
    """
    
    # ✅ Champs calculés en lecture seule
    client_account_name = serializers.CharField(
        source='client_account.name',
        read_only=True
    )
    
    # ✅ SerializerMethodField pour logique complexe
    related_count = serializers.SerializerMethodField(read_only=True)
    active_count = serializers.SerializerMethodField(read_only=True)
    
    # ✅ Champs d'écriture avec validation
    related_field = serializers.PrimaryKeyRelatedField(
        queryset=RelatedModel.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Related Field')
        }
    )
    
    class Meta:
        model = {Entity}
        fields = [
            # ✅ Identifiants
            'id', 'name',
            
            # ✅ Relations
            'related_field', 'related_field_name',
            
            # ✅ Client scoping
            'client_id', 'client_account', 'client_account_name',
            
            # ✅ Champs calculés
            'related_count', 'active_count',
            
            # ✅ Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'client_account', 'client_id', 'client_account_name',
            'related_count', 'active_count',
            'created_at', 'updated_at'
        ]
    
    def get_related_count(self, obj):
        """
        Récupère le count depuis annotation queryset si disponible.
        Fallback sur .count() si pas d'annotation (moins performant).
        """
        if hasattr(obj, 'related_count'):
            return obj.related_count
        return obj.related_model.count()
    
    def get_active_count(self, obj):
        """Idem pour active count"""
        if hasattr(obj, 'active_count'):
            return obj.active_count
        return obj.related_model.filter(is_active=True).count()
    
    def validate_name(self, value):
        """
        Validation du nom avec unicité par client.
        
        Pattern:
            1. Normaliser (trim, capitalize)
            2. Vérifier unicité dans client
            3. Exclure instance actuelle si update
        """
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
            )
        
        # Normaliser
        value = value.strip()
        
        # Client ID depuis contexte
        client_id = self._get_client_id_from_context()
        
        # Vérifier unicité (case-insensitive)
        queryset = {Entity}.objects.filter(
            client_account_id=client_id,
            name__iexact=value
        )
        
        # Exclure instance actuelle en cas d'update
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        
        if queryset.exists():
            raise StandardizedValidationError(
                CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields=f"name '{value}'"
                )
            )
        
        return value
    
    def validate(self, attrs):
        """
        Validation globale inter-champs.
        
        Examples:
            - Cohérence dates (start < end)
            - Dépendances entre champs
            - Business rules complexes
        """
        # Récupérer client_id pour validations
        client_id = self._get_client_id_from_context()
        attrs['client_account_id'] = client_id
        
        # Validations métier...
        # if attrs.get('field1') and not attrs.get('field2'):
        #     raise StandardizedValidationError("Field2 required when Field1 is set")
        
        return attrs
```

### 2.4 List Serializer - OPTIMISÉ

```python
class {Entity}ListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer optimisé pour les listes (performance critique).
    
    Principes:
        - Champs minimum nécessaires pour affichage table
        - SerializerMethodField pour relations (évite N+1)
        - Pas de nested serializers profonds
    """
    
    # ✅ Relations sous forme d'objets simples (frontend-friendly)
    related_field = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = {Entity}
        fields = [
            # ✅ Identité minimale
            'id', 'name',
            
            # ✅ Relations (objets simples)
            'related_field', 'related_field_name',
            
            # ✅ Status
            'is_active',
            
            # ✅ Timestamps essentiels
            'created_at'
        ]
        read_only_fields = fields
    
    def get_related_field(self, obj):
        """
        Retourner relation sous forme d'objet minimal.
        Compatible usage frontend: row.original.related_field?.name
        """
        if obj.related_field:
            return {
                'id': str(obj.related_field_id),
                'name': obj.related_field.name
            }
        return None
```

### 2.5 Create/Update Serializers

```python
class {Entity}CreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer spécialisé pour création avec validations strictes.
    """
    
    class Meta:
        model = {Entity}
        fields = ['name', 'field1', 'field2', 'related_field']
        extra_kwargs = {
            'name': {'required': True},
            'field1': {'required': False, 'default': 'default_value'},
        }
    
    def validate(self, attrs):
        """Validations spécifiques à la création"""
        client_id = self._get_client_id_from_context()
        attrs['client_account_id'] = client_id
        
        # Validations métier création...
        
        return attrs


class {Entity}UpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour modifications (PATCH).
    """
    
    class Meta:
        model = {Entity}
        fields = ['name', 'field1', 'field2']
        extra_kwargs = {
            'name': {'required': False},
            'field1': {'required': False},
        }
    
    def update(self, instance, validated_data):
        """
        Update avec logique métier.
        
        Pattern:
            1. Vérifier protections (locked, system entity, etc.)
            2. Appliquer modifications
            3. Sauvegarder
            4. Post-processing (denormalization, etc.)
        """
        # Protection entités système
        if getattr(instance, 'is_locked', False):
            raise StandardizedValidationError(
                CoreErrorMessages.PERMISSION_DENIED + " - Cannot modify locked entity"
            )
        
        # Appliquer modifications
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Post-processing si nécessaire
        # Ex: denormalization, cascade updates, etc.
        
        return instance
```

---

## 3. BULK OPERATIONS

### 3.1 Structure Bulk ViewSet

**TOUJOURS dans fichier séparé**: `{entity}_view_bulk.py`

```python
# backend/{module_name}/views/{entity}_view_bulk.py

"""
{Entity} Bulk Operations ViewSet

Handles bulk create/update/delete with:
    - Idempotency via Redis
    - Set-based SQL (1 query vs N)
    - Strict/partial modes
    - Comprehensive error handling
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

# ✅ OBLIGATOIRE: BulkOperationThrottle
from core.throttling import BulkOperationThrottle

# ✅ Idempotency layer
from core.idempotency import (
    start_op,
    complete_op,
    fail_op,
    get_owner_from_request,
    compute_payload_hash
)

# ✅ Logging helpers pour bulk
from core.logging.helpers import safe_batch_context

# ✅ Cache management
from core.cache_utils import disable_signals_with_invalidation

from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

from ..models import {Entity}
from .{entity}_view import {Entity}ViewSet

logger = get_logger(__name__)


class {Entity}BulkViewSet({Entity}ViewSet):
    """
    ViewSet for bulk {entity} operations.
    
    Inherits authentication, permissions, and client scoping from {Entity}ViewSet.
    All operations support idempotency via Idempotency-Key header.
    
    Optimizations:
        - Set-based SQL: 1 query for N operations
        - Signal disable during bulk ops
        - Batch logging with safe_batch_context
    """
    
    # ✅ OBLIGATOIRE: Throttling spécifique bulk
    throttle_classes = [BulkOperationThrottle]
    
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Bulk create entities - IDEMPOTENT wrapper.
        
        Query params:
            - mode: 'strict' (all-or-nothing) or 'partial' (best-effort)
            - detailed: 'true' for full response, 'false' for summary only
        
        Headers:
            - Idempotency-Key: UUID for idempotency (auto-generated if missing)
        """
        # Idempotency wrapper
        idempotency_key = request.headers.get('Idempotency-Key')
        owner = get_owner_from_request(request)
        payload_hash = compute_payload_hash(request.data)
        
        # Check existing operation
        existing = start_op(idempotency_key, owner, payload_hash)
        if existing:
            return Response(existing, status=status.HTTP_200_OK)
        
        try:
            # Execute business logic
            result = self._bulk_create_impl(request)
            
            # Mark complete
            complete_op(idempotency_key, result)
            
            return Response(result, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            fail_op(idempotency_key, str(e))
            raise
    
    def _bulk_create_impl(self, request):
        """
        Internal implementation of bulk create.
        
        Steps:
            1. Validate input (max 500 items)
            2. Serialize & validate each item
            3. Bulk insert with disable_signals
            4. Build response (summary + details if requested)
        """
        ctx = ctx_from_request(request)
        mode = request.query_params.get('mode', 'partial')
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        
        # ✅ 1. Validate input
        data_list = request.data.get('{entities}', [])
        
        if not data_list:
            raise StandardizedValidationError(
                CoreErrorMessages.BULK_NO_DATA.format(entity='{entities}')
            )
        
        if len(data_list) > 500:
            raise StandardizedValidationError(
                CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity='items')
            )
        
        # ✅ 2. Validate each item
        serializer = {Entity}CreateSerializer(
            data=data_list,
            many=True,
            context=self.get_serializer_context()
        )
        
        if mode == 'strict':
            serializer.is_valid(raise_exception=True)
        
        # ✅ 3. Bulk insert with signal disable
        client_id = self.get_client_id()
        
        with disable_signals_with_invalidation(client_id, ['{module_name}', 'related_module']):
            with transaction.atomic():
                # Bulk insert
                instances = {Entity}.objects.bulk_create([
                    {Entity}(**item) for item in serializer.validated_data
                ])
        
        # ✅ 4. Audit log
        audit_log(
            event='{entity}_bulk_create_success',
            action='bulk_create',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='{entity}',
            target_count=len(instances),
            outcome='success'
        )
        
        # ✅ 5. Build response
        result = {
            'success': True,
            'summary': {
                'requested': len(data_list),
                'created': len(instances),
                'failed': len(data_list) - len(instances)
            }
        }
        
        if detailed:
            result['data'] = {Entity}Serializer(instances, many=True).data
        
        return result
    
    @action(detail=False, methods=['patch'], url_path='bulk-update')
    def bulk_update(self, request):
        """
        Bulk update entities - SET-BASED SQL.
        
        Pattern:
            - Extract IDs + update_data from request
            - filter(id__in=ids).update(**update_data)  # 1 query!
            - NO loop, NO save() per instance
        """
        # Similar pattern...
        pass
    
    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Bulk delete entities - SET-BASED SQL.
        
        Pattern:
            - Extract IDs from request
            - filter(id__in=ids).delete()  # 1 query!
            - NO loop, NO instance.delete()
        """
        # Similar pattern...
        pass
```

---

## 4. SÉCURITÉ & COMPLIANCE

### 4.1 PII Protection (SOC 2)

**RÈGLE ABSOLUE: Jamais de PII dans les logs**

```python
# ✅ CORRECT
from core.logging.helpers import safe_user_context

logger.info("User updated", extra=safe_user_context(user))
# Output: user_id=abc-123 is_active=True role_name=Admin

# ❌ INCORRECT
logger.info(f"User {user.email} updated")  # PII LEAK!
logger.info("User data", extra={'email': user.email})  # PII LEAK!
```

**Helpers obligatoires:**
```python
from core.logging.helpers import (
    safe_user_context,        # Pour User instances
    safe_user_data_context,    # Pour dicts (bulk operations)
    safe_batch_context         # Pour listes (batch processing)
)

# Usage dans create()
ctx = ctx_from_request(request)
ctx.update({
    'event': 'entity_created',
    **safe_user_context(request.user)  # Spread pattern
})
logger.info('Entity created', extra=ctx)
```

### 4.2 Audit Log SOC 2 - OBLIGATOIRE

```python
from core.logging.audit import audit_log

# ✅ OBLIGATOIRE après CHAQUE mutation (create/update/delete)
audit_log(
    event='{entity}_create_success',    # event identifier
    action='create',                     # create/update/delete/bulk_*
    actor_id=str(request.user.id),      # UUID only
    client_id=str(client_id),           # tenant UUID
    target_type='{entity}',             # entity type
    target_id=str(instance.id),         # entity UUID
    outcome='success',                   # success/failure
    extra={'name': instance.name}       # business context (NO PII)
)
```

### 4.3 Race Conditions (TOCTOU Prevention)

```python
from django.db import transaction

# ✅ CORRECT: Lock row during validation
with transaction.atomic():
    entity = {Entity}.objects.select_for_update().get(id=entity_id)
    
    # Validation
    if not entity.can_be_modified():
        raise ValidationError("Cannot modify")
    
    # Update (protected by lock)
    entity.status = 'updated'
    entity.save()

# ❌ INCORRECT: TOCTOU vulnerability
entity = {Entity}.objects.get(id=entity_id)
if not entity.can_be_modified():  # ❌ Check
    raise ValidationError()

# Time window - autre process peut modifier!

entity.status = 'updated'  # ❌ Use (data may have changed)
entity.save()
```

---

## 5. CACHE & REDIS

### 5.1 Pattern Invalidation - CRITICAL

**Après CHAQUE mutation:**
```python
# ✅ Dans transaction.on_commit() pour safety
with transaction.atomic():
    instance.save()
    
    # ✅ CRITICAL: Invalider APRÈS commit
    transaction.on_commit(
        lambda: self._invalidate_all_related_caches(client_id)
    )
```

**Helper method:**
```python
def _invalidate_all_related_caches(self, client_id):
    """
    CRITICAL: Invalider module principal + TOUS modules dépendants.
    
    Règle: Si module A a FK vers B, ou B affiche count de A,
           alors mutation A DOIT invalider cache B.
    """
    if not client_id:
        return
    
    # Module principal
    invalidate_tag(client_id, '{module_name}')
    
    # ✅ IMPORTANT: Modules dépendants (compléter selon relations)
    invalidate_tag(client_id, 'users')     # Si rôle changé
    invalidate_tag(client_id, 'teams')     # Si user changé
    invalidate_tag(client_id, 'accounts')  # Si stats impactées
```

**Mapping relations → invalidation:**
- User modifié → Invalider `roles` (users_count change)
- Role modifié → Invalider `users` (permissions change)
- Team modifié → Invalider `users` + `organizations`
- Règle: **Cartographier TOUTES les dépendances avant implémentation**

---

## 6. PERMISSIONS & AUTHORIZATION

### 6.1 Registry Configuration

**Fichier**: `backend/permissions/registry/{module_name}_registry.py`

```python
from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']

{MODULE_NAME}_REGISTRY: Dict[str, Dict[Action, Dict[Tier, Scope]]] = {
    '{entities}': {
        'create': {
            'admin': 'client',     # Admin can create for all client
            'manager': 'team',     # Manager can create for team
            'individual': 'none'   # Individual cannot create
        },
        'read': {
            'admin': 'client',     # Admin sees all
            'manager': 'team',     # Manager sees team
            'individual': 'mine'   # Individual sees own
        },
        'update': {
            'admin': 'client',
            'manager': 'team',
            'individual': 'mine'
        },
        'delete': {
            'admin': 'client',
            'manager': 'none',     # Manager cannot delete
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

---

## 7. LOGGING & AUDIT

### 7.1 Logging Standard

```python
from core.logging import get_logger, ctx_from_request

logger = get_logger(__name__)

# ✅ Pattern standard
ctx = ctx_from_request(request)
ctx.update({
    'event': 'entity_action',
    'entity_id': str(entity.id),
    'entity_type': '{entity}'
})
logger.info('Entity action completed', extra=ctx)
```

### 7.2 Niveaux de Log

```python
# DEBUG - Dev only
logger.debug("Processing item", extra={'item_id': str(item_id)})

# INFO - Normal operations (audit trail)
logger.info("Entity created", extra=ctx)

# WARNING - Unexpected but handled
logger.warning("Rate limit approaching", extra=ctx)

# ERROR - Errors requiring attention
logger.error("Operation failed", extra=ctx, exc_info=True)

# CRITICAL - System failures
logger.critical("Database connection lost", extra=ctx)
```

---

## 8. FRONTEND REACT

### 8.1 Structure Fichiers

```
frontend/src/
├── views/
│   └── admin/
│       └── {module}/
│           └── list.jsx                 # ✅ Page container (orchestration)
├── sections/
│   └── admin/
│       └── {module}/
│           ├── {Entity}Table.jsx       # ✅ Table wrapper (minimal)
│           ├── Form{Entity}Add.jsx     # ✅ Create form
│           ├── Form{Entity}Edit.jsx    # ✅ Edit form
│           ├── Form{Entity}BulkEdit.jsx # ✅ Bulk edit
│           ├── Alert{Entity}Delete.jsx  # ✅ Delete confirmation
│           └── Alert{Entity}BulkDelete.jsx
└── api/
    └── admin/
        └── {module}.js                  # ✅ SWR hooks + mutations
```

### 8.2 Page Container - PATTERN EXACT

**Fichier**: `frontend/src/views/admin/{module}/list.jsx`

```javascript
// frontend/src/views/admin/{module}/list.jsx

'use client';
import { useMemo, useState, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';

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
 * Map frontend column IDs to backend field names
 * Critical for server-side sorting
 */
const COLUMN_TO_BACKEND_FIELD = {
  name: 'name',
  created_at: 'created_at',
  field1: 'field1'
};

// ==============================|| {MODULE} LIST PAGE ||============================== //

/**
 * Main container page for {Entity} management.
 * 
 * Architecture:
 * - ReusableTable used directly (no wrapper component)
 * - Columns defined HERE with useMemo
 * - All state management (pagination, search, sorting) HERE
 * - Modals orchestrated HERE
 * 
 * This pattern matches User & Role management for consistency.
 */
export default function {Entities}ListPage() {
  const { tenantId } = useAuth();
  
  const MAX_PAGE_SIZE = 100;
  
  // ==============================|| STATE ||============================== //
  
  // Pagination with localStorage persistence
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('{entity}TablePageSize', 10);
  
  const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 10;
    return Math.min(parsed, MAX_PAGE_SIZE);
  }, [pageSize]);
  
  // Search - server-side filtering
  const [search, setSearch] = useState('');
  
  // Sorting - TanStack format
  const [sorting, setSorting] = useState([]);
  
  // Modals
  const [addModal, setAddModal] = useState(false);
  const [editModal, setEditModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);
  
  // ==============================|| COMPUTED ||============================== //
  
  /**
   * Convert TanStack sorting to Django ordering
   * Example: [{id: 'name', desc: true}] → '-name'
   */
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
  
  // Build SWR key for cache revalidation
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
   * ✅ CRITICAL: Columns defined in page, NOT in table component
   * This pattern matches User & Role management
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
          <IconButton
            color="primary"
            onClick={() => handleEdit(row.original)}
          >
            <EditOutlined />
          </IconButton>
          <IconButton
            color="error"
            onClick={() => handleDelete(row.original)}
          >
            <DeleteOutlined />
          </IconButton>
        </Stack>
      )
    }
  ], [handleEdit, handleDelete]);
  
  // ==============================|| RENDER ||============================== //
  
  return (
    <>
      <Box>
        {/* Header with Add button */}
        <Stack direction="row" justifyContent="space-between" mb={2}>
          <Typography variant="h3">{Entities}</Typography>
          <Button variant="contained" onClick={handleAdd}>
            Add {Entity}
          </Button>
        </Stack>
        
        {/* ✅ ReusableTable directly (no wrapper) */}
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

### 8.3 Table Component - MINIMAL WRAPPER

**Fichier**: `frontend/src/sections/admin/{module}/{Entity}Table.jsx`

```javascript
// frontend/src/sections/admin/{module}/{Entity}Table.jsx

/**
 * ✅ IMPORTANT: Ce composant est un WRAPPER MINIMAL
 * 
 * Il ne fait que passer les props à ReusableTable.
 * AUCUNE logique métier ici.
 * 
 * Pourquoi ce wrapper existe:
 * - Cohérence architecturale
 * - Point d'extension future si nécessaire
 * - Facilite tests
 */

import PropTypes from 'prop-types';
import ReusableTable from 'components/table/Table';

function {Entity}Table(props) {
  return <ReusableTable {...props} />;
}

{Entity}Table.propTypes = {
  data: PropTypes.array,
  columns: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.object,
  // ... autres props ReusableTable
};

export default {Entity}Table;
```

---

## 9. API HOOKS SWR

### 9.1 Structure API File

**Fichier**: `frontend/src/api/admin/{module}.js`

```javascript
// frontend/src/api/admin/{module}.js

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { 
  tenantKey, 
  revalidateMultiple 
} from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  {entities}: '/client/{entities}/',
  {entity}Detail: (id) => `/client/{entities}/${id}/`,
};

// ==============================|| HELPER ||============================== //

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

// ==============================|| READ HOOKS ||============================== //

/**
 * ✅ GET ALL ENTITIES
 * 
 * @param {Object} params - { page, pageSize, search, ordering }
 * @returns {Object} { {entities}Loading, {entities}, {entities}Count, {entities}Error }
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

// ==============================|| MUTATIONS ||============================== //

/**
 * ✅ CREATE ENTITY
 * 
 * CRITICAL: Revalidation croisée obligatoire
 */
export async function create{Entity}(data) {
  // ✅ Validation UUID fields
  const uuidFields = ['related_field_id'];
  for (const field of uuidFields) {
    const value = data[field];
    if (value && !isValidUUID(value)) {
      return {
        success: false,
        error: `Invalid ${field} format`
      };
    }
  }
  
  // ✅ Sanitize strings
  const sanitized = sanitizeObject(data, ['name', 'description']);
  
  const result = await api.post(endpoints.{entities}, sanitized);
  
  if (result.success) {
    // ✅ CRITICAL: Invalider module principal + dépendants
    revalidateMultiple([
      endpoints.{entities},           // Module principal
      '/client/related-module1/',     // Module dépendant 1
      '/client/related-module2/'      // Module dépendant 2
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
 * ✅ UPDATE ENTITY
 * 
 * CRITICAL: Revalidation module + entity + dépendants
 */
export async function update{Entity}(entityId, data) {
  // ✅ Validate entity ID
  if (!entityId || !isValidUUID(entityId)) {
    return {
      success: false,
      error: 'Invalid entity ID format'
    };
  }
  
  // ✅ Validate related UUIDs
  const uuidFields = ['related_field_id'];
  for (const field of uuidFields) {
    const value = data[field];
    if (value && !isValidUUID(value)) {
      return {
        success: false,
        error: `Invalid ${field} format`
      };
    }
  }
  
  const sanitized = sanitizeObject(data, ['name', 'description']);
  
  const result = await api.patch(endpoints.{entity}Detail(entityId), sanitized);
  
  if (result.success) {
    // ✅ CRITICAL: Revalidation croisée
    revalidateMultiple([
      endpoints.{entities},              // Liste
      endpoints.{entity}Detail(entityId), // Entity specific
      '/client/related-module1/',        // Dépendants
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
 * ✅ DELETE ENTITY
 */
export async function delete{Entity}(entityId) {
  if (!entityId || !isValidUUID(entityId)) {
    return {
      success: false,
      error: 'Invalid entity ID format',
      status: 400
    };
  }
  
  const result = await api.delete(endpoints.{entity}Detail(entityId));
  
  if (result.success || result.status === 204) {
    // ✅ Revalidation
    revalidateMultiple([
      endpoints.{entities},
      '/client/related-module1/'
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

---

## 10. VALIDATION & SANITIZATION

### 10.1 Backend Validation

**Dans serializer:**
```python
def validate_name(self, value):
    """Validation avec messages centralisés"""
    if not value or not value.strip():
        raise StandardizedValidationError(
            CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
        )
    
    value = value.strip()
    
    # Unicité
    client_id = self._get_client_id_from_context()
    if {Entity}.objects.filter(
        client_account_id=client_id,
        name__iexact=value
    ).exclude(id=self.instance.id if self.instance else None).exists():
        raise StandardizedValidationError(
            CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields=f"name '{value}'")
        )
    
    return value
```

### 10.2 Frontend Validation

**Yup schemas:**
```javascript
import * as Yup from 'yup';
import { isValidUUID } from 'utils/validators';

const validationSchema = Yup.object({
  name: Yup.string()
    .required('Name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be less than 100 characters'),
  
  related_field_id: Yup.string()
    .nullable()
    .test('is-valid-uuid', 'Invalid selection', function(value) {
      if (!value) return true;
      return isValidUUID(value);
    })
});
```

---

## 11. TESTS

### 11.1 Backend Tests Obligatoires

```
backend/tests/integration/{module_name}/
├── test_{entity}_crud.py          # CRUD operations
├── test_{entity}_permissions.py   # Permissions matrix
├── test_{entity}_bulk.py          # Bulk operations
└── test_{entity}_concurrency.py   # Race conditions
```

**Template test CRUD:**
```python
import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db(transaction=True)

class Test{Entity}CRUD:
    def test_list_success(self, api, users, tenants):
        """Test listing entities"""
        authenticate_user(api, users["admin"], tenants["A"])
        
        url = reverse('{module}:{entity}-list')
        response = api.get(f"{url}?client_id={tenants['A']}")
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
    
    def test_create_success(self, api, users, tenants):
        """Test creating entity"""
        # Similar pattern...
    
    def test_cross_tenant_isolation(self, api, users, tenants):
        """Test multi-tenant isolation"""
        # Critical test...
```

---

## 12. CHECKLIST COMPLÈTE

### Backend
- [ ] Structure fichiers conforme
- [ ] ViewSet: `ScopedQuerysetMixin + BaseAPIView + ModelViewSet`
- [ ] Attributs: `entity_name`, `module`, `authentication_classes`, `permission_classes`
- [ ] Serializers: Principal + List + Create + Update (tous dans 1 fichier)
- [ ] Serializers héritent de `ClientScopeManager.SerializerMixin`
- [ ] `get_queryset()` avec annotations pour performance
- [ ] `list()` avec cache Redis + `_serialize_list_queryset()`
- [ ] `create()` avec `transaction.atomic()` + `audit_log()` + cache invalidation
- [ ] `_invalidate_all_related_caches()` inclut TOUS modules dépendants
- [ ] Bulk operations dans fichier séparé avec `BulkOperationThrottle`
- [ ] Set-based SQL (NO loops)
- [ ] Logging: `safe_user_context()` systématique (NO PII)
- [ ] Audit log SOC 2 pour toutes mutations
- [ ] Registry permissions complet
- [ ] Tests coverage > 80%

### Frontend
- [ ] Architecture: Columns dans `list.jsx` (page), pas dans Table component
- [ ] State management: page, pageSize (localStorage), search, sorting dans page
- [ ] Handlers: pagination, search, sorting dans page (callbacks)
- [ ] `COLUMN_TO_BACKEND_FIELD` mapping pour sorting
- [ ] API hooks: `useGet{Entities}` avec useMemo sur swrKey
- [ ] Mutations: `create/update/delete` avec validation UUID
- [ ] `revalidateMultiple()` sur TOUS endpoints impactés
- [ ] Formik + Yup validation
- [ ] `handleFormikError()` pour error handling
- [ ] Loading states (Skeleton)
- [ ] Empty states
- [ ] Error states avec retry

### Sécurité
- [ ] AUCUNE PII dans logs (audit exhaustif)
- [ ] `safe_user_context()` utilisé partout
- [ ] `audit_log()` pour toutes mutations
- [ ] TOCTOU prevention (`select_for_update()`)
- [ ] Validation UUID client-side ET server-side
- [ ] Sanitization inputs

### Cache & Performance
- [ ] Cache sur `list()` avec tag versioning
- [ ] Invalidation dans `transaction.on_commit()`
- [ ] `_invalidate_all_related_caches()` complet
- [ ] Set-based SQL bulk operations
- [ ] Annotations queryset (éviter N+1)
- [ ] select_related / prefetch_related appropriés

---

**Fin du guide. Ce document reflète EXACTEMENT les patterns réels extraits du code.**

**Questions? Référez-vous aux fichiers sources:**
- Backend: `backend/end_users/views/{user,role}_view{,_bulk}.py`
- Serializers: `backend/end_users/serializers/{user,role}_serializers.py`
- Frontend: `frontend/src/views/admin/{users,roles}/list.jsx`
- API: `frontend/src/api/admin/{users,roles}.js`