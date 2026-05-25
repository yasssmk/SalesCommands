# app_modules/signals/views/cluster_views.py
"""
Views for signal clusters.

Four endpoints, all class-based APIView (not ViewSet):
  GET  /module-signals/clusters/                        → list
  GET  /module-signals/clusters/<canonical_key>/        → detail
  POST /module-signals/clusters/archive/                → archive a cluster
  POST /module-signals/clusters/unarchive/              → unarchive a cluster

Why APIView and not ViewSet
---------------------------
A cluster is not an ORM entity. canonical_key is not a DB primary key,
and there is no CRUD surface on the cluster itself (writes happen on
signals or on SignalClusterArchival). Forcing a ViewSet here would
require a fake queryset and hide the fact that the "resource" is a
computed projection.

Authentication & scoping
------------------------
All four views use CustomJWTAuthentication + IsAuthenticated +
ScopedPermission with module = 'signals'. Tenant isolation is enforced
through ClientScopeManager.ViewMixin (via BaseAPIView) for every DB
write or read against SignalClusterArchival.

Cache invalidation
------------------
Archive / unarchive invalidate the shared 'signals' cache tag so that
any cached cluster listing becomes instantly stale. Follows the pattern
used by BaseSignalViewSet.
"""

from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.apps_shared_methods import BaseAPIView
from core.cache_utils import invalidate_tag
from core.error_messages import CoreErrorMessages, SignalErrorMessages
from core.exceptions import StandardizedValidationError
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

from permissions.mixins import ScopedPermission

from ..constants import SignalClusterType
from ..models import SignalClusterArchival
from ..serializers import (
    SignalClusterDetailSerializer,
    SignalClusterListSerializer,
)
from ..constants import (
    SignalClusterType,
    SIGNALS_CACHE_TAG,
    SIGNAL_CLUSTERS_CACHE_TAG,
)
from ..services import SignalClusterService

logger = get_logger(__name__)

_VALID_CLUSTER_TYPES = {choice.value for choice in SignalClusterType}


def _invalidate_signal_caches(client_id):
    """
    Invalidate both signal and cluster cache tags after any archival change.

    Archive / unarchive affect cluster visibility in list responses
    (via include_archived filtering). Invalidating SIGNAL_CLUSTERS_CACHE_TAG
    is mandatory here.

    SIGNALS_CACHE_TAG is also invalidated so that any signal-level
    listing that projects "has_active_cluster_archive" (future-proofing
    for pipeline generation hooks) stays consistent. Cost is a single
    extra Redis INCR — negligible.
    """
    client_id_str = str(client_id)
    invalidate_tag(client_id_str, SIGNALS_CACHE_TAG)
    invalidate_tag(client_id_str, SIGNAL_CLUSTERS_CACHE_TAG)


# =============================================================================
# HELPERS — query / body parsing
# =============================================================================

def _parse_account_id(request, *, source='query'):
    """
    Extract the 'account' identifier from the request.

    Args:
        request: DRF request.
        source:  'query' for GET endpoints, 'body' for POST endpoints.

    Returns:
        The account UUID (as string).

    Raises:
        StandardizedValidationError if 'account' is missing or empty.
    """
    container = request.query_params if source == 'query' else request.data
    account_id = container.get('account')
    if not account_id:
        raise StandardizedValidationError(
            SignalErrorMessages.CLUSTER_ACCOUNT_REQUIRED
        )
    return account_id


def _parse_signal_type(request, *, source='query', allow_list: bool = False):
    """
    Extract 'signal_type' from the request, defaulting to 'pain'.

    Two modes controlled by `allow_list`:
      - allow_list=False (default, used by Detail / Archive / Unarchive):
          Returns a single string. A CSV input is rejected — a detail
          is always about one signal_type.
      - allow_list=True (used by List):
          Accepts either a single value ('pain') or a CSV list
          ('pain,objective'). Returns a list of strings. The deeper
          validation and deduplication are performed by the service
          layer (SignalClusterService._assert_signal_types_supported).

    Validation performed here is kept purposefully shallow: we only
    check that each token is a known SignalClusterType value. The
    service is the single source of truth for which types are
    actually *supported* for aggregation. This mirrors how the service
    treats Objective (valid type but yields no clusters yet).

    Args:
        request:     DRF request object.
        source:      'query' for GET endpoints, 'body' for POST endpoints.
        allow_list:  When True, accepts CSV input and returns a list.

    Returns:
        str when allow_list=False, list[str] when allow_list=True.

    Raises:
        StandardizedValidationError if any provided value is not a
        valid SignalClusterType.
    """
    container = request.query_params if source == 'query' else request.data
    raw_value = container.get('signal_type')

    # Default to 'pain' when the caller omits the param entirely.
    if not raw_value:
        return [SignalClusterType.PAIN.value] if allow_list else (
            SignalClusterType.PAIN.value
        )

    if allow_list:
        # Split on comma and strip whitespace. Empty tokens (e.g. from a
        # trailing comma) are dropped silently — they carry no intent.
        tokens = [t.strip() for t in raw_value.split(',') if t.strip()]
        if not tokens:
            # Treat "signal_type=" or "signal_type=,," as missing.
            return [SignalClusterType.PAIN.value]

        for token in tokens:
            if token not in _VALID_CLUSTER_TYPES:
                raise StandardizedValidationError(
                    SignalErrorMessages.CLUSTER_SIGNAL_TYPE_INVALID.format(
                        signal_type=token,
                    )
                )
        return tokens

    # Single-value mode (Detail / Archive / Unarchive). A comma here is
    # a caller mistake — reject rather than silently picking the first.
    if ',' in raw_value:
        raise StandardizedValidationError(
            SignalErrorMessages.CLUSTER_SIGNAL_TYPE_INVALID.format(
                signal_type=raw_value,
            )
        )

    if raw_value not in _VALID_CLUSTER_TYPES:
        raise StandardizedValidationError(
            SignalErrorMessages.CLUSTER_SIGNAL_TYPE_INVALID.format(
                signal_type=raw_value,
            )
        )
    return raw_value


def _parse_bool(value, *, default=False):
    """Parse a query-string boolean ('true'/'false'/'1'/'0') with default."""
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


# =============================================================================
# LIST
# =============================================================================

class SignalClusterListView(BaseAPIView):
    """
    GET /module-signals/clusters/

    Query params:
      account           (UUID, required)
      signal_type       (optional, default 'pain')
      decision_cycle    (UUID, optional — filter to clusters touching this DC)
      include_archived  (bool, optional, default false)

    Response:
      200 { success: true, data: [ cluster, cluster, ... ] }
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'signals'
    entity_name            = 'signal_cluster'

    def get(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        logger.info('signal_cluster_list_requested', extra=ctx)

        account_id         = _parse_account_id(request, source='query')
        # List accepts either a single signal_type or a CSV list so the
        # frontend can fetch mixed Pain+Objective clusters in one call.
        # SignalClusterService.list_clusters_for_account is the final
        # authority on which types yield results.
        signal_type        = _parse_signal_type(
            request, source='query', allow_list=True,
        )
        decision_cycle_id  = request.query_params.get('decision_cycle') or None
        include_archived   = _parse_bool(
            request.query_params.get('include_archived'),
            default=False,
        )

        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account_id,
            signal_type=signal_type,
            decision_cycle_id=decision_cycle_id,
            include_archived=include_archived,
        )

        serializer = SignalClusterListSerializer(clusters, many=True)
        return Response({'success': True, 'data': serializer.data})


# =============================================================================
# DETAIL
# =============================================================================

class SignalClusterDetailView(BaseAPIView):
    """
    GET /module-signals/clusters/<canonical_key>/

    Path param:
      canonical_key  (string, e.g. 'pain:OPS:TIME')

    Query params:
      account      (UUID, required)
      signal_type  (optional, default 'pain')

    Response:
      200 { success: true, data: { ...cluster, members: [...] } }
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'signals'
    entity_name            = 'signal_cluster'

    def get(self, request, canonical_key=None, *args, **kwargs):
        ctx = ctx_from_request(request)
        logger.info('signal_cluster_detail_requested', extra={
            **ctx, 'canonical_key': canonical_key,
        })

        if not canonical_key:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_CANONICAL_KEY_REQUIRED
            )

        account_id  = _parse_account_id(request, source='query')
        signal_type = _parse_signal_type(request, source='query')

        cluster = SignalClusterService.get_cluster_detail(
            account_id=account_id,
            canonical_key=canonical_key,
            signal_type=signal_type,
        )

        serializer = SignalClusterDetailSerializer(cluster)
        return Response({'success': True, 'data': serializer.data})


# =============================================================================
# ARCHIVE
# =============================================================================

class SignalClusterArchiveView(BaseAPIView):
    """
    POST /module-signals/clusters/archive/

    Body:
      {
        "account":       "<uuid>",
        "canonical_key": "pain:OPS:TIME",
        "signal_type":   "pain"     // optional, default 'pain'
      }

    Response:
      201 { success: true, data: { archived: true, canonical_key, signal_type } }

    Errors:
      400  CLUSTER_ALREADY_ARCHIVED  if an active archival row already exists.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'signals'
    entity_name            = 'signal_cluster'

    action_policies = {
        'post': {'crud': 'update', 'scope': 'client'},
    }

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        ctx           = ctx_from_request(request)
        account_id    = _parse_account_id(request, source='body')
        signal_type   = _parse_signal_type(request, source='body')
        canonical_key = request.data.get('canonical_key')

        if not canonical_key:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_CANONICAL_KEY_REQUIRED
            )

        client_id = self.get_client_id()

        logger.info('signal_cluster_archive_requested', extra={
            **ctx,
            'account_id':    str(account_id),
            'signal_type':   signal_type,
            'canonical_key': canonical_key,
        })

        # Guard: no active archival row must already exist for this cluster.
        # The DB-level partial unique constraint would catch a race, but
        # surfacing a clean 400 beforehand gives a better API contract.
        exists = SignalClusterArchival.objects.filter(
            client_id=client_id,
            account_id=account_id,
            signal_type=signal_type,
            canonical_key=canonical_key,
            unarchived_at__isnull=True,
        ).exists()
        if exists:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_ALREADY_ARCHIVED
            )

        archival = SignalClusterArchival(
            account_id=account_id,
            signal_type=signal_type,
            canonical_key=canonical_key,
            archived_by=request.user,
        )
        archival.save(user=request.user, client_id=client_id)

        audit_log(
            event='signal_cluster_archived',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='signal_cluster',
            target_id=canonical_key,
            outcome='success',
            extra={
                'account_id':    str(account_id),
                'signal_type':   signal_type,
                'canonical_key': canonical_key,
            },
        )

        transaction.on_commit(lambda: _invalidate_signal_caches(client_id))

        return Response(
            {
                'success': True,
                'data': {
                    'archived':      True,
                    'canonical_key': canonical_key,
                    'signal_type':   signal_type,
                },
            },
            status=status.HTTP_201_CREATED,
        )


# =============================================================================
# UNARCHIVE
# =============================================================================

class SignalClusterUnarchiveView(BaseAPIView):
    """
    POST /module-signals/clusters/unarchive/

    Body:
      {
        "account":       "<uuid>",
        "canonical_key": "pain:OPS:TIME",
        "signal_type":   "pain"     // optional, default 'pain'
      }

    Response:
      200 { success: true, data: { archived: false, canonical_key, signal_type } }

    Errors:
      400  CLUSTER_NOT_ARCHIVED  if no active archival row exists for the cluster.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'signals'
    entity_name            = 'signal_cluster'

    action_policies = {
        'post': {'crud': 'update', 'scope': 'client'},
    }

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        ctx           = ctx_from_request(request)
        account_id    = _parse_account_id(request, source='body')
        signal_type   = _parse_signal_type(request, source='body')
        canonical_key = request.data.get('canonical_key')

        if not canonical_key:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_CANONICAL_KEY_REQUIRED
            )

        client_id = self.get_client_id()

        logger.info('signal_cluster_unarchive_requested', extra={
            **ctx,
            'account_id':    str(account_id),
            'signal_type':   signal_type,
            'canonical_key': canonical_key,
        })

        archival = (
            SignalClusterArchival.objects
            .filter(
                client_id=client_id,
                account_id=account_id,
                signal_type=signal_type,
                canonical_key=canonical_key,
                unarchived_at__isnull=True,
            )
            .first()
        )

        if not archival:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_NOT_ARCHIVED
            )

        archival.unarchived_at = timezone.now()
        archival.unarchived_by = request.user
        archival.save(user=request.user)

        audit_log(
            event='signal_cluster_unarchived',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='signal_cluster',
            target_id=canonical_key,
            outcome='success',
            extra={
                'account_id':    str(account_id),
                'signal_type':   signal_type,
                'canonical_key': canonical_key,
            },
        )

        transaction.on_commit(lambda: _invalidate_signal_caches(client_id))

        return Response({
            'success': True,
            'data': {
                'archived':      False,
                'canonical_key': canonical_key,
                'signal_type':   signal_type,
            },
        })