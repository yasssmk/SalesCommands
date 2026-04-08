# app_modules/signals/views/tech_stack_signal_views.py
"""
TechStackSignalViewSet — CRUD + validate/reject for TechStackSignal.

Inherits all shared logic from BaseSignalViewSet.
No extra select_related beyond the base chain — TechStackSignal has no
target_contact or target_department FK.
"""

from ..models import TechStackSignal
from ..serializers import (
    TechStackSignalListSerializer,
    TechStackSignalDetailSerializer,
    TechStackSignalCreateSerializer,
    TechStackSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


class TechStackSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for TechStackSignal.

    Endpoints (mounted under /tech-stack/):
      GET    /tech-stack/                  → list
      POST   /tech-stack/                  → create
      GET    /tech-stack/{id}/             → retrieve
      PATCH  /tech-stack/{id}/             → partial_update
      PUT    /tech-stack/{id}/             → update (treated as PATCH)
      DELETE /tech-stack/{id}/             → destroy
      POST   /tech-stack/{id}/validate/    → validate_signal
      POST   /tech-stack/{id}/reject/      → reject_signal
    """

    queryset                = TechStackSignal.objects.all()
    model_label             = 'tech_stack_signal'
    list_serializer_class   = TechStackSignalListSerializer
    detail_serializer_class = TechStackSignalDetailSerializer
    create_serializer_class = TechStackSignalCreateSerializer
    update_serializer_class = TechStackSignalUpdateSerializer

    search_fields = ['tech_name', 'usage', 'limitations']