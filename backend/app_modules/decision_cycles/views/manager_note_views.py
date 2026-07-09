# app_modules/decision_cycles/views/manager_note_views.py
"""
ManagerNoteViewSet — CRUD for ManagerNote sub-resources of a DecisionCycle.

Security model:
    - create: manager / admin only (ScopedPermission via registry)
    - list / retrieve: manager / admin + cycle owner
    - delete: note author or admin only (checked in destroy())
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
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

from permissions.mixins import ScopedPermission
from permissions.compat import get_auth_ctx

from app_modules.notifications.models import NotificationCategory
from app_modules.notifications.services import NotificationService

from ..models import DecisionCycle, ManagerNote
from ..serializers import (
    ManagerNoteListSerializer,
    ManagerNoteCreateSerializer,
)
from .deal_product_views import CycleScopedMixin


logger = get_logger(__name__)


class ManagerNoteViewSet(CycleScopedMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    CRUD endpoints for ManagerNote, nested under a DecisionCycle.

    Endpoints (mounted under /decision-cycles/{cycle_id}/notes/):
      GET    /                → list
      POST   /                → create
      GET    /{pk}/           → retrieve
      DELETE /{pk}/           → destroy
    """

    queryset = ManagerNote.objects.all()
    entity_name = 'manager_note'

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'decision_cycles'

    action_policies = {
        'list':     {'crud': 'read',   'scope': 'client'},
        'retrieve': {'crud': 'read',   'scope': 'client'},
        'create':   {'crud': 'create', 'scope': 'mine'},
        'destroy':  {'crud': 'delete', 'scope': 'mine'},
    }

    # =========================================================================
    # CYCLE RESOLUTION — tenant-scoped override
    # =========================================================================
    # CycleScopedMixin delegates to DecisionCycleViewSet.get_queryset() which
    # applies ownership scope (team/mine) for write actions. That is correct
    # for DealProduct (owner-driven edits) but too restrictive for manager
    # notes: a manager must coach ANY cycle in the tenant, not just their
    # team's. We override to do a simple tenant-scoped lookup; the role gate
    # in each CRUD method provides the real access control.
    # =========================================================================

    def _resolve_parent_cycle(self):
        if hasattr(self, '_parent_cycle'):
            return self._parent_cycle

        cycle_id = self.kwargs.get('cycle_id')
        ctx = get_auth_ctx(self.request)
        client_id = ctx.client_id

        try:
            cycle = DecisionCycle.objects.get(id=cycle_id, client_id=client_id)
        except DecisionCycle.DoesNotExist:
            raise Http404

        self._parent_cycle = cycle
        return cycle

    # =========================================================================
    # SERIALIZER ROUTING
    # =========================================================================

    def get_serializer_class(self):
        if self.action == 'create':
            return ManagerNoteCreateSerializer
        return ManagerNoteListSerializer

    # =========================================================================
    # QUERYSET — scoped to parent cycle
    # =========================================================================

    def get_queryset(self):
        cycle = self._resolve_parent_cycle()
        return ManagerNote.objects.filter(
            decision_cycle=cycle,
            client_id=cycle.client_id,
        ).select_related('created_by')

    # =========================================================================
    # SERIALIZER CONTEXT — injects decision_cycle for create serializer
    # =========================================================================

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['decision_cycle'] = self._resolve_parent_cycle()
        return ctx

    # =========================================================================
    # PERMISSION HELPERS
    # =========================================================================

    def _get_effective_tier(self, request):
        """Resolve effective tier from JWT role flags (same logic as checks.py)."""
        ctx = get_auth_ctx(request)
        has_admin = ctx.is_superuser
        has_manager = False
        for role in ctx.roles:
            if isinstance(role, dict):
                if role.get('is_admin'):
                    has_admin = True
                if role.get('is_manager'):
                    has_manager = True
        if has_admin:
            return 'admin'
        if has_manager:
            return 'manager'
        return 'individual'

    def _is_manager_or_admin(self, request):
        return self._get_effective_tier(request) in ('admin', 'manager')

    def _is_admin(self, request):
        return self._get_effective_tier(request) == 'admin'

    def _is_cycle_owner(self, user):
        cycle = self._resolve_parent_cycle()
        return cycle.owner_id and str(cycle.owner_id) == str(user.id)

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

        if not self._is_manager_or_admin(request) and not self._is_cycle_owner(request.user):
            return Response(
                {'success': False, 'error': str(CoreErrorMessages.PERMISSION_DENIED)},
                status=status.HTTP_403_FORBIDDEN,
            )

        logger.info('manager_note_list_requested', extra={
            **ctx, 'cycle_id': str(cycle.id),
        })

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)

        if not self._is_manager_or_admin(request) and not self._is_cycle_owner(request.user):
            return Response(
                {'success': False, 'error': str(CoreErrorMessages.PERMISSION_DENIED)},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance = self.get_object()

        logger.info('manager_note_retrieved', extra={
            **ctx, 'note_id': str(instance.id),
        })

        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        cycle = self._resolve_parent_cycle()

        if not self._is_manager_or_admin(request):
            return Response(
                {'success': False, 'error': str(CoreErrorMessages.PERMISSION_DENIED)},
                status=status.HTTP_403_FORBIDDEN,
            )

        logger.info('manager_note_create_requested', extra={
            **ctx, 'cycle_id': str(cycle.id),
        })

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='manager_note_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(cycle.client_id),
            target_type='manager_note',
            target_id=str(instance.id),
            outcome='success',
        )

        # Primitives captured outside the commit closure for the rich title
        # and the routing payload the frontend deep-links with.
        actor_name = request.user.get_full_name() or request.user.email
        account_name = cycle.account.company_name

        def _post_commit():
            self._invalidate_caches(cycle.client_id)
            # Notify the cycle owner that a note was added. The self-notify
            # and owner-None guards live in NotificationService.emit().
            NotificationService.emit(
                client_id=cycle.client_id,
                recipient=cycle.owner_id,
                actor=request.user,
                category=NotificationCategory.MANAGER_NOTE,
                title=f"{actor_name} left a note on {cycle.name} · {account_name}",
                related_object_type='decision_cycle',
                related_object_id=cycle.id,
                payload={'account_id': str(cycle.account_id), 'cycle_id': str(cycle.id)},
            )

        transaction.on_commit(_post_commit)

        output = ManagerNoteListSerializer(instance, context=self.get_serializer_context())
        return Response(
            {'success': True, 'data': output.data},
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        instance = self.get_object()
        note_id = str(instance.id)
        client_id = instance.client_id

        is_author = instance.created_by_id and str(instance.created_by_id) == str(request.user.id)

        if not is_author and not self._is_admin(request):
            return Response(
                {'success': False, 'error': str(CoreErrorMessages.PERMISSION_DENIED)},
                status=status.HTTP_403_FORBIDDEN,
            )

        logger.info('manager_note_delete_requested', extra={
            **ctx, 'note_id': note_id,
        })

        instance.delete()

        audit_log(
            event='manager_note_delete_success',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='manager_note',
            target_id=note_id,
            outcome='success',
        )

        self._invalidate_caches(client_id)

        return Response(
            {'success': True, 'data': None},
            status=status.HTTP_204_NO_CONTENT,
        )
