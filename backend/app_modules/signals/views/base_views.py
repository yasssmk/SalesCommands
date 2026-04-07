# app_modules/signals/views/base_views.py
"""
BaseSignalViewSet — shared ViewSet logic for all signal types.

Provides:
  - CRUD with client scoping (ScopedQuerysetMixin)
  - get_serializer_class() routing (list / detail / create / update)
  - perform_create() routed through SignalManager.create()
  - Custom @action endpoints: validate, reject, merge, supersede
  - Cache invalidation on every write
  - Structured logging + SOC 2 audit trail

Concrete ViewSets (QualificationSignalViewSet, TechStackSignalViewSet)
inherit this class and set the four required class attributes:
  queryset, model_label, list_serializer_class, detail_serializer_class,
  create_serializer_class, update_serializer_class.

SignalChoicesView — standalone APIView returning frontend-ready choice lists.
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
from core.error_messages import CoreErrorMessages
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
    QualificationField,
    TechStackField,
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

class BaseSignalViewSet(OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    Abstract base ViewSet for QualificationSignal and TechStackSignal.

    Concrete subclasses MUST define:
      queryset                  — model-specific base queryset
      model_label               — string for logging ('qualification_signal' | 'tech_stack_signal')
      list_serializer_class     — lightweight list serializer
      detail_serializer_class   — full detail serializer
      create_serializer_class   — write serializer for POST
      update_serializer_class   — restricted write serializer for PATCH

    The class does NOT set Meta.abstract — Django's viewset inheritance
    handles polymorphism at class level, not model level.
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

    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = SignalFilter   # default — overridden dynamically below
    search_fields    = ['field_name', 'value']
    ordering_fields  = ['created_at', 'updated_at', 'status', 'confirmation_count', 'last_confirmed_at']
    ordering         = ['-created_at']

    action_policies = {
        'validate':  {'crud': 'update', 'scope': 'client'},
        'reject':    {'crud': 'update', 'scope': 'client'},
        'merge':     {'crud': 'update', 'scope': 'client'},
        'supersede': {'crud': 'create', 'scope': 'client'},
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

        # Apply owner_scope filter (?owner_scope=mine|team|all)
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
                'merged_into',
                'superseded_by',
            )

        return qs
    
    def filter_queryset(self, queryset):
        """
        Bind SignalFilter to the concrete queryset model before django-filters
        performs its model assertion check.

        DjangoFilterBackend.get_filterset_class() reads view.filterset_class
        via getattr() — it never calls view.get_filterset_class(). Setting
        self.filterset_class on the instance here ensures the backend sees
        the correctly-bound FilterSet before the assertion runs.
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
            extra={'field_name': instance.field_name, 'source': instance.source},
        )

        transaction.on_commit(lambda: _invalidate_signal_caches(self.get_client_id()))

        output = self.detail_serializer_class(instance, context={'request': request})
        return Response(
            {'success': True, 'data': output.data},
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        """
        Delegate creation to SignalManager so source → status routing
        and model.save() business rules are always enforced.

        Sets serializer.instance so downstream code can read the result.
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
        """PUT /signals/{id}/ — treated as PATCH (partial always True)."""
        kwargs['partial'] = True
        return self.partial_update(request, *args, **kwargs)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """PATCH /signals/{id}/"""
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

        _invalidate_signal_caches(self.get_client_id())

        output = self.detail_serializer_class(instance, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """DELETE /signals/{id}/"""
        ctx      = ctx_from_request(request)
        instance = self.get_object()
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
        POST /signals/{id}/validate/
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

        _invalidate_signal_caches(self.get_client_id())

        output = self.detail_serializer_class(updated, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @action(detail=True, methods=['post'], url_path='reject')
    @transaction.atomic
    def reject_signal(self, request, pk=None):
        """
        Reject a PENDING signal.
        POST /signals/{id}/reject/
        Body (optional): { "reason": "string" }
        """
        ctx      = ctx_from_request(request)
        instance = self.get_object()
        reason   = request.data.get('reason', None)

        logger.info(f"{self.model_label}_reject_requested", extra={
            **ctx, 'signal_id': str(instance.id),
        })

        updated = SignalManager.reject(signal=instance, user=request.user, reason=reason)

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

        _invalidate_signal_caches(self.get_client_id())

        output = self.detail_serializer_class(updated, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @action(detail=True, methods=['post'], url_path='merge')
    @transaction.atomic
    def merge_signal(self, request, pk=None):
        """
        Merge this signal (source) into a target signal.
        POST /signals/{id}/merge/
        Body: { "target_signal_id": "<uuid>" }

        Guards (enforced by SignalManager):
          - Same concrete type
          - Same field_name
          - Target must be VALIDATED
          - Source must not already be MERGED
        """
        ctx      = ctx_from_request(request)
        instance = self.get_object()

        target_signal_id = request.data.get('target_signal_id')
        if not target_signal_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='target_signal_id')
            )

        # Resolve target within same model & client scope
        try:
            target = self.get_queryset().get(pk=target_signal_id)
        except self.get_queryset().model.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        logger.info(f"{self.model_label}_merge_requested", extra={
            **ctx,
            'source_signal_id': str(instance.id),
            'target_signal_id': str(target.id),
        })

        updated_target = SignalManager.merge(
            source_signal=instance,
            target_signal=target,
            user=request.user,
        )

        audit_log(
            event=f'{self.model_label}_merged',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=str(updated_target.id),
            outcome='success',
            extra={
                'source_signal_id': str(instance.id),
                'confirmations_added': instance.confirmation_count,
            },
        )

        _invalidate_signal_caches(self.get_client_id())

        output = self.detail_serializer_class(updated_target, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @action(detail=True, methods=['post'], url_path='supersede')
    @transaction.atomic
    def supersede_signal(self, request, pk=None):
        """
        Supersede this signal with a replacement carrying new_data.
        POST /signals/{id}/supersede/
        Body: { "new_data": { <same shape as create payload> } }

        new_data is validated through the create serializer before being
        passed to SignalManager.supersede() — same guards as a normal create.
        """
        ctx      = ctx_from_request(request)
        instance = self.get_object()

        new_data_raw = request.data.get('new_data')
        if not new_data_raw:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='new_data')
            )

        # Validate new_data through the create serializer
        create_serializer = self.create_serializer_class(
            data=new_data_raw,
            context=self.get_serializer_context(),
        )
        create_serializer.is_valid(raise_exception=True)

        logger.info(f"{self.model_label}_supersede_requested", extra={
            **ctx, 'signal_id': str(instance.id),
        })

        new_signal = SignalManager.supersede(
            old_signal=instance,
            new_data=create_serializer.validated_data.copy(),
            user=request.user,
        )

        audit_log(
            event=f'{self.model_label}_superseded',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=str(new_signal.id),
            outcome='success',
            extra={
                'old_signal_id': str(instance.id),
                'field_name': new_signal.field_name,
            },
        )

        _invalidate_signal_caches(self.get_client_id())

        output = self.detail_serializer_class(new_signal, context={'request': request})
        return Response(
            {'success': True, 'data': output.data},
            status=status.HTTP_201_CREATED,
        )


# =============================================================================
# CHOICES VIEW
# =============================================================================

class SignalChoicesView(APIView):
    """
    Return frontend-ready choice lists for the Signals module.

    GET /signals/choices/

    Response shape:
    {
      "success": true,
      "data": {
        "status":              [{"value": "PENDING", "label": "Pending"}, ...],
        "source":              [...],
        "signal_category":     [...],
        "qualification_fields":[{"value": "pain_point", "label": "Pain Point"}, ...],
        "tech_stack_fields":   [...]
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
                'status':               _choices(SignalStatus),
                'source':               _choices(SignalSource),
                'signal_category':      _choices(SignalCategory),
                'qualification_fields': _choices(QualificationField),
                'tech_stack_fields':    _choices(TechStackField),
            },
        })