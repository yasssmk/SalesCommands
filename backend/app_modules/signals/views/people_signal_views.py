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
