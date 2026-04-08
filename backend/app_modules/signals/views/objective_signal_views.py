# app_modules/signals/views/objective_signal_views.py
"""
ObjectiveSignalViewSet — CRUD + validate/reject for ObjectiveSignal.

Inherits all shared logic from BaseSignalViewSet.
Extends get_queryset() with target_contact and target_department
select_related for all actions.
"""

from ..models import ObjectiveSignal
from ..serializers import (
    ObjectiveSignalListSerializer,
    ObjectiveSignalDetailSerializer,
    ObjectiveSignalCreateSerializer,
    ObjectiveSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


class ObjectiveSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for ObjectiveSignal.

    Endpoints (mounted under /objective/):
      GET    /objective/                  → list
      POST   /objective/                  → create
      GET    /objective/{id}/             → retrieve
      PATCH  /objective/{id}/             → partial_update
      PUT    /objective/{id}/             → update (treated as PATCH)
      DELETE /objective/{id}/             → destroy
      POST   /objective/{id}/validate/    → validate_signal
      POST   /objective/{id}/reject/      → reject_signal
    """

    queryset                = ObjectiveSignal.objects.all()
    model_label             = 'objective_signal'
    list_serializer_class   = ObjectiveSignalListSerializer
    detail_serializer_class = ObjectiveSignalDetailSerializer
    create_serializer_class = ObjectiveSignalCreateSerializer
    update_serializer_class = ObjectiveSignalUpdateSerializer

    search_fields = ['summary', 'success_criteria']

    def get_queryset(self):
        """
        Extend base queryset with ObjectiveSignal-specific select_related.

        Adds target_contact and target_department on top of the base
        select_related chain for all actions.
        """
        qs = super().get_queryset()
        qs = qs.select_related(
            'target_contact',
            'target_department',
        )
        return qs