# app_modules/signals/views/people_signal_views.py
"""
PeopleSignalViewSet — CRUD + validate/reject/reopen for PeopleSignal.

Inherits all shared logic from BaseSignalViewSet. Extends get_queryset()
with the `target_contact` and `target_department` FK preloads to avoid
N+1 on list responses that render contact/department names.

Cluster cache invalidation is intentionally left at the base default
(False): PeopleSignal does not participate in the cluster model — it
has no canonical_key.
"""

from django.db import transaction
from rest_framework.decorators import action
from rest_framework.response import Response

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import PeopleSignal
from ..serializers import (
    PeopleSignalListSerializer,
    PeopleSignalDetailSerializer,
    PeopleSignalCreateSerializer,
    PeopleSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet, _invalidate_signal_caches


class PeopleSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for PeopleSignal.

    Endpoints (mounted under /people/):
      GET    /people/                  → list
      POST   /people/                  → create
      GET    /people/{id}/             → retrieve
      PATCH  /people/{id}/             → partial_update
      PUT    /people/{id}/             → update (treated as PATCH)
      DELETE /people/{id}/             → destroy
      POST   /people/{id}/validate/    → REFUSED (étape 5: use resolve)
      POST   /people/{id}/resolve/     → resolve (validate WITH a stakeholder)
      GET    /people/{id}/resolution-candidates/ → resolution_candidates
      POST   /people/{id}/reject/      → reject_signal
      POST   /people/{id}/reopen/      → reopen_signal
    """

    queryset                = PeopleSignal.objects.all()
    model_label             = 'people_signal'
    list_serializer_class   = PeopleSignalListSerializer
    detail_serializer_class = PeopleSignalDetailSerializer
    create_serializer_class = PeopleSignalCreateSerializer
    update_serializer_class = PeopleSignalUpdateSerializer

    invalidate_cluster_tag = False

    search_fields = ['notes']

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related('target_contact', 'target_department')
        return qs

    # =========================================================================
    # Sprint « Cycle de vie des contacts », étape 5 — signal -> stakeholder
    # =========================================================================

    def validate_signal(self, request, pk=None):
        """A People signal is validated WITH its stakeholder (resolve):
        the generic validate would bypass that rule — refused."""
        self.get_object()                     # 404 / scope first
        raise StandardizedValidationError(SignalErrorMessages.PEOPLE_REQUIRES_STAKEHOLDER)

    @action(detail=True, methods=['post'], url_path='resolve')
    @transaction.atomic
    def resolve(self, request, pk=None):
        """
        POST /people/{id}/resolve/ with ONE of {stakeholder_id} |
        {contact_id} | {create: {full_name?, department_id?}} — affiliation
        + validation in one transaction (stakeholder_service).
        """
        from app_modules.decision_cycles.services.stakeholder_service import (
            resolve_people_signal,
        )
        instance = self.get_object()
        body = request.data or {}
        updated = resolve_people_signal(
            instance, request.user,
            stakeholder_id=body.get('stakeholder_id'),
            contact_id=body.get('contact_id'),
            create=body.get('create'),
        )
        transaction.on_commit(lambda: _invalidate_signal_caches(self.get_client_id()))
        output = self.detail_serializer_class(updated, context={'request': request})
        return Response({'success': True, 'data': output.data})

    @action(detail=True, methods=['get'], url_path='resolution-candidates')
    def resolution_candidates(self, request, pk=None):
        """GET /people/{id}/resolution-candidates/ — the DC stakeholders +
        the account contacts not yet stakeholders; exact matches proposed."""
        from app_modules.decision_cycles.services.stakeholder_service import (
            resolution_candidates,
        )
        instance = self.get_object()
        return Response({'success': True, 'data': resolution_candidates(instance)})
