# app_modules/signals/views/blocker_signal_views.py
"""
BlockerSignalViewSet — CRUD + validate/reject for BlockerSignal.

Inherits all shared logic from BaseSignalViewSet. Extends get_queryset()
with the `contact` FK preload (blocker-specific attribution surface)
to avoid an N+1 on list responses that render contact.first_name /
last_name on each row.

Cluster cache invalidation is intentionally left at the base default
(False): BlockerSignal does not participate in the cluster model — see
the BlockerSignal model docstring and signals/cache_invalidation.py.
"""

from ..models import BlockerSignal
from ..serializers import (
    BlockerSignalListSerializer,
    BlockerSignalDetailSerializer,
    BlockerSignalCreateSerializer,
    BlockerSignalUpdateSerializer,
)
from .base_views import BaseSignalViewSet


class BlockerSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for BlockerSignal.

    Endpoints (mounted under /blockers/):
      GET    /blockers/                  → list
      POST   /blockers/                  → create
      GET    /blockers/{id}/             → retrieve
      PATCH  /blockers/{id}/             → partial_update
      PUT    /blockers/{id}/             → update (treated as PATCH)
      DELETE /blockers/{id}/             → destroy
      POST   /blockers/{id}/validate/    → validate_signal
      POST   /blockers/{id}/reject/      → reject_signal
    """

    queryset                = BlockerSignal.objects.all()
    model_label             = 'blocker_signal'
    list_serializer_class   = BlockerSignalListSerializer
    detail_serializer_class = BlockerSignalDetailSerializer
    create_serializer_class = BlockerSignalCreateSerializer
    update_serializer_class = BlockerSignalUpdateSerializer

    # BlockerSignal does not participate in cluster aggregation — keep
    # the base default (False). See BlockerSignal model docstring and
    # signals/cache_invalidation.py for the rationale.
    invalidate_cluster_tag = False

    search_fields = ['summary']

    def get_queryset(self):
        """
        Extend base queryset with the Blocker-specific `contact` FK.

        Universally-present FKs (account, source_activity, validated_by,
        requested_by on detail) are preloaded by BaseSignalViewSet.
        `contact` is BlockerSignal-specific and gets preloaded here so
        the list serializer's compact contact payload does not trigger
        an N+1.
        """
        qs = super().get_queryset()
        qs = qs.select_related('contact')
        return qs
