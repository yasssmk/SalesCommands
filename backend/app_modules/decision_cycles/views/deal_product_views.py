# app_modules/decision_cycles/views/deal_product_views.py
"""
DealProductViewSet — CRUD for DealProduct sub-resources of a DecisionCycle.

Security model:
    Access to products is governed by the parent cycle. The ViewSet does NOT
    use ScopedQuerysetMixin or OwnerScopeMixin (DealProduct has no owner
    field). Instead, _resolve_parent_cycle() reuses DecisionCycleViewSet's
    fully scoped queryset to verify the user can access the parent cycle.

    - Reads:  require read access to the parent cycle (scope: client).
    - Writes: require update access to the parent cycle (scope: mine/team/client
              depending on tier — mirrors DecisionCycleViewSet permissions).
"""

from django.db import transaction
from django.http import Http404

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import ctx_from_request, get_logger
from core.logging.audit import audit_log
from core.cache_utils import invalidate_tag

from permissions.mixins import ScopedPermission

from ..models import DecisionCycle, DealProduct
from ..serializers import (
    DealProductListSerializer,
    DealProductCreateSerializer,
    DealProductUpdateSerializer,
)


logger = get_logger(__name__)


class CycleScopedMixin:
    """
    Resolves and permission-checks the parent DecisionCycle from URL kwargs.

    Reuses DecisionCycleViewSet's scoped queryset so the same ownership
    rules (client/team/mine) are applied to the parent cycle. No hand-written
    Q-objects — the entire scope chain (client filtering + registry scope +
    ownership) is delegated to DecisionCycleViewSet.get_queryset().
    """

    def _resolve_parent_cycle(self):
        if hasattr(self, '_parent_cycle'):
            return self._parent_cycle

        from .views import DecisionCycleViewSet

        cycle_id = self.kwargs.get('cycle_id')

        action_policy = self.action_policies.get(self.action, {})
        crud = action_policy.get('crud', 'read')
        cycle_action = 'list' if crud == 'read' else 'partial_update'

        cycle_vs = DecisionCycleViewSet()
        cycle_vs.request = self.request
        cycle_vs.kwargs = {}
        cycle_vs.action = cycle_action
        cycle_vs.format_kwarg = None

        try:
            cycle = cycle_vs.get_queryset().get(id=cycle_id)
        except DecisionCycle.DoesNotExist:
            raise Http404

        self._parent_cycle = cycle
        return cycle


class DealProductViewSet(CycleScopedMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    CRUD endpoints for DealProduct, nested under a DecisionCycle.

    Endpoints (mounted under /decision-cycles/{cycle_id}/products/):
      GET    /                → list
      POST   /                → create
      GET    /{pk}/           → retrieve
      PATCH  /{pk}/           → partial_update
      DELETE /{pk}/           → destroy
      PUT    /{pk}/           → update (treated as PATCH)
    """

    queryset = DealProduct.objects.all()
    entity_name = 'deal_product'

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'decision_cycles'

    action_policies = {
        'list':           {'crud': 'read',   'scope': 'client'},
        'retrieve':       {'crud': 'read',   'scope': 'client'},
        'create':         {'crud': 'create', 'scope': 'mine'},
        'partial_update': {'crud': 'update', 'scope': 'mine'},
        'update':         {'crud': 'update', 'scope': 'mine'},
        'destroy':        {'crud': 'delete', 'scope': 'mine'},
    }

    # =========================================================================
    # SERIALIZER ROUTING
    # =========================================================================

    def get_serializer_class(self):
        if self.action == 'create':
            return DealProductCreateSerializer
        if self.action in ('update', 'partial_update'):
            return DealProductUpdateSerializer
        return DealProductListSerializer

    # =========================================================================
    # QUERYSET — scoped to parent cycle
    # =========================================================================

    def get_queryset(self):
        cycle = self._resolve_parent_cycle()
        return DealProduct.objects.filter(
            decision_cycle=cycle,
            client_id=cycle.client_id,
        ).select_related('product_catalog_entry')

    # =========================================================================
    # SERIALIZER CONTEXT — injects decision_cycle for create serializer
    # =========================================================================

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['decision_cycle'] = self._resolve_parent_cycle()
        return ctx

    # =========================================================================
    # CACHE HELPERS
    # =========================================================================

    def _invalidate_caches(self, client_id):
        invalidate_tag(str(client_id), 'decision_cycles')

    # =========================================================================
    # CRUD
    # =========================================================================

    def list(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        cycle = self._resolve_parent_cycle()

        logger.info('deal_product_list_requested', extra={
            **ctx, 'cycle_id': str(cycle.id),
        })

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info('deal_product_retrieved', extra={
            **ctx, 'product_id': str(instance.id),
        })

        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        cycle = self._resolve_parent_cycle()

        logger.info('deal_product_create_requested', extra={
            **ctx, 'cycle_id': str(cycle.id),
        })

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='deal_product_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(cycle.client_id),
            target_type='deal_product',
            target_id=str(instance.id),
            outcome='success',
        )

        transaction.on_commit(
            lambda: self._invalidate_caches(cycle.client_id)
        )

        output = DealProductListSerializer(instance, context=self.get_serializer_context())
        return Response(
            {'success': True, 'data': output.data},
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.partial_update(request, *args, **kwargs)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info('deal_product_update_requested', extra={
            **ctx, 'product_id': str(instance.id),
        })

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        audit_log(
            event='deal_product_update_success',
            action='partial_update',
            actor_id=str(request.user.id),
            client_id=str(updated.client_id),
            target_type='deal_product',
            target_id=str(instance.id),
            fields_changed=list(serializer.validated_data.keys()),
            outcome='success',
        )

        transaction.on_commit(
            lambda: self._invalidate_caches(updated.client_id)
        )

        output = DealProductListSerializer(updated, context=self.get_serializer_context())
        return Response({'success': True, 'data': output.data})

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        instance = self.get_object()
        product_id = str(instance.id)
        client_id = instance.client_id

        logger.info('deal_product_delete_requested', extra={
            **ctx, 'product_id': product_id,
        })

        instance.delete()

        audit_log(
            event='deal_product_delete_success',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='deal_product',
            target_id=product_id,
            outcome='success',
        )

        self._invalidate_caches(client_id)

        return Response(
            {'success': True, 'data': None},
            status=status.HTTP_204_NO_CONTENT,
        )
