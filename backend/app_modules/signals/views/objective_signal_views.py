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

    Cluster cache invalidation:
      ObjectiveSignal participates in the cluster model since Wave B —
      clusters are grouped by canonical_key = "objective:<what>:<dimension>"
      on an account. Every write on this ViewSet therefore mutates
      cluster membership, priority score, or freshness. The
      `invalidate_cluster_tag = True` flag below instructs
      BaseSignalViewSet to bust SIGNAL_CLUSTERS_CACHE_TAG in addition
      to SIGNALS_CACHE_TAG after every create / update / delete /
      validate / reject.

      Note: the UI currently renders ObjectiveSignals as individual
      cards (not as clusters). The cluster payload is produced by
      SignalClusterService and consumed by the Pre-call Game Plan LLM
      pipeline. Invalidating the tag here keeps the cluster cache
      coherent for that downstream consumer regardless of the UI shape.
    """
    queryset                = ObjectiveSignal.objects.all()
    model_label             = 'objective_signal'
    list_serializer_class   = ObjectiveSignalListSerializer
    detail_serializer_class = ObjectiveSignalDetailSerializer
    create_serializer_class = ObjectiveSignalCreateSerializer
    update_serializer_class = ObjectiveSignalUpdateSerializer

    # ObjectiveSignal participates in the cluster model (see class
    # docstring). Writes here must bust the signal_clusters cache tag.
    invalidate_cluster_tag = True

    search_fields = ['summary', 'success_criteria']

    def get_queryset(self):
        """
        Extend base queryset with ObjectiveSignal-specific select_related.

        The base queryset now preloads only universally-present FKs since
        Sprint TechStack (account, source_activity, audit users). This
        method adds every Objective-specific FK on top:

          source_contact, source_department  — narrative provenance
          decision_cycle, campaign           — secondary deal links
          target_contact, target_department  — Objective subject
        """
        qs = super().get_queryset()
        qs = qs.select_related(
            'source_contact',
            'source_department',
            'decision_cycle',
            'campaign',
            'target_contact',
            'target_department',
        )
        return qs