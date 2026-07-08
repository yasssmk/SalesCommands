# app_modules/signals/views/tech_stack_signal_views.py
"""
TechStackSignalViewSet — CRUD + validate/reject for TechStackSignal.

Inherits all shared logic from BaseSignalViewSet.

Notes:
  * The model uses a catalog FK + structured lifecycle fields — see
    app_modules/signals/models/tech_stack_signal.py for the full
    architecture.
  * `invalidate_cluster_tag = False`: TechStack is NOT clusterable
    (product decision) — it produces no clusters, so writes only need to
    bust SIGNALS_CACHE_TAG, never SIGNAL_CLUSTERS_CACHE_TAG.
  * Search now traverses the catalog FK so the rep can search by
    company / product name without dragging the catalog ID through the
    UI.
"""

from rest_framework.decorators import action
from rest_framework.response import Response

from core.logging import ctx_from_request, get_logger

from ..constants import SignalStatus
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

    # Search across narrative fields and the catalog FK's text columns,
    # so a rep typing "Salesforce" in the search box hits matching
    # signals without needing the catalog UUID.
    search_fields = [
        'notes',
        'cost_description',
        'tech_catalog_entry__company_name',
        'tech_catalog_entry__product_name',
    ]

    def get_queryset(self):
        """
        Extend base queryset with TechStackSignal-specific select_related.

        Adds tech_catalog_entry (the compact catalog payload exposed by
        the serializers) and usage_department (often null but exposed
        compactly when set; prefetching avoids N+1 on list views).
        """
        qs = super().get_queryset()
        qs = qs.select_related(
            'tech_catalog_entry',
            'usage_department',
        )
        return qs

    @action(detail=False, methods=['get'], url_path='detected')
    def detected(self, request):
        """
        List "detected" TechStack signals: PENDING observations whose
        LLM-extracted tool could not be matched to the tenant catalog
        (tech_catalog_entry is null; the raw name lives in
        metadata['pending_tech_name']).

        GET /tech-stack/detected/

        These are the signals an admin needs to reconcile — attach (or
        create) a catalog entry, then validate. Attaching goes through
        the normal PATCH path (TechStackSignalUpdateSerializer allows the
        FK while PENDING); this endpoint only surfaces the work list.

        Tenant-scoped (ScopedQuerysetMixin), paginated, ordered
        most-recent-first (TechStackSignal.Meta.ordering).
        """
        logger.info(
            'tech_stack_signal_detected_requested',
            extra=ctx_from_request(request),
        )

        qs = self.get_queryset().filter(
            status=SignalStatus.PENDING,
            tech_catalog_entry__isnull=True,
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.list_serializer_class(
                page, many=True, context={'request': request},
            )
            return self.get_paginated_response(serializer.data)

        serializer = self.list_serializer_class(
            qs, many=True, context={'request': request},
        )
        return Response({'success': True, 'data': serializer.data})