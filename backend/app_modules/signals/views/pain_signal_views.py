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

    search_fields = ['summary', 'business_cost']

    def get_queryset(self):
        """
        Extend base queryset with PainSignal-specific select_related.

        Adds impacted_department on top of the base select_related chain
        for all actions.
        """
        qs = super().get_queryset()
        qs = qs.select_related('impacted_department')
        return qs