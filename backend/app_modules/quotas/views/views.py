# app_modules/quotas/views/views.py
"""
Scoped CRUD for the personal Quota (objective).

Scoping is entirely delegated to the existing primitives — ScopedQuerysetMixin
(role scope via OWNERSHIP_MAP['quotas']) + ScopedPermission (registry via
module='quotas') + OwnerScopeMixin (owner_scope query param). This viewset adds
no bespoke filtering; it only wires owner/client_id on write.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ..models import Quota
from ..serializers import QuotaSerializer
from ..services.progress import compute_progress_batch


class QuotaViewSet(OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """Personal Sales objectives — each user manages their own; managers/admins
    read within their scope. Registry-scoped via module='quotas'."""

    queryset = Quota.objects.all()
    serializer_class = QuotaSerializer
    entity_name = 'quota'

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['metric', 'source_campaign', 'owner']
    ordering_fields = ['period_start', 'period_end', 'created_at', 'updated_at']
    ordering = ['-period_start', '-created_at']

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'quotas'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['client_id'] = self.get_client_id()
        # When list() precomputed the page's attainment in one batch pass, hand
        # it to the serializer so each row reads its progress from the map
        # instead of computing per-row (anti-N+1).
        progress_map = getattr(self, '_progress_map', None)
        if progress_map is not None:
            context['progress_map'] = progress_map
        return context

    def list(self, request, *args, **kwargs):
        """List with attainment precomputed in ONE batch pass over the page.

        compute_progress_batch groups the page's quotas by (metric, perimeter,
        window, campaign) so the metric runs once per group, not once per quota —
        the query count does not grow with the number of quotas on the page.
        """
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        objects = page if page is not None else list(queryset)

        self._progress_map = compute_progress_batch(objects)

        serializer = self.get_serializer(objects, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
