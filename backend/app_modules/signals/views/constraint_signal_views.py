# app_modules/signals/views/constraint_signal_views.py
"""
ConstraintSignalViewSet — CRUD + validate/reject/reopen for ConstraintSignal.

Inherits all shared logic from BaseSignalViewSet. Extends get_queryset()
with the `target_departments` M2M prefetch to avoid N+1 on list responses.

Cluster cache invalidation is set to True: ConstraintSignal participates
in the cluster model via its canonical_key (constraint:{what}:{dimension}).
"""

from ..models import ConstraintSignal
from ..serializers import (
    ConstraintSignalListSerializer,
    ConstraintSignalDetailSerializer,
    ConstraintSignalCreateSerializer,
    ConstraintSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


class ConstraintSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for ConstraintSignal.

    Endpoints (mounted under /constraints/):
      GET    /constraints/                  → list
      POST   /constraints/                  → create
      GET    /constraints/{id}/             → retrieve
      PATCH  /constraints/{id}/             → partial_update
      PUT    /constraints/{id}/             → update (treated as PATCH)
      DELETE /constraints/{id}/             → destroy
      POST   /constraints/{id}/validate/    → validate_signal
      POST   /constraints/{id}/reject/      → reject_signal
      POST   /constraints/{id}/reopen/      → reopen_signal
    """

    queryset                = ConstraintSignal.objects.all()
    model_label             = 'constraint_signal'
    list_serializer_class   = ConstraintSignalListSerializer
    detail_serializer_class = ConstraintSignalDetailSerializer
    create_serializer_class = ConstraintSignalCreateSerializer
    update_serializer_class = ConstraintSignalUpdateSerializer

    invalidate_cluster_tag = True

    search_fields = ['summary']

    def get_queryset(self):
        qs = super().get_queryset()
        # Multi-department scope is the target_departments M2M — prefetched so
        # the list/detail serializer's get_target_departments iterates the
        # cache with no per-row query (mirrors TechStackSignalViewSet).
        qs = qs.prefetch_related('target_departments')
        return qs
