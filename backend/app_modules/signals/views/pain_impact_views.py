# app_modules/signals/views/pain_impact_views.py
"""
PainImpactViewSet — CRUD for PainImpact.

Unlike BaseSignalViewSet, PainImpact has no lifecycle:
  - No PENDING/VALIDATED/REJECTED status
  - No /validate/ or /reject/ actions
  - No source enum, no confidence, no corroboration

A PainImpact is truth-by-association: it is meaningful only while attached
to its parent Pain and lives/dies with it (CASCADE on pain_signal delete).

Endpoints (mounted under /pain-impacts/):
  GET    /pain-impacts/                   → list (filtered by pain_signal, etc.)
  POST   /pain-impacts/                   → create
  GET    /pain-impacts/{id}/              → retrieve
  PATCH  /pain-impacts/{id}/              → partial_update
  PUT    /pain-impacts/{id}/              → update (treated as PATCH)
  DELETE /pain-impacts/{id}/              → destroy

No @action custom endpoints — the simple CRUD surface is enough.
"""

import django_filters
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.cache_utils import invalidate_tag
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ..filters import CharInFilter
from ..models import PainImpact
from ..serializers import (
    PainImpactListSerializer,
    PainImpactDetailSerializer,
    PainImpactCreateSerializer,
    PainImpactUpdateSerializer,
)

from ..constants import SIGNALS_CACHE_TAG, SIGNAL_CLUSTERS_CACHE_TAG

logger = get_logger(__name__)

_SIGNAL_CACHE_TAG = 'signals'


def _invalidate_signal_caches(client_id):
    """
    Invalidate both signal and cluster cache tags after any PainImpact write.

    PainImpact is a PIVOT entity for cluster aggregated stats:
      - human_impacts distribution
      - metrics list
      - impacted_contacts_count
      - max_impact_level

    Every write therefore busts SIGNAL_CLUSTERS_CACHE_TAG in addition
    to SIGNALS_CACHE_TAG. No flag: PainImpact has no ViewSet where
    cluster invalidation would be optional.
    """
    client_id_str = str(client_id)
    invalidate_tag(client_id_str, SIGNALS_CACHE_TAG)
    invalidate_tag(client_id_str, SIGNAL_CLUSTERS_CACHE_TAG)


# =============================================================================
# FILTER
# =============================================================================

class PainImpactFilter(django_filters.FilterSet):
    """
    FilterSet for PainImpact.

    Supports:
      - pain_signal          : UUID — filter impacts of a specific pain
      - level                : list — BUSINESS/DEPARTMENT/PERSONAL
      - human_impact         : list
      - impacted_department  : UUID
      - impacted_contact     : UUID

    Cross-pain queries (e.g. "all PERSONAL impacts on account X") work by
    chaining pain_signal__account on the queryset side; not exposed as
    a direct filter here to keep the API surface minimal.
    """

    pain_signal         = django_filters.UUIDFilter(field_name='pain_signal_id')
    impacted_department = django_filters.UUIDFilter(field_name='impacted_department_id')
    impacted_contact    = django_filters.UUIDFilter(field_name='impacted_contact_id')

    level        = CharInFilter(field_name='level',        lookup_expr='in')
    human_impact = CharInFilter(field_name='human_impact', lookup_expr='in')

    # Account-scope filter via the parent pain.
    # This is useful for AccountSignalsTab → "all impacts on this account"
    # even without knowing individual pain ids.
    account = django_filters.UUIDFilter(field_name='pain_signal__account_id')

    class Meta:
        model = PainImpact
        fields = [
            'pain_signal',
            'level',
            'human_impact',
            'impacted_department',
            'impacted_contact',
            'account',
        ]


# =============================================================================
# VIEWSET
# =============================================================================

class PainImpactViewSet(
    OwnerScopeMixin,
    ScopedQuerysetMixin,
    BaseAPIView,
    viewsets.ModelViewSet,
):
    """
    ViewSet for PainImpact CRUD.

    Auth:
      - JWT-based (CustomJWTAuthentication)
      - Client-scoped via ScopedPermission + ScopedQuerysetMixin
      - Owner-scoped via OwnerScopeMixin (inherits visibility rules from
        the parent PainSignal implicitly — an impact is visible if the
        querying user can see its pain's account)
    """

    queryset = PainImpact.objects.all()

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'signals'
    model_label            = 'pain_impact'

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PainImpactFilter
    search_fields   = ['metric', 'notes']
    ordering_fields = ['created_at', 'updated_at', 'level']
    ordering        = ['-created_at']

    # =========================================================================
    # SERIALIZER ROUTING
    # =========================================================================

    def get_serializer_class(self):
        if self.action == 'list':
            return PainImpactListSerializer
        if self.action in ('update', 'partial_update'):
            return PainImpactUpdateSerializer
        if self.action == 'create':
            return PainImpactCreateSerializer
        return PainImpactDetailSerializer

    # =========================================================================
    # QUERYSET — tuned per action
    # =========================================================================

    def get_queryset(self):
        """
        Client-scoped queryset with select_related optimised per action.

        Lists: keep it lean — parent pain compact ref + dept/contact compact.
        Detail: also fetch audit users for provenance display.
        """
        qs = super().get_queryset()
        qs = self.apply_owner_scope_filter(qs)

        if self.action == 'list':
            qs = qs.select_related(
                'pain_signal',
                'impacted_department',
                'impacted_contact',
            )
        else:
            qs = qs.select_related(
                'pain_signal',
                'impacted_department',
                'impacted_contact',
                'created_by',
                'updated_by',
            )

        return qs

    # =========================================================================
    # CRUD OVERRIDES
    # =========================================================================

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """POST /pain-impacts/ — create a new impact attached to a pain."""
        ctx = ctx_from_request(request)
        logger.info(f"{self.model_label}_create_requested", extra=ctx)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = self.perform_create(serializer)

        audit_log(
            event=f'{self.model_label}_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=str(instance.id),
            outcome='success',
            extra={
                'level': instance.level,
                'pain_signal_id': str(instance.pain_signal_id),
            },
        )

        transaction.on_commit(
            lambda: _invalidate_signal_caches(self.get_client_id())
        )

        # Re-serialize through Detail to return the full payload
        output = PainImpactDetailSerializer(instance, context={'request': request})
        return Response(
            {'success': True, 'data': output.data},
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        """
        Save with the client scope injected — no SignalManager routing
        (no lifecycle) and no `user=` kwarg (PainImpact has no ownership
        field; audit fields `created_by` / `updated_by` are populated by
        ModuleBaseModel from the request context).
        """
        client_id = self.get_client_id()
        instance = serializer.save(client_id=client_id)
        return instance

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """PUT /pain-impacts/{id}/ — treated as PATCH."""
        kwargs['partial'] = True
        return self.partial_update(request, *args, **kwargs)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """PATCH /pain-impacts/{id}/"""
        ctx      = ctx_from_request(request)
        instance = self.get_object()

        logger.info(f"{self.model_label}_update_requested", extra={
            **ctx, 'impact_id': str(instance.id),
        })

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # No `user=` kwarg — PainImpact has no ownership field. The updated_by
        # audit field is populated by ModuleBaseModel from the request context.
        serializer.save()

        audit_log(
            event=f'{self.model_label}_update_success',
            action='partial_update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=str(instance.id),
            fields_changed=list(serializer.validated_data.keys()),
            outcome='success',
        )

        transaction.on_commit(
            lambda: _invalidate_signal_caches(self.get_client_id())
        )

        output = PainImpactDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """DELETE /pain-impacts/{id}/"""
        ctx       = ctx_from_request(request)
        instance  = self.get_object()
        impact_id = str(instance.id)
        pain_id   = str(instance.pain_signal_id)

        logger.info(f"{self.model_label}_delete_requested", extra={
            **ctx, 'impact_id': impact_id, 'pain_signal_id': pain_id,
        })

        instance.delete()

        audit_log(
            event=f'{self.model_label}_delete_success',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=impact_id,
            outcome='success',
            extra={'pain_signal_id': pain_id},
        )

        _invalidate_signal_caches(self.get_client_id())

        return Response(
            {'success': True, 'data': None},
            status=status.HTTP_204_NO_CONTENT,
        )