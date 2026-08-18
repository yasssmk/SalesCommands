# app_modules/signals/views/pain_signal_views.py
"""
PainSignalViewSet — CRUD + validate/reject for PainSignal.

Inherits all shared logic from BaseSignalViewSet. Extends get_queryset()
with PainSignal-specific FKs (decision_cycle, campaign)
that do not exist on every concrete signal type and therefore are not
preloaded by the base.
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

    # PainSignal participates in the cluster model: every write changes
    # cluster membership, priority score, or freshness. Must bust the
    # signal_clusters cache tag in addition to signals.
    invalidate_cluster_tag = True

    search_fields = ['summary']

    def get_queryset(self):
        """
        Extend base queryset with PainSignal-specific optimisations.

        Adds the FKs that exist on PainSignal but not on every concrete
        signal type (the base queryset preloads only universally-present
        FKs — account, source_activity, audit users on detail,
        source_activity.contacts for the standardised source_context
        block).

        PainSignal-specific FKs preloaded here:
          - decision_cycle      : exposed inside the source_context block
                                  on detail responses.
          - campaign            : same.
          - related_techstack_mention : free-text tool trace rendered by
                                  the Pain List and Detail serializers
                                  on every row (no extra query per row).
        """
        qs = super().get_queryset()
        qs = qs.select_related(
            'decision_cycle',
            'campaign',
        )
        return qs