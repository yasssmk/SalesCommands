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

    # PainSignal participates in the cluster model: every write changes
    # cluster membership, priority score, or freshness. Must bust the
    # signal_clusters cache tag in addition to signals.
    invalidate_cluster_tag = True

    search_fields = ['summary']

    def get_queryset(self):
        """
        Extend base queryset with PainSignal-specific optimisations.

        Adds the FKs that exist on PainSignal but not on every concrete
        type (the base queryset preloads only universally-present FKs
        since Sprint TechStack — see BaseSignalViewSet.get_queryset).

        Notes:
          - source_contact / source_department were removed from
            BaseSignal during the standardisation refactor — they no
            longer appear in any select_related. Provenance is now
            derived from source_activity (the standardised
            `source_context` block — see BaseSignalListSerializer /
            BaseSignalDetailSerializer).
          - impacted_department was removed from PainSignal in Sprint 1.6 —
            it now lives on PainImpact. No select_related on it here.
          - related_techstack (Sprint TechStack cross-reference) is
            included so the Pain detail / list serializers can render
            the compact catalog payload without an extra query per row.
          - Nested 'impacts' are prefetched for all actions to avoid N+1
            when the serializer renders the nested list. The prefetch
            itself select_relates the FK fields on PainImpact to keep the
            total query count bounded at O(1) regardless of impact count.
        """
        from django.db.models import Prefetch
        from ..models import PainImpact

        qs = super().get_queryset()

        # Pain-specific FKs added on top of the base queryset (which
        # preloads only universally-present FKs — account,
        # source_activity, audit users on detail, source_activity.contacts
        # for the standardised source_context block).
        qs = qs.select_related(
            'decision_cycle',
            'campaign',
            'related_techstack',
        )

        impacts_prefetch = Prefetch(
            'impacts',
            queryset=PainImpact.objects.select_related(
                'impacted_department',
                'impacted_contact',
            ).order_by('-created_at'),
        )
        qs = qs.prefetch_related(impacts_prefetch)

        return qs