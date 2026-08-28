# app_modules/signals/views/tech_stack_signal_views.py
"""
TechStackSignalViewSet — CRUD + validate/reject for TechStackSignal.

Inherits all shared logic from BaseSignalViewSet.

Notes:
  * The model identifies its tool by free text (tech_name + the derived
    tech_name_normalized) and carries three qualification booleans — see
    app_modules/signals/models/tech_stack_signal.py for the full
    architecture.
  * `invalidate_cluster_tag = False`: TechStack is NOT clusterable
    (product decision) — it produces no clusters, so writes only need to
    bust SIGNALS_CACHE_TAG, never SIGNAL_CLUSTERS_CACHE_TAG.
  * Search hits the tool name directly (raw and normalised), so a rep
    typing "salesforce" matches however the LLM spelled it.
"""

from core.logging import get_logger

from ..models import TechStackSignal
from ..serializers import (
    TechStackSignalListSerializer,
    TechStackSignalDetailSerializer,
    TechStackSignalCreateSerializer,
    TechStackSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet

logger = get_logger(__name__)


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

    Cluster cache invalidation:
      TechStack is NOT clusterable (product decision) — it produces no
      clusters. Writes on this ViewSet therefore never affect cluster
      caches; `invalidate_cluster_tag = False` keeps invalidation scoped
      to SIGNALS_CACHE_TAG only.
    """

    queryset                = TechStackSignal.objects.all()
    model_label             = 'tech_stack_signal'
    list_serializer_class   = TechStackSignalListSerializer
    detail_serializer_class = TechStackSignalDetailSerializer
    create_serializer_class = TechStackSignalCreateSerializer
    update_serializer_class = TechStackSignalUpdateSerializer

    # TechStack is not clusterable (see class docstring) — writes here
    # must NOT bust the signal_clusters cache tag.
    invalidate_cluster_tag = False

    # Search across the tool name and the narrative fields. Both the raw
    # and the normalised name are searchable: the raw one matches what
    # the rep sees on the card, the normalised one makes the search
    # case- and spacing-insensitive without a DB function.
    search_fields = [
        'tech_name',
        'tech_name_normalized',
        'notes',
        'cost_description',
    ]

    def get_queryset(self):
        """
        Extend base queryset with TechStackSignal-specific joins.

        usage_department (single FK) is often null but is exposed compactly
        when set; select_related avoids N+1 on list views.

        usage_departments (M2M — who USES the tool) is exposed as a compact
        list. prefetch_related loads every signal's departments in ONE extra
        query for the whole page, so the serializer's obj.usage_departments
        .all() fires no per-row query regardless of how many departments a
        signal carries (constant query count, N+1-safe).

        The tool name lives on the row itself, so nothing else needs joining.
        """
        qs = super().get_queryset()
        qs = qs.select_related('usage_department')
        qs = qs.prefetch_related('usage_departments')
        return qs
