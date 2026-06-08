# app_modules/signals/views/next_step_signal_views.py
"""
NextStepSignalViewSet — CRUD + validate/reject for NextStepSignal.

Inherits all shared logic from BaseSignalViewSet. Extends get_queryset()
with the `suggested_contacts` M2M prefetch (next-step-specific
attendee surface) to avoid an N+1 on list responses that render the
compact attendees payload on each row.

Cluster cache invalidation is intentionally left at the base default
(False): NextStepSignal does not participate in the cluster model — see
the NextStepSignal model docstring and signals/cache_invalidation.py.
"""

from ..models import NextStepSignal
from ..serializers import (
    NextStepSignalListSerializer,
    NextStepSignalDetailSerializer,
    NextStepSignalCreateSerializer,
    NextStepSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


class NextStepSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for NextStepSignal.

    Endpoints (mounted under /next-steps/):
      GET    /next-steps/                  → list
      POST   /next-steps/                  → create
      GET    /next-steps/{id}/             → retrieve
      PATCH  /next-steps/{id}/             → partial_update
      PUT    /next-steps/{id}/             → update (treated as PATCH)
      DELETE /next-steps/{id}/             → destroy
      POST   /next-steps/{id}/validate/    → validate_signal
      POST   /next-steps/{id}/reject/      → reject_signal
    """

    queryset                = NextStepSignal.objects.all()
    model_label             = 'next_step_signal'
    list_serializer_class   = NextStepSignalListSerializer
    detail_serializer_class = NextStepSignalDetailSerializer
    create_serializer_class = NextStepSignalCreateSerializer
    update_serializer_class = NextStepSignalUpdateSerializer

    # NextStepSignal does not participate in cluster aggregation — keep
    # the base default (False). See NextStepSignal model docstring and
    # signals/cache_invalidation.py for the rationale.
    invalidate_cluster_tag = False

    search_fields = ['suggested_title']

    def get_queryset(self):
        """
        Extend base queryset with the NextStep-specific
        `suggested_contacts` M2M prefetch.

        Universally-present FKs (account, source_activity, validated_by,
        requested_by on detail) are preloaded by BaseSignalViewSet.
        `suggested_contacts` is a NextStep-specific m2m and gets
        prefetched here so the list serializer's compact attendees
        payload does not trigger an N+1 (one extra query per row
        otherwise).
        """
        qs = super().get_queryset()
        qs = qs.prefetch_related('suggested_contacts', 'created_activities')
        return qs
