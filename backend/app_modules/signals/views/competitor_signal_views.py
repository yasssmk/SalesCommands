# app_modules/signals/views/competitor_signal_views.py
"""
CompetitorSignalViewSet — CRUD + validate/reject/reopen for CompetitorSignal.

Inherits all shared logic from BaseSignalViewSet. Cloned on
ConstraintSignalViewSet but simpler: CompetitorSignal has no
target_department FK, so no extra select_related is added.

Cluster cache invalidation is set to True: CompetitorSignal participates in
the cluster model via its derived competitor_name_normalized (read-time
grouping key, DC-only).
"""

from ..models import CompetitorSignal
from ..serializers import (
    CompetitorSignalListSerializer,
    CompetitorSignalDetailSerializer,
    CompetitorSignalCreateSerializer,
    CompetitorSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


class CompetitorSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for CompetitorSignal.

    Endpoints (mounted under /competitor/):
      GET    /competitor/                  → list
      POST   /competitor/                  → create
      GET    /competitor/{id}/             → retrieve
      PATCH  /competitor/{id}/             → partial_update
      PUT    /competitor/{id}/             → update (treated as PATCH)
      DELETE /competitor/{id}/             → destroy
      POST   /competitor/{id}/validate/    → validate_signal
      POST   /competitor/{id}/reject/      → reject_signal
      POST   /competitor/{id}/reopen/      → reopen_signal
    """

    queryset                = CompetitorSignal.objects.all()
    model_label             = 'competitor_signal'
    list_serializer_class   = CompetitorSignalListSerializer
    detail_serializer_class = CompetitorSignalDetailSerializer
    create_serializer_class = CompetitorSignalCreateSerializer
    update_serializer_class = CompetitorSignalUpdateSerializer

    invalidate_cluster_tag = True

    search_fields = ['competitor_name', 'summary']
