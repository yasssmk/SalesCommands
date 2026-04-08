# app_modules/signals/views/people_signal_views.py
"""
PeopleSignalViewSet — CRUD + validate/reject for PeopleSignal.

Inherits all shared logic from BaseSignalViewSet.
Extends get_queryset() with target_contact and target_department
select_related for list actions.
"""

from ..models import PeopleSignal
from ..serializers import (
    PeopleSignalListSerializer,
    PeopleSignalDetailSerializer,
    PeopleSignalCreateSerializer,
    PeopleSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


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
      POST   /people/{id}/validate/    → validate_signal
      POST   /people/{id}/reject/      → reject_signal
    """

    queryset                = PeopleSignal.objects.all()
    model_label             = 'people_signal'
    list_serializer_class   = PeopleSignalListSerializer
    detail_serializer_class = PeopleSignalDetailSerializer
    create_serializer_class = PeopleSignalCreateSerializer
    update_serializer_class = PeopleSignalUpdateSerializer

    search_fields = ['notes']

    def get_queryset(self):
        """
        Extend base queryset with PeopleSignal-specific select_related.

        List action: adds target_contact, target_department on top of
        base source_contact, source_department.
        All other actions: adds target_contact, target_department on top
        of the full base select_related chain.
        """
        qs = super().get_queryset()

        if self.action == 'list':
            qs = qs.select_related(
                'target_contact',
                'target_department',
            )
        else:
            qs = qs.select_related(
                'target_contact',
                'target_department',
            )

        return qs