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
from core.exceptions import StandardizedValidationError
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ..constants import (
    SignalStatus,
    SignalSource,
    SignalCategory,
    PeopleRole,
    InfluenceLevel,
    PainCategory,
    PainLevel,
    GoalLevel,
    TechCategory,
    Satisfaction,
)
from ..filters import SignalFilter
from ..services import SignalManager

logger = get_logger(__name__)

_SIGNAL_CACHE_TAG = 'signals'


def _invalidate_signal_caches(client_id):
    """Invalidate signal cache tag after any write operation."""
    invalidate_tag(str(client_id), _SIGNAL_CACHE_TAG)


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

    Concrete subclasses MUST define:
      queryset                  — model-specific base queryset
      model_label               — string for logging (e.g. 'people_signal')
      list_serializer_class     — lightweight list serializer
      detail_serializer_class   — full detail serializer
      create_serializer_class   — write serializer for POST
      update_serializer_class   — restricted write serializer for PATCH
    """

    # --- to be overridden by concrete ViewSets ---
    list_serializer_class   = None
    detail_serializer_class = None
    create_serializer_class = None
    update_serializer_class = None
    model_label             = 'signal'

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
        """Client-scoped queryset with select_related tuned per action."""
        qs = super().get_queryset()
        qs = self.apply_owner_scope_filter(qs)

        if self.action == 'list':
            qs = qs.select_related(
                'source_contact',
                'source_department',
            )
        else:
            qs = qs.select_related(
                'account',
                'source_activity',
                'source_contact',
                'source_department',
                'decision_cycle',
                'campaign',
                'validated_by',
                'last_modified_by',
                'requested_by',
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
            lambda: _invalidate_signal_caches(self.get_client_id())
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
            lambda: _invalidate_signal_caches(self.get_client_id())
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

        _invalidate_signal_caches(self.get_client_id())

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
            lambda: _invalidate_signal_caches(self.get_client_id())
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
            lambda: _invalidate_signal_caches(self.get_client_id())
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
        "status":           [...],
        "source":           [...],
        "signal_category":  [...],
        "people_roles":     [...],
        "influence_levels": [...],
        "pain_categories":  [...],
        "pain_levels":      [...],
        "goal_levels":      [...],
        "tech_categories":  [...],
        "satisfaction":     [...],
      }
    }
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated]

    def get(self, request):
        def _choices(enum_cls):
            return [{'value': v, 'label': l} for v, l in enum_cls.choices]

        return Response({
            'success': True,
            'data': {
                'status':           _choices(SignalStatus),
                'source':           _choices(SignalSource),
                'signal_category':  _choices(SignalCategory),
                'people_roles':     _choices(PeopleRole),
                'influence_levels': _choices(InfluenceLevel),
                'pain_categories':  _choices(PainCategory),
                'pain_levels':      _choices(PainLevel),
                'goal_levels':      _choices(GoalLevel),
                'tech_categories':  _choices(TechCategory),
                'satisfaction':     _choices(Satisfaction),
            },
        })