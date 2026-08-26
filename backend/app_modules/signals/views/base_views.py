# app_modules/signals/views/base_views.py
"""
BaseSignalViewSet — shared ViewSet logic for all signal types.

Provides:
  - CRUD with client scoping (ScopedQuerysetMixin)
  - get_serializer_class() routing (list / detail / create / update)
  - perform_create() routed through SignalManager.create()
  - Custom @action endpoints: validate, reject
  - Cache invalidation on every write
  - Structured logging + SOC 2 audit trail

Concrete ViewSets inherit this class and set the four required attributes:
  queryset, model_label, list_serializer_class, detail_serializer_class,
  create_serializer_class, update_serializer_class.

SignalChoicesView — standalone APIView returning frontend-ready choice lists
for all 4 signal types.
"""

from django.db import transaction
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from core.apps_shared_methods import BaseAPIView
from core.cache_utils import invalidate_tag
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

from ..constants import SIGNALS_CACHE_TAG, SIGNAL_CLUSTERS_CACHE_TAG

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ..constants import (
    SignalStatus,
    SignalSource,
    SignalCategory,
    SignalWhat,
    SignalDimension,
    ScopeLevel,
    UsageScope,
)

from ..filters import SignalFilter
from ..services import SignalManager

logger = get_logger(__name__)


def _invalidate_signal_caches(client_id, *, invalidate_cluster_tag: bool = False):
    """
    Invalidate signal cache tags after any write operation.

    Args:
        client_id: Client UUID used for tenant-scoped cache keys.
        invalidate_cluster_tag:
            When True, also invalidate SIGNAL_CLUSTERS_CACHE_TAG. Set
            to True for ViewSets whose writes affect cluster membership
            or aggregated cluster stats (PainSignalViewSet). Default
            False for People / Objective / TechStack ViewSets whose
            writes do not touch cluster data.
    """
    client_id_str = str(client_id)
    invalidate_tag(client_id_str, SIGNALS_CACHE_TAG)
    if invalidate_cluster_tag:
        invalidate_tag(client_id_str, SIGNAL_CLUSTERS_CACHE_TAG)

# =============================================================================
# BASE VIEWSET
# =============================================================================

class BaseSignalViewSet(
    OwnerScopeMixin,
    ScopedQuerysetMixin,
    BaseAPIView,
    viewsets.ModelViewSet,
):
    """
    Base ViewSet for all concrete signal types.
    ...
    """

    # --- to be overridden by concrete ViewSets ---
    list_serializer_class   = None
    detail_serializer_class = None
    create_serializer_class = None
    update_serializer_class = None
    model_label             = 'signal'

    # Cluster cache invalidation flag.
    #
    # When True, every write performed by this ViewSet also invalidates
    # SIGNAL_CLUSTERS_CACHE_TAG in addition to SIGNALS_CACHE_TAG.
    #
    # Must be set to True on concrete ViewSets whose writes affect
    # cluster data:
    #   - PainSignalViewSet  (cluster membership, priority_score,
    #                         freshness_status, confirmation_count)
    #
    # Kept False for signal types that do not participate in the
    # cluster model (People / Objective / TechStack).
    invalidate_cluster_tag = False

    # --- shared config ---
    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'signals'

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SignalFilter
    search_fields   = []
    ordering_fields = ['created_at', 'updated_at', 'status']
    ordering        = ['-created_at']

    action_policies = {
        'validate': {'crud': 'update', 'scope': 'client'},
        'reject':   {'crud': 'update', 'scope': 'client'},
    }

    # =========================================================================
    # SERIALIZER ROUTING
    # =========================================================================

    def get_serializer_class(self):
        if self.action == 'list':
            return self.list_serializer_class
        if self.action in ('update', 'partial_update'):
            return self.update_serializer_class
        if self.action == 'create':
            return self.create_serializer_class
        return self.detail_serializer_class

    # =========================================================================
    # QUERYSET — optimised per action
    # =========================================================================

    def get_queryset(self):
        """
        Client-scoped queryset with select_related and prefetch_related
        tuned per action.

        Per-type select_related strategy
        --------------------------------
        Each concrete signal model carries its own narrow surface of
        FKs. The base queryset preloads only FKs that exist on EVERY
        concrete signal model (account, source_activity, audit users
        on detail). Concrete ViewSets add their type-specific
        select_related on top via super().get_queryset() chaining:

          PainSignalViewSet      → decision_cycle, campaign,
                                    related_techstack_mention
          ObjectiveSignalViewSet → decision_cycle, campaign,
                                    target_contact, target_department
          TechStackSignalViewSet → usage_department
                                    (decision_cycle and campaign are
                                     shadow-overridden to None on the
                                     model — derived via source_activity
                                     fallback in SignalSourceSerializer)

        This mirrors the per-type strategy already used by
        SignalDataService._RELATED_BY_TYPE (see signal_data_service.py).

        Standardised provenance prefetch
        --------------------------------
        Both list and detail actions prefetch
        `source_activity__contacts__standard_department` because the
        standardised `source_context` block exposed by
        BaseSignalListSerializer / BaseSignalDetailSerializer (introduced
        by the standardisation refactor) reads activity.contacts — and
        each contact's standard_department — to derive the
        participating-contacts list. Without this prefetch, every
        rendered signal (and every contact on it) would issue an extra
        query, yielding O(N) DB roundtrips on list responses.
        """
        qs = super().get_queryset()
        qs = self.apply_owner_scope_filter(qs)

        # Data-quality gate: never surface a signal whose `what` (domain) fell
        # outside the controlled SignalWhat vocabulary. Such rows are persisted
        # flagged (is_domain_valid=False) for traceability/reprocessing but must
        # not appear in any list, detail, count or lifecycle action. Applied to
        # every action so an excluded row is unreachable through the API — the
        # aggregated list reuses this queryset, so it inherits the exclusion.
        qs = qs.filter(is_domain_valid=True)

        if self.action == 'list':
            # Universal FKs only — concrete ViewSets add type-specific
            # select_related on top via super().get_queryset() chaining.
            qs = qs.select_related(
                'account',
                'source_activity',
            ).prefetch_related(
                # The standardised `source_context` block exposed by
                # BaseSignalListSerializer reads source_activity.contacts
                # (m2m) and each contact's standard_department. Prefetch
                # both levels to keep the list at a bounded query count
                # regardless of result size.
                'source_activity__contacts__standard_department',
            )
        else:
            qs = qs.select_related(
                'account',
                'source_activity',
                'validated_by',
                'requested_by',
            ).prefetch_related(
                # source_activity exposes its linked contacts (and each
                # contact's standard_department) through the enriched
                # compact serializer and the standardised `source_context`
                # block — prefetch both levels to keep detail reads at a
                # bounded number of queries.
                'source_activity__contacts__standard_department',
            )

        return qs

    def filter_queryset(self, queryset):
        """
        Bind SignalFilter to the concrete queryset model before django-filters
        performs its model assertion check.

        DjangoFilterBackend reads view.filterset_class via getattr() — setting
        self.filterset_class on the instance here ensures the backend sees the
        correctly-bound FilterSet before the assertion runs.
        """
        model = queryset.model
        if SignalFilter.Meta.model is not model:
            bound_meta = type('Meta', (SignalFilter.Meta,), {'model': model})
            self.filterset_class = type(
                f'{model.__name__}Filter', (SignalFilter,), {'Meta': bound_meta}
            )
        else:
            self.filterset_class = SignalFilter
        return super().filter_queryset(queryset)

    # =========================================================================
    # CRUD OVERRIDES
    # =========================================================================

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new signal.
        POST /<signal-type>/
        Routes through SignalManager.create() for source → status logic.
        """
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
            extra={'source': instance.source},
        )

        transaction.on_commit(
            lambda: _invalidate_signal_caches(
                self.get_client_id(),
                invalidate_cluster_tag=self.invalidate_cluster_tag,
            )
        )

        output = self.detail_serializer_class(instance, context={'request': request})
        return Response(
            {'success': True, 'data': output.data},
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        """
        Delegate creation to SignalManager so source → status routing
        and model.save() business rules are always enforced.
        """
        data      = serializer.validated_data.copy()
        client_id = self.get_client_id()

        instance = SignalManager.create(
            data=data,
            user=self.request.user,
            client_id=client_id,
        )
        serializer.instance = instance
        return instance

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """PUT /<signal-type>/{id}/ — treated as PATCH."""
        kwargs['partial'] = True
        return self.partial_update(request, *args, **kwargs)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """PATCH /<signal-type>/{id}/"""
        ctx      = ctx_from_request(request)
        instance = self.get_object()

        logger.info(f"{self.model_label}_update_requested", extra={
            **ctx, 'signal_id': str(instance.id),
        })

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
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
            lambda: _invalidate_signal_caches(
                self.get_client_id(),
                invalidate_cluster_tag=self.invalidate_cluster_tag,
            )
        )

        output = self.detail_serializer_class(instance, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """DELETE /<signal-type>/{id}/"""
        ctx       = ctx_from_request(request)
        instance  = self.get_object()
        signal_id = str(instance.id)

        logger.info(f"{self.model_label}_delete_requested", extra={
            **ctx, 'signal_id': signal_id,
        })

        instance.delete()

        audit_log(
            event=f'{self.model_label}_delete_success',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=signal_id,
            outcome='success',
        )

        _invalidate_signal_caches(
            self.get_client_id(),
            invalidate_cluster_tag=self.invalidate_cluster_tag,
        )

        return Response(
            {'success': True, 'data': None},
            status=status.HTTP_204_NO_CONTENT,
        )

    # =========================================================================
    # CUSTOM ACTIONS
    # =========================================================================

    @action(detail=True, methods=['post'], url_path='validate')
    @transaction.atomic
    def validate_signal(self, request, pk=None):
        """
        Validate (approve) a PENDING signal.
        POST /<signal-type>/{id}/validate/
        """
        ctx      = ctx_from_request(request)
        instance = self.get_object()

        logger.info(f"{self.model_label}_validate_requested", extra={
            **ctx, 'signal_id': str(instance.id),
        })

        updated = SignalManager.validate(signal=instance, user=request.user)

        audit_log(
            event=f'{self.model_label}_validated',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=str(updated.id),
            fields_changed=['status', 'validated_by', 'validated_at'],
            outcome='success',
        )

        transaction.on_commit(
            lambda: _invalidate_signal_caches(
                self.get_client_id(),
                invalidate_cluster_tag=self.invalidate_cluster_tag,
            )
        )

        output = self.detail_serializer_class(updated, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @action(detail=True, methods=['post'], url_path='reject')
    @transaction.atomic
    def reject_signal(self, request, pk=None):
        """
        Reject a PENDING signal.
        POST /<signal-type>/{id}/reject/
        Body (optional): { "reason": "string" }
        """
        ctx      = ctx_from_request(request)
        instance = self.get_object()
        reason   = request.data.get('reason', None)

        logger.info(f"{self.model_label}_reject_requested", extra={
            **ctx, 'signal_id': str(instance.id),
        })

        updated = SignalManager.reject(
            signal=instance,
            user=request.user,
            reason=reason,
        )

        audit_log(
            event=f'{self.model_label}_rejected',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=str(updated.id),
            fields_changed=['status'],
            outcome='success',
            extra={'reason': reason},
        )

        transaction.on_commit(
            lambda: _invalidate_signal_caches(
                self.get_client_id(),
                invalidate_cluster_tag=self.invalidate_cluster_tag,
            )
        )

        output = self.detail_serializer_class(updated, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @action(detail=True, methods=['post'], url_path='reopen')
    @transaction.atomic
    def reopen_signal(self, request, pk=None):
        """
        Reopen a VALIDATED or REJECTED signal back to PENDING.
        POST /<signal-type>/{id}/reopen/
        """
        ctx      = ctx_from_request(request)
        instance = self.get_object()

        logger.info(f"{self.model_label}_reopen_requested", extra={
            **ctx, 'signal_id': str(instance.id),
        })

        updated = SignalManager.reopen(signal=instance, user=request.user)

        audit_log(
            event=f'{self.model_label}_reopened',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=str(updated.id),
            fields_changed=['status', 'validated_by', 'validated_at'],
            outcome='success',
        )

        transaction.on_commit(
            lambda: _invalidate_signal_caches(
                self.get_client_id(),
                invalidate_cluster_tag=self.invalidate_cluster_tag,
            )
        )

        output = self.detail_serializer_class(updated, context={'request': request})
        return Response({'success': True, 'data': output.data})


# =============================================================================
# CHOICES VIEW
# =============================================================================

class SignalChoicesView(APIView):
    """
    Return frontend-ready choice lists for all signal types.

    GET /signals/choices/

    Response shape:
    {
      "success": true,
      "data": {
        "status":            [...],
        "source":            [...],
        "signal_category":   [...],
        "signal_whats":      [...],   # shared across Pain, Objective and Impact
        "signal_dimensions": [...],   # shared across Pain, Objective and Impact
        "human_impacts":     [...],
        "scope_levels":      [...],   # Pain, Objective and Impact scope axis
        "usage_scopes":      [...],   # TechStackSignal usage scope axis
      }
    }

    Notes:
      - scope_levels drives the PainSignal / ObjectiveSignal / ImpactSignal
        scope_level (BUSINESS / DEPARTMENT / PERSONAL) — see those models'
        docstrings.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated]

    def get(self, request):
        def _choices(enum_cls):
            return [{'value': v, 'label': l} for v, l in enum_cls.choices]

        return Response({
            'success': True,
            'data': {
                'status':            _choices(SignalStatus),
                'source':            _choices(SignalSource),
                'signal_category':   _choices(SignalCategory),
                'signal_whats':      _choices(SignalWhat),
                'signal_dimensions': _choices(SignalDimension),
                'scope_levels':      _choices(ScopeLevel),
                'usage_scopes':      _choices(UsageScope),
            },
        })