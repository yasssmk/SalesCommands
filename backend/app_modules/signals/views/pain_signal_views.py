# app_modules/signals/views/pain_signal_views.py
"""
PainSignalViewSet — CRUD + validate/reject for PainSignal.

Inherits all shared logic from BaseSignalViewSet.
Extends get_queryset() with impacted_department select_related.
"""

from ..models import PainSignal
from ..serializers import (
    PainSignalListSerializer,
    PainSignalDetailSerializer,
    PainSignalCreateSerializer,
    PainSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


class PainSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for PainSignal.

    Endpoints (mounted under /pain/):
      GET    /pain/                  → list
      POST   /pain/                  → create
      GET    /pain/{id}/             → retrieve
      PATCH  /pain/{id}/             → partial_update
      PUT    /pain/{id}/             → update (treated as PATCH)
      DELETE /pain/{id}/             → destroy
      POST   /pain/{id}/validate/    → validate_signal
      POST   /pain/{id}/reject/      → reject_signal
    """

    queryset                = PainSignal.objects.all()
    model_label             = 'pain_signal'
    list_serializer_class   = PainSignalListSerializer
    detail_serializer_class = PainSignalDetailSerializer
    create_serializer_class = PainSignalCreateSerializer
    update_serializer_class = PainSignalUpdateSerializer

    search_fields = ['summary']

    def get_queryset(self):
        """
        Extend base queryset with PainSignal-specific optimisations.

        Notes:
          - impacted_department was removed from PainSignal in Sprint 1.6 —
            it now lives on PainImpact. No select_related on it here.
          - Nested 'impacts' are prefetched for all actions to avoid N+1
            when the serializer renders the nested list. The prefetch
            itself select_relates the FK fields on PainImpact to keep the
            total query count bounded at O(1) regardless of impact count.
        """
        from django.db.models import Prefetch
        from ..models import PainImpact

        qs = super().get_queryset()

        impacts_prefetch = Prefetch(
            'impacts',
            queryset=PainImpact.objects.select_related(
                'impacted_department',
                'impacted_contact',
            ).order_by('-created_at'),
        )
        qs = qs.prefetch_related(impacts_prefetch)

        return qs