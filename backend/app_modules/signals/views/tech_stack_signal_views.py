# app_modules/signals/views/tech_stack_signal_views.py
"""
TechStackSignalViewSet — CRUD + lifecycle actions for TechStackSignal.

Inherits all shared logic from BaseSignalViewSet.
Extends search_fields with tech_name so reps can search by tool name.
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
    API endpoints for TechStackSignal.

    Endpoints (mounted at /signals/tech-stack/ via urls.py):
      GET    /                    → list
      POST   /                    → create
      GET    /{id}/               → retrieve
      PATCH  /{id}/               → partial_update
      DELETE /{id}/               → destroy
      POST   /{id}/validate/      → validate_signal
      POST   /{id}/reject/        → reject_signal
      POST   /{id}/merge/         → merge_signal
      POST   /{id}/supersede/     → supersede_signal
    """

    queryset    = TechStackSignal.objects.all()
    model_label = 'tech_stack_signal'

    list_serializer_class   = TechStackSignalListSerializer
    detail_serializer_class = TechStackSignalDetailSerializer
    create_serializer_class = TechStackSignalCreateSerializer
    update_serializer_class = TechStackSignalUpdateSerializer

    # Extend base search fields with tech_name
    search_fields = BaseSignalViewSet.search_fields + ['tech_name']