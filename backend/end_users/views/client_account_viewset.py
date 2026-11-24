from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from django.db.models import Count, Q
from django.http import Http404
import time
from core.apps_shared_methods import BaseAPIView
from core.exceptions import StandardizedPermissionDenied
from core.error_messages import CoreErrorMessages
from ..models import ClientAccount
from ..serializers import ClientAccountSerializer


class ClientAccountViewSet(BaseAPIView, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    READ-ONLY access to the requester's OWN client account (the tenant root).

    The queryset goes through the shared tenant filter (BaseAPIView →
    ``filter_queryset_by_client``), which pins the tenant-root model to
    ``id = <tenant of the token>``: any other tenant's id is not found (404).
    A token without a tenant (product_admin, end user without
    ``client_account``) gets a 403.

    Exposed routes (end_users/urls.py): retrieve + seats. Listing, creating,
    updating or deleting tenants is NOT a client-side operation (TD-322);
    tenant management by the product admin is tracked in TD-329.
    """
    queryset = ClientAccount.objects.all()
    serializer_class = ClientAccountSerializer
    entity_name = 'client_account'
    # BaseAPIView carries generic put/patch/delete/post handlers that a
    # method absent from the as_view() mapping would otherwise reach: this
    # view is read-only, so any other method is a clean 405.
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        """The requester's own tenant only (shared tenant filter), with the
        serialized counts aggregated in the main query (no per-row COUNT).
        distinct=True is REQUIRED: two Count() over different relations in one
        query cross-join, so without DISTINCT each count would be inflated by
        the cardinality of the other."""
        try:
            queryset = super().get_queryset()
        except AuthenticationFailed:
            # Authenticated, but the token carries no tenant: the resource is
            # not theirs → 403 (not 401, not 500).
            raise StandardizedPermissionDenied(CoreErrorMessages.PERMISSION_DENIED)
        return queryset.annotate(
            users_count_annotated=Count(
                'users', filter=Q(users__is_active=True), distinct=True
            ),
            organizations_count_annotated=Count('organizations', distinct=True),
        )

    @action(detail=True, methods=['get'])
    def seats(self, request, pk=None):
        """
        Seat usage of the requester's own tenant.
        Used by: SeatsSummary (admin users page).

        GET /client/client-accounts/{uuid}/seats/

        Response:
        {
            "success": true,
            "data": {"seats": 100, "seats_used": 47, "seats_left": 53},
            "_meta": {"timing_ms": 12.45}
        }
        """
        start_time = time.time()

        client = self.get_queryset().filter(pk=pk).values(
            'max_users', 'users_count_annotated'
        ).first()
        if not client:
            raise Http404

        max_users = client['max_users'] or 0
        seats_used = client['users_count_annotated']

        return Response({
            'success': True,
            'data': {
                'seats': max_users,
                'seats_used': seats_used,
                'seats_left': max(0, max_users - seats_used),
            },
            '_meta': {
                'timing_ms': round((time.time() - start_time) * 1000, 2)
            }
        })
