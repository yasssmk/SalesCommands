# app_modules/campaigns/views/campaign_views.py
"""
CampaignViewSet — CRUD + lifecycle actions + dashboard + playlist.

Follows ActivityViewSet / TerritoryViewSet patterns:
    - BaseAPIView + ScopedQuerysetMixin + OwnerScopeMixin
    - Response({'success': True, 'data': ...})
    - Redis caching with tag invalidation
    - Structured logging + SOC 2 audit trail
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Count

from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.cache_utils import (
    invalidate_tag,
    build_drf_cache_key,
    cache_get_set,
    get_permissions_version,
    _is_redis_backend,
)

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ..models import (
    Campaign,
    CampaignStatus,
    CampaignType,
    CampaignAccount,
    CampaignMember,
)
from ..serializers import (
    CampaignListSerializer,
    CampaignDetailSerializer,
    CampaignCreateSerializer,
    CampaignUpdateSerializer,
)
from ..services import (
    CampaignCreationService,
    CampaignLifecycleService,
    CampaignExecutionService,
    CampaignAnalyticsService,
)
from ..config.settings import CONFIG

logger = get_logger(__name__)


class CampaignViewSet(OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing Campaigns.

    Endpoints:
        GET    /campaigns/                  - List campaigns
        POST   /campaigns/                  - Create campaign
        GET    /campaigns/{id}/             - Retrieve campaign
        PATCH  /campaigns/{id}/             - Update campaign
        DELETE /campaigns/{id}/             - Delete campaign

        POST   /campaigns/{id}/start/       - Start campaign
        POST   /campaigns/{id}/pause/       - Pause campaign
        POST   /campaigns/{id}/resume/      - Resume campaign
        POST   /campaigns/{id}/complete/    - Complete campaign
        POST   /campaigns/{id}/cancel/      - Cancel campaign

        GET    /campaigns/{id}/dashboard/   - Campaign dashboard KPIs
        GET    /campaigns/{id}/summary/     - Campaign summary
        GET    /campaigns/{id}/playlist/    - Activity playlist

        POST   /campaigns/{id}/generate-activities/ - Generate activities
    """

    queryset = Campaign.objects.all()
    serializer_class = CampaignDetailSerializer
    entity_name = 'campaign'

    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'status': ['exact', 'in'],
        'campaign_type': ['exact'],
        'territory': ['exact'],
    }
    search_fields = CONFIG.filters.campaign_search
    ordering_fields = ['name', 'status', 'campaign_type', 'start_date', 'end_date', 'created_at']
    ordering = CONFIG.filters.default_campaign_ordering

    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'campaigns'

    # Action policies
    action_policies = {
        'start': {'crud': 'update', 'scope': 'client'},
        'pause': {'crud': 'update', 'scope': 'client'},
        'resume': {'crud': 'update', 'scope': 'client'},
        'complete': {'crud': 'update', 'scope': 'client'},
        'cancel': {'crud': 'update', 'scope': 'client'},
        'dashboard': {'crud': 'read', 'scope': 'client'},
        'summary': {'crud': 'read', 'scope': 'client'},
        'playlist': {'crud': 'read', 'scope': 'client'},
        'generate_activities': {'crud': 'update', 'scope': 'client'},
        'my_campaigns': {'crud': 'read', 'scope': 'mine'},
    }

    # ==========================================================================
    # CACHE HELPERS
    # ==========================================================================

    def _invalidate_campaign_caches(self, client_id):
        """Invalidate campaign and cross-module caches."""
        client_id_str = str(client_id)
        invalidate_tag(client_id_str, 'campaigns')
        invalidate_tag(client_id_str, 'activities')

        logger.info('cache_invalidation_campaign', extra={
            'event': 'cache_invalidation',
            'client_id': client_id_str,
            'tags': ['campaigns', 'activities'],
        })

    # ==========================================================================
    # SERIALIZER SELECTION
    # ==========================================================================

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return CampaignListSerializer
        elif self.action == 'create':
            return CampaignCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CampaignUpdateSerializer
        return CampaignDetailSerializer

    # ==========================================================================
    # QUERYSET
    # ==========================================================================

    def get_queryset(self):
        """Get filtered queryset with optimized prefetching."""
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'CampaignViewSet',
        })

        queryset = super().get_queryset()

        if self.action == 'list':
            queryset = queryset.select_related(
                'territory',
            ).prefetch_related(
                'objectives',
                'members',
            ).annotate(
                _accounts_count=Count('campaign_accounts', distinct=True),
                _members_count=Count('members', distinct=True),
            )
        elif self.action == 'retrieve':
            queryset = queryset.select_related(
                'territory',
                'created_by',
                'updated_by',
            ).prefetch_related(
                'objectives',
                'members__user',
                'members__added_by',
                'campaign_accounts',
            ).annotate(
                _accounts_count=Count('campaign_accounts', distinct=True),
            )
        else:
            queryset = queryset.select_related('territory')

        # Apply owner scope filter (mine/team/all)
        queryset = self.apply_owner_scope_filter(queryset)

        return queryset

    # ==========================================================================
    # LIST
    # ==========================================================================

    def list(self, request, *args, **kwargs):
        """
        List campaigns with pagination and Redis caching.
        GET /campaigns/
        """
        ctx = ctx_from_request(request)
        logger.info("campaigns_list_requested", extra=ctx)

        if not _is_redis_backend():
            return Response(self._list_uncached_data(request))

        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='campaigns_list',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            tag_namespace='campaigns',
        )

        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: self._list_uncached_data(request),
            ttl=60,
            tag=(client_id, 'campaigns'),
        )

        logger.info("campaigns_list_success", extra={
            **ctx,
            'count': cached_data.get('data', {}).get('count', '-') if isinstance(cached_data.get('data'), dict) else '-',
        })

        return Response(cached_data)

    def _list_uncached_data(self, request):
        """Produce list data dict (cache-friendly)."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            }

        serializer = self.get_serializer(queryset, many=True)
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            }
        }

    # ==========================================================================
    # RETRIEVE
    # ==========================================================================

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single campaign.
        GET /campaigns/{id}/
        """
        ctx = ctx_from_request(request)
        pk = kwargs.get('pk')

        if not _is_redis_backend():
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({'success': True, 'data': serializer.data})

        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='campaign_detail',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            extra=str(pk),
            tag_namespace='campaigns',
        )

        def producer():
            instance = self.get_object()
            serializer = CampaignDetailSerializer(instance, context={'request': request})
            return {'success': True, 'data': serializer.data}

        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, 'campaigns'),
        )

        logger.info("campaign_retrieved", extra={**ctx, 'campaign_id': str(pk)})
        return Response(cached_data)

    # ==========================================================================
    # CREATE
    # ==========================================================================

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new campaign with optional nested entities.
        POST /campaigns/
        """
        ctx = ctx_from_request(request)
        logger.info("campaign_create_requested", extra=ctx)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        # Invalidate caches
        client_id = self.get_client_id()
        self._invalidate_campaign_caches(client_id)

        logger.info("campaign_create_success", extra={
            **ctx,
            'campaign_id': str(instance.id),
            'campaign_name': instance.name,
        })

        output = CampaignDetailSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': output.data,
        }, status=status.HTTP_201_CREATED)

    # ==========================================================================
    # UPDATE
    # ==========================================================================

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update campaign (PUT). Delegates to partial_update."""
        return self._perform_update(request, partial=False, *args, **kwargs)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Partial update campaign (PATCH)."""
        return self._perform_update(request, partial=True, *args, **kwargs)

    def _perform_update(self, request, partial=False, *args, **kwargs):
        """Common update logic for PUT and PATCH."""
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("campaign_update_requested", extra={
            **ctx,
            'campaign_id': str(instance.id),
            'partial': partial,
        })

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        # Audit
        audit_log(
            event='campaign_update_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign',
            target_id=str(instance.id),
            outcome='success',
            extra={'campaign_name': instance.name},
        )

        client_id = self.get_client_id()
        self._invalidate_campaign_caches(client_id)

        logger.info("campaign_update_success", extra={
            **ctx,
            'campaign_id': str(instance.id),
        })

        output = CampaignDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': output.data})

    # ==========================================================================
    # DELETE
    # ==========================================================================

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a campaign.
        DELETE /campaigns/{id}/

        Only DRAFT campaigns can be deleted.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        if instance.status != CampaignStatus.DRAFT:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_IN_FINAL_STATE.format(
                    state=instance.get_status_display()
                )
            )

        campaign_id = str(instance.id)
        campaign_name = instance.name

        logger.info("campaign_delete_requested", extra={
            **ctx,
            'campaign_id': campaign_id,
        })

        instance.delete()

        audit_log(
            event='campaign_delete_success',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign',
            target_id=campaign_id,
            outcome='success',
            extra={'campaign_name': campaign_name},
        )

        client_id = self.get_client_id()
        self._invalidate_campaign_caches(client_id)

        logger.info("campaign_delete_success", extra={
            **ctx,
            'campaign_id': campaign_id,
        })

        return Response({
            'success': True,
            'data': None,
        }, status=status.HTTP_204_NO_CONTENT)

    # ==========================================================================
    # LIFECYCLE ACTIONS
    # ==========================================================================

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def start(self, request, pk=None):
        """
        Start campaign: DRAFT → ACTIVE.
        POST /campaigns/{id}/start/
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_start_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        service = CampaignLifecycleService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.start(campaign)

        self._invalidate_campaign_caches(self.get_client_id())

        output = CampaignDetailSerializer(result['campaign'], context={'request': request})
        return Response({
            'success': True,
            'data': {
                'campaign': output.data,
                'accounts_activated': result['accounts_activated'],
                'accounts_enrolled': result['accounts_enrolled'],
                'activities_created': result.get('activities_created', 0),
                'generation_errors': result.get('generation_errors', []),
            },
        })


    @action(detail=True, methods=['post'])
    @transaction.atomic
    def pause(self, request, pk=None):
        """
        Pause campaign: ACTIVE → PAUSED.
        POST /campaigns/{id}/pause/
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_pause_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        service = CampaignLifecycleService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.pause(campaign)

        self._invalidate_campaign_caches(self.get_client_id())

        output = CampaignDetailSerializer(result['campaign'], context={'request': request})
        return Response({
            'success': True,
            'data': output.data,
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def resume(self, request, pk=None):
        """
        Resume campaign: PAUSED → ACTIVE.
        POST /campaigns/{id}/resume/
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_resume_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        service = CampaignLifecycleService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.resume(campaign)

        self._invalidate_campaign_caches(self.get_client_id())

        output = CampaignDetailSerializer(result['campaign'], context={'request': request})
        return Response({
            'success': True,
            'data': {
                'campaign': output.data,
                'callbacks_resumed': result['callbacks_resumed'],
            },
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        """
        Complete campaign: ACTIVE/PAUSED → COMPLETED.
        POST /campaigns/{id}/complete/
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_complete_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        service = CampaignLifecycleService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.complete(campaign)

        self._invalidate_campaign_caches(self.get_client_id())

        output = CampaignDetailSerializer(result['campaign'], context={'request': request})
        return Response({
            'success': True,
            'data': {
                'campaign': output.data,
                'accounts_stopped': result['accounts_stopped'],
            },
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancel(self, request, pk=None):
        """
        Cancel campaign: any non-final → CANCELLED.
        POST /campaigns/{id}/cancel/
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_cancel_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        service = CampaignLifecycleService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.cancel(campaign)

        self._invalidate_campaign_caches(self.get_client_id())

        output = CampaignDetailSerializer(result['campaign'], context={'request': request})
        return Response({
            'success': True,
            'data': {
                'campaign': output.data,
                'accounts_stopped': result['accounts_stopped'],
                'activities_cancelled': result['activities_cancelled'],
            },
        })

    # ==========================================================================
    # DASHBOARD & ANALYTICS ACTIONS
    # ==========================================================================

    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """
        Full campaign dashboard KPIs.
        GET /campaigns/{id}/dashboard/
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_dashboard_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        if not _is_redis_backend():
            data = self._produce_dashboard(campaign)
            return Response({'success': True, 'data': data})

        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='campaign_dashboard',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            extra=str(campaign.id),
            tag_namespace='campaigns',
        )

        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: {'success': True, 'data': self._produce_dashboard(campaign)},
            ttl=30,
            tag=(client_id, 'campaigns'),
        )

        return Response(cached_data)

    def _produce_dashboard(self, campaign):
        """Produce dashboard data dict."""
        service = CampaignAnalyticsService(client_id=self.get_client_id())
        return service.get_dashboard(campaign)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Campaign summary stats.
        GET /campaigns/{id}/summary/
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_summary_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        service = CampaignAnalyticsService(client_id=self.get_client_id())
        data = service.get_summary(campaign)

        return Response({'success': True, 'data': data})

    # ==========================================================================
    # PLAYLIST ACTION
    # ==========================================================================

    @action(detail=True, methods=['get'])
    def playlist(self, request, pk=None):
        """
        Get prioritized activity playlist for campaign.
        GET /campaigns/{id}/playlist/?executor_id={uuid}&limit={int}
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_playlist_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        # Optional executor filter
        from end_users.models import User
        executor = None
        executor_id = request.query_params.get('executor_id')
        if executor_id:
            try:
                executor = User.objects.get(id=executor_id)
            except User.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )

        limit = request.query_params.get('limit')
        if limit:
            try:
                limit = int(limit)
            except (TypeError, ValueError):
                limit = None

        service = CampaignExecutionService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.get_playlist(campaign, executor=executor, limit=limit)

        # Serialize activities
        from app_modules.activities.serializers import ActivityListSerializer
        serializer = ActivityListSerializer(
            result['activities'], many=True, context={'request': request}
        )

        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'total_count': result['total_count'],
            },
        })

    # ==========================================================================
    # EXECUTION ACTIONS
    # ==========================================================================

    @action(detail=True, methods=['post'], url_path='generate-activities')
    @transaction.atomic
    def generate_activities(self, request, pk=None):
        """
        Generate activities for campaign accounts.
        POST /campaigns/{id}/generate-activities/

        Body (optional):
            - activity_type: Override default activity type
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()

        logger.info("campaign_generate_activities_requested", extra={
            **ctx, 'campaign_id': str(campaign.id),
        })

        activity_type = request.data.get('activity_type')

        service = CampaignExecutionService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.generate_activities(campaign, activity_type=activity_type)

        self._invalidate_campaign_caches(self.get_client_id())

        logger.info("campaign_generate_activities_success", extra={
            **ctx,
            'campaign_id': str(campaign.id),
            'activities_created': result['activities_created'],
        })

        return Response({
            'success': True,
            'data': result,
        })

    # ==========================================================================
    # LIST ACTIONS
    # ==========================================================================

    @action(detail=False, methods=['get'], url_path='my-campaigns')
    def my_campaigns(self, request):
        """
        Get campaigns where current user is a member.
        GET /campaigns/my-campaigns/
        """
        ctx = ctx_from_request(request)
        logger.info("my_campaigns_requested", extra=ctx)

        member_campaign_ids = CampaignMember.objects.filter(
            user=request.user,
            client_id=self.get_client_id(),
        ).values_list('campaign_id', flat=True)

        queryset = self.get_queryset().filter(id__in=member_campaign_ids)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CampaignListSerializer(page, many=True, context={'request': request})
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                },
            })

        serializer = CampaignListSerializer(queryset, many=True, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            },
        })