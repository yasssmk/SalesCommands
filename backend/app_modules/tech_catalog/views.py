# app_modules/tech_catalog/views.py
"""
ViewSet for the TechCatalog module.

Five standard REST endpoints — list, retrieve, create, partial_update,
destroy — calqué sur le pattern CompanyAccountViewSet, without the
partner/hierarchy/qualification surface.

Permission model:
    All writes (create/update/delete) are admin-only, enforced by
    ScopedPermission against permissions/registry/tech_catalog_registry.py.
    Reads are open to admin/manager/individual within the tenant — sales
    reps will need read access to power AsyncTechCatalogSelect in
    downstream consumers (Decision Cycle, Product, signals).

Caching:
    list/retrieve responses are cached per (tenant, user, perm_version,
    query) when Redis is available, mirroring the pattern in
    CompanyAccountViewSet. Every write invalidates the
    TECH_CATALOG_CACHE_TAG for the tenant, dropping all cached lists
    and details in one shot.

Tenant isolation:
    ScopedQuerysetMixin filters every read by the requesting user's
    tenant, using the entry registered in OWNERSHIP_MAP['tech_catalog']
    (client_account_fk='client_id').

No custom actions:
    The catalog is a pure reference list. There is no validate /
    deprecate / merge / hierarchy surface — those were intentionally
    out of scope. If a future need arises (e.g. bulk import for tenant
    onboarding), it will be added explicitly, not retrofitted.
"""

from django.db import transaction
from django.http import Http404

from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from core.apps_shared_methods import BaseAPIView
from core.cache_utils import (
    _is_redis_backend,
    build_drf_cache_key,
    cache_get_set,
    get_permissions_version,
    invalidate_tag,
)
from core.error_messages import CoreErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import ctx_from_request, get_logger
from core.logging.audit import audit_log

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from app_modules.tech_catalog.constants import TECH_CATALOG_CACHE_TAG
from app_modules.tech_catalog.models import TechCatalog
from app_modules.tech_catalog.serializers import (
    TechCatalogCreateSerializer,
    TechCatalogListSerializer,
    TechCatalogSerializer,
    TechCatalogUpdateSerializer,
)


logger = get_logger(__name__)


class TechCatalogViewSet(
    OwnerScopeMixin,
    ScopedQuerysetMixin,
    BaseAPIView,
    viewsets.ModelViewSet,
):
    """
    REST endpoints for tenant-level TechCatalog entries.

    Standard CRUD only — no custom @action methods. The five canonical
    endpoints are wired in urls.py:

        GET    /tech-catalog/             → list
        POST   /tech-catalog/             → create     (admin only)
        GET    /tech-catalog/<uuid>/      → retrieve
        PATCH  /tech-catalog/<uuid>/      → partial_update (admin only)
        DELETE /tech-catalog/<uuid>/      → destroy    (admin only)
    """

    queryset = TechCatalog.objects.all()
    serializer_class = TechCatalogSerializer
    entity_name = 'tech_catalog'

    # -------------------------------------------------------------------------
    # Filtering / search / ordering
    # -------------------------------------------------------------------------

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    # No FilterSet class — keeping this MVP. Filters can be added later
    # via a TechCatalogFilter when an actual UI need surfaces.
    filterset_class = None

    # Server-side search hits both names — useful when reps know the
    # vendor but not the product, or vice versa.
    search_fields = ['company_name', 'product_name']

    ordering_fields = [
        'company_name',
        'product_name',
        'created_at',
        'updated_at',
    ]
    ordering = ['company_name', 'product_name']

    # -------------------------------------------------------------------------
    # Auth & permission scope
    # -------------------------------------------------------------------------

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'tech_catalog'

    # No custom action policies — the registry's CRUD matrix covers
    # every endpoint exposed by this ViewSet.

    # =========================================================================
    # SERIALIZER ROUTING
    # =========================================================================

    def get_serializer_class(self):
        if self.action == 'list':
            return TechCatalogListSerializer
        if self.action == 'create':
            return TechCatalogCreateSerializer
        if self.action in ('update', 'partial_update'):
            return TechCatalogUpdateSerializer
        return TechCatalogSerializer

    # =========================================================================
    # QUERYSET
    # =========================================================================

    def get_queryset(self):
        """
        Tenant-scoped queryset, with select_related on audit FKs for
        the detail view to keep retrieve at a single query.
        """
        queryset = super().get_queryset()

        # OwnerScope filter — TechCatalog has no owner_user in the
        # OWNERSHIP_MAP, so this is effectively a no-op for `mine`/`team`
        # scopes. It's still here for consistency with the Account
        # pattern: if the `owner_scope` query param is ever extended
        # to mean something module-specific, this hook is in place.
        queryset = self.apply_owner_scope_filter(queryset)

        if self.action in ('retrieve', 'update', 'partial_update'):
            queryset = queryset.select_related('created_by', 'updated_by')

        return queryset

    # =========================================================================
    # CACHE HELPERS
    # =========================================================================

    def _invalidate_caches(self, client_id):
        """Invalidate every cached list/detail for the tenant."""
        invalidate_tag(client_id, TECH_CATALOG_CACHE_TAG)

    # =========================================================================
    # LIST / RETRIEVE
    # =========================================================================

    def list(self, request, *args, **kwargs):
        """
        GET /tech-catalog/

        Cached when Redis is the backend; falls through to a direct
        queryset render when running on the file-based dev cache.
        """
        if not _is_redis_backend():
            response = super().list(request, *args, **kwargs)
            return Response({'success': True, 'data': response.data})

        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()
        query_string = request.META.get('QUERY_STRING', '')

        cache_key = build_drf_cache_key(
            namespace='tech_catalog_list',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            query_string=query_string,
            tag_namespace=TECH_CATALOG_CACHE_TAG,
        )

        def producer():
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return {
                    'success': True,
                    'data': {
                        'results': serializer.data,
                        'count': self.paginator.page.paginator.count,
                        'next': self.paginator.get_next_link(),
                        'previous': self.paginator.get_previous_link(),
                    },
                }

            serializer = self.get_serializer(queryset, many=True)
            return {'success': True, 'data': serializer.data}

        cached = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, TECH_CATALOG_CACHE_TAG),
        )

        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'tech_catalog_list',
            'result_count': (
                cached.get('data', {}).get('count', '-')
                if isinstance(cached.get('data'), dict)
                else '-'
            ),
        })
        logger.info('tech_catalog_list', extra=ctx)

        return Response(cached)

    def retrieve(self, request, *args, **kwargs):
        """GET /tech-catalog/<uuid>/"""
        pk = kwargs.get('pk')

        if not _is_redis_backend():
            try:
                entry = self.get_object()
                serializer = TechCatalogSerializer(
                    entry, context=self.get_serializer_context()
                )
                return Response({'success': True, 'data': serializer.data})
            except (TechCatalog.DoesNotExist, Http404):
                return Response(
                    {'success': False, 'error': CoreErrorMessages.OBJECT_NOT_FOUND},
                    status=status.HTTP_404_NOT_FOUND,
                )

        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()

        cache_key = build_drf_cache_key(
            namespace='tech_catalog_detail',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            extra=str(pk),
            tag_namespace=TECH_CATALOG_CACHE_TAG,
        )

        def producer():
            try:
                entry = self.get_object()

                ctx = ctx_from_request(request)
                ctx.update({
                    'target_id': str(entry.id),
                    'event': 'tech_catalog_retrieve',
                })
                logger.info('tech_catalog_retrieve', extra=ctx)

                serializer = TechCatalogSerializer(
                    entry, context=self.get_serializer_context()
                )
                return {'success': True, 'data': serializer.data}

            except (TechCatalog.DoesNotExist, Http404):
                return {
                    'success': False,
                    'error': CoreErrorMessages.OBJECT_NOT_FOUND,
                    'status': 404,
                }

        cached = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, TECH_CATALOG_CACHE_TAG),
        )

        if not cached.get('success'):
            return Response(
                {'success': False, 'error': cached.get('error')},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(cached)

    # =========================================================================
    # CREATE
    # =========================================================================

    def create(self, request, *args, **kwargs):
        """
        POST /tech-catalog/

        Admin-only (enforced by ScopedPermission against the registry).
        No mine-scope auto-assignment — the catalog has no per-row
        owner concept.
        """
        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                entry = serializer.save()

                self._invalidate_caches(str(entry.client_id))

                audit_log(
                    event='tech_catalog_create_success',
                    action='create',
                    actor_id=str(request.user.id),
                    client_id=str(entry.client_id),
                    target_type='tech_catalog',
                    target_id=str(entry.id),
                    outcome='success',
                )

                return Response(
                    {
                        'success': True,
                        'message': (
                            f'Tech catalog entry "{entry.company_name} / '
                            f'{entry.product_name}" created successfully'
                        ),
                        'data': TechCatalogSerializer(
                            entry, context=self.get_serializer_context()
                        ).data,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            return self.handle_exception(e)

    # =========================================================================
    # PARTIAL UPDATE
    # =========================================================================

    def partial_update(self, request, *args, **kwargs):
        """PATCH /tech-catalog/<uuid>/"""
        try:
            with transaction.atomic():
                entry = self.get_object()
                serializer = self.get_serializer(
                    entry, data=request.data, partial=True
                )
                serializer.is_valid(raise_exception=True)
                updated = serializer.save()

                self._invalidate_caches(str(updated.client_id))

                changed_fields = sorted(serializer.validated_data.keys())

                audit_log(
                    event='tech_catalog_update_success',
                    action='partial_update',
                    actor_id=str(request.user.id),
                    client_id=str(updated.client_id),
                    target_type='tech_catalog',
                    target_id=str(entry.id),
                    fields_changed=changed_fields,
                    outcome='success',
                )

                return Response({
                    'success': True,
                    'message': (
                        f'Tech catalog entry "{updated.company_name} / '
                        f'{updated.product_name}" updated successfully'
                    ),
                    'data': TechCatalogSerializer(
                        updated, context=self.get_serializer_context()
                    ).data,
                })

        except (TechCatalog.DoesNotExist, Http404):
            return Response(
                {'success': False, 'error': CoreErrorMessages.OBJECT_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return self.handle_exception(e)

    # =========================================================================
    # DESTROY (hard delete — see model docstring)
    # =========================================================================

    def destroy(self, request, *args, **kwargs):
        """
        DELETE /tech-catalog/<uuid>/

        Hard delete. The catalog has no soft-delete flag on the model
        and the recadrage explicitly opted for hard delete to mirror
        CompanyAccount.

        Downstream M2M relations (DC ↔ TechCatalog, Product ↔
        TechCatalog, Signal ↔ TechCatalog) are out of scope here. When
        they land, their FK on_delete behaviour will determine the
        cascade — typically PROTECT for catalogs already referenced,
        but that's the consumer's call.
        """
        try:
            with transaction.atomic():
                client_id = self.get_client_id()
                pk = kwargs.get('pk')

                entry = (
                    TechCatalog.objects
                    .select_for_update()
                    .filter(id=pk, client_id=client_id)
                    .first()
                )

                if not entry:
                    audit_log(
                        event='tech_catalog_delete_not_found',
                        action='delete',
                        actor_id=str(request.user.id),
                        client_id=str(client_id),
                        target_type='tech_catalog',
                        target_id=str(pk or '-'),
                        outcome='not_found',
                    )
                    return Response(
                        {
                            'success': False,
                            'error': CoreErrorMessages.OBJECT_NOT_FOUND,
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Tenant scope sanity check — the .filter above already
                # enforces it, but validate_client_id() centralizes the
                # error semantic (StandardizedPermissionDenied) for any
                # row reached through other paths.
                self.validate_client_id(entry)

                display = (
                    entry.company_name
                    if entry.company_name == entry.product_name
                    else f'{entry.company_name} / {entry.product_name}'
                )
                entry.delete()

                self._invalidate_caches(str(client_id))

                audit_log(
                    event='tech_catalog_delete_success',
                    action='delete',
                    actor_id=str(request.user.id),
                    client_id=str(client_id),
                    target_type='tech_catalog',
                    target_id=str(pk),
                    outcome='success',
                )

                return Response(
                    {
                        'success': True,
                        'message': f'Tech catalog entry "{display}" deleted successfully',
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            return self.handle_exception(e)