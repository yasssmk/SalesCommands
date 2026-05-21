# app_modules/signals/views/impact_signal_views.py
"""
ImpactSignalViewSet — CRUD + validate/reject for ImpactSignal.

Inherits all shared logic from BaseSignalViewSet. Extends get_queryset()
with the BaseSignal-declared FKs (decision_cycle, campaign) that the
base queryset does not preload by default.

ImpactSignal participates in the cluster model on the same canonical
axes as PainSignal and ObjectiveSignal (canonical_key format:
"impact:<what>:<dimension>"). Every write therefore busts both
SIGNALS_CACHE_TAG and SIGNAL_CLUSTERS_CACHE_TAG — same stance as
PainSignalViewSet.
"""

from ..models import ImpactSignal
from ..serializers import (
    ImpactSignalListSerializer,
    ImpactSignalDetailSerializer,
    ImpactSignalCreateSerializer,
    ImpactSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


class ImpactSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for ImpactSignal.

    Endpoints (mounted under /impact/):
      GET    /impact/                  → list
      POST   /impact/                  → create
      GET    /impact/{id}/             → retrieve
      PATCH  /impact/{id}/             → partial_update
      PUT    /impact/{id}/             → update (treated as PATCH)
      DELETE /impact/{id}/             → destroy
      POST   /impact/{id}/validate/    → validate_signal
      POST   /impact/{id}/reject/      → reject_signal
    """

    queryset                = ImpactSignal.objects.all()
    model_label             = 'impact_signal'

    list_serializer_class   = ImpactSignalListSerializer
    detail_serializer_class = ImpactSignalDetailSerializer
    create_serializer_class = ImpactSignalCreateSerializer
    update_serializer_class = ImpactSignalUpdateSerializer

    # ImpactSignal participates in the cluster model on the same
    # canonical (what × dimension) axes as PainSignal and
    # ObjectiveSignal. Every write changes cluster membership,
    # priority score, freshness, or aggregated stats. Must bust the
    # signal_clusters cache tag in addition to signals.
    invalidate_cluster_tag = True

    # Full-text search anchor: the impact's narrative summary is the
    # only free-text field worth indexing for search (metric_text is
    # short and formatted, not narrative).
    search_fields = ['summary']

    def get_queryset(self):
        """
        Extend base queryset with ImpactSignal-relevant FK preloads.

        Adds the BaseSignal FKs (decision_cycle, campaign) that exist
        on ImpactSignal but are not preloaded by the base queryset
        (the base only preloads universally-present FKs — account,
        source_activity, audit users on detail, source_activity.contacts
        for the standardised source_context block).

        ImpactSignal carries no Impact-specific FK (no equivalent to
        Pain's related_techstack, Objective's target_contact /
        target_department, or TechStack's tech_catalog_entry).
        Lifecycle data is captured directly on the model
        (impact_type, scope_level, metric_text, human_impact) — all
        scalar fields requiring no relational preload.

        FKs preloaded here:
          - decision_cycle : exposed inside the source_context block
                              on detail responses.
          - campaign       : same.
        """
        qs = super().get_queryset()
        qs = qs.select_related(
            'decision_cycle',
            'campaign',
        )
        return qs