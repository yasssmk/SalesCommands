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

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ..models import Quota
from ..serializers import QuotaSerializer


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
        return context
