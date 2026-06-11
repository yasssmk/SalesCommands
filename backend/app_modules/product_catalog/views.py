# app_modules/product_catalog/views.py
"""
ViewSet for the ProductCatalog module.

Five standard REST endpoints — list, retrieve, create, partial_update,
destroy — mirroring the TechCatalog pattern.

Permission model:
    All writes (create/update/delete) are admin-only, enforced by
    ScopedPermission against permissions/registry/product_catalog_registry.py.
    Reads are open to admin/manager/individual within the tenant.
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

from app_modules.product_catalog.constants import PRODUCT_CATALOG_CACHE_TAG
from app_modules.product_catalog.models import ProductCatalog
from app_modules.product_catalog.serializers import (
    ProductCatalogCreateSerializer,
    ProductCatalogListSerializer,
    ProductCatalogSerializer,
    ProductCatalogUpdateSerializer,
)


logger = get_logger(__name__)


class ProductCatalogViewSet(
    OwnerScopeMixin,
    ScopedQuerysetMixin,
    BaseAPIView,
    viewsets.ModelViewSet,
):
    """
    REST endpoints for tenant-level ProductCatalog entries.
    """

    queryset = ProductCatalog.objects.all()
    serializer_class = ProductCatalogSerializer
    entity_name = 'product_catalog'

    # -------------------------------------------------------------------------
    # Filtering / search / ordering
    # -------------------------------------------------------------------------

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_class = None

    search_fields = ['name']

    ordering_fields = [
        'name',
        'default_unit_price',
        'created_at',
        'updated_at',
    ]
    ordering = ['name']

    # -------------------------------------------------------------------------
    # Auth & permission scope
    # -------------------------------------------------------------------------

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'product_catalog'

    # =========================================================================
    # SERIALIZER ROUTING
    # =========================================================================

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductCatalogListSerializer
        if self.action == 'create':
            return ProductCatalogCreateSerializer
        if self.action in ('update', 'partial_update'):
            return ProductCatalogUpdateSerializer
        return ProductCatalogSerializer

    # =========================================================================
    # QUERYSET
    # =========================================================================

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_owner_scope_filter(queryset)

        if self.action in ('retrieve', 'update', 'partial_update'):
            queryset = queryset.select_related('created_by', 'updated_by')

        return queryset

    # =========================================================================
    # CACHE HELPERS
    # =========================================================================

    def _invalidate_caches(self, client_id):
        invalidate_tag(client_id, PRODUCT_CATALOG_CACHE_TAG)

    # =========================================================================
    # LIST / RETRIEVE
    # =========================================================================

    def list(self, request, *args, **kwargs):
        if not _is_redis_backend():
            response = super().list(request, *args, **kwargs)
            return Response({'success': True, 'data': response.data})

        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()
        query_string = request.META.get('QUERY_STRING', '')

        cache_key = build_drf_cache_key(
            namespace='product_catalog_list',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            query_string=query_string,
            tag_namespace=PRODUCT_CATALOG_CACHE_TAG,
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
            tag=(client_id, PRODUCT_CATALOG_CACHE_TAG),
        )

        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'product_catalog_list',
            'result_count': (
                cached.get('data', {}).get('count', '-')
                if isinstance(cached.get('data'), dict)
                else '-'
            ),
        })
        logger.info('product_catalog_list', extra=ctx)

        return Response(cached)

    def retrieve(self, request, *args, **kwargs):
        pk = kwargs.get('pk')

        if not _is_redis_backend():
            try:
                entry = self.get_object()
                serializer = ProductCatalogSerializer(
                    entry, context=self.get_serializer_context()
                )
                return Response({'success': True, 'data': serializer.data})
            except (ProductCatalog.DoesNotExist, Http404):
                return Response(
                    {'success': False, 'error': CoreErrorMessages.OBJECT_NOT_FOUND},
                    status=status.HTTP_404_NOT_FOUND,
                )

        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()

        cache_key = build_drf_cache_key(
            namespace='product_catalog_detail',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            extra=str(pk),
            tag_namespace=PRODUCT_CATALOG_CACHE_TAG,
        )

        def producer():
            try:
                entry = self.get_object()

                ctx = ctx_from_request(request)
                ctx.update({
                    'target_id': str(entry.id),
                    'event': 'product_catalog_retrieve',
                })
                logger.info('product_catalog_retrieve', extra=ctx)

                serializer = ProductCatalogSerializer(
                    entry, context=self.get_serializer_context()
                )
                return {'success': True, 'data': serializer.data}

            except (ProductCatalog.DoesNotExist, Http404):
                return {
                    'success': False,
                    'error': CoreErrorMessages.OBJECT_NOT_FOUND,
                    'status': 404,
                }

        cached = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, PRODUCT_CATALOG_CACHE_TAG),
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
        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                entry = serializer.save()

                self._invalidate_caches(str(entry.client_id))

                audit_log(
                    event='product_catalog_create_success',
                    action='create',
                    actor_id=str(request.user.id),
                    client_id=str(entry.client_id),
                    target_type='product_catalog',
                    target_id=str(entry.id),
                    outcome='success',
                )

                return Response(
                    {
                        'success': True,
                        'message': (
                            f'Product catalog entry "{entry.name}" '
                            f'created successfully'
                        ),
                        'data': ProductCatalogSerializer(
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
                    event='product_catalog_update_success',
                    action='partial_update',
                    actor_id=str(request.user.id),
                    client_id=str(updated.client_id),
                    target_type='product_catalog',
                    target_id=str(entry.id),
                    fields_changed=changed_fields,
                    outcome='success',
                )

                return Response({
                    'success': True,
                    'message': (
                        f'Product catalog entry "{updated.name}" '
                        f'updated successfully'
                    ),
                    'data': ProductCatalogSerializer(
                        updated, context=self.get_serializer_context()
                    ).data,
                })

        except (ProductCatalog.DoesNotExist, Http404):
            return Response(
                {'success': False, 'error': CoreErrorMessages.OBJECT_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return self.handle_exception(e)

    # =========================================================================
    # DESTROY
    # =========================================================================

    def destroy(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                client_id = self.get_client_id()
                pk = kwargs.get('pk')

                entry = (
                    ProductCatalog.objects
                    .select_for_update()
                    .filter(id=pk, client_id=client_id)
                    .first()
                )

                if not entry:
                    audit_log(
                        event='product_catalog_delete_not_found',
                        action='delete',
                        actor_id=str(request.user.id),
                        client_id=str(client_id),
                        target_type='product_catalog',
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

                self.validate_client_id(entry)

                display = entry.name
                entry.delete()

                self._invalidate_caches(str(client_id))

                audit_log(
                    event='product_catalog_delete_success',
                    action='delete',
                    actor_id=str(request.user.id),
                    client_id=str(client_id),
                    target_type='product_catalog',
                    target_id=str(pk),
                    outcome='success',
                )

                return Response(
                    {
                        'success': True,
                        'message': f'Product catalog entry "{display}" deleted successfully',
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            return self.handle_exception(e)
