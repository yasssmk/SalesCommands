# app_modules/campaigns/views/campaign_views.py
"""
CampaignViewSet — CRUD + lifecycle actions + dashboard + playlist.

Follows ActivityViewSet / TerritoryViewSet patterns:
    - BaseAPIView + ScopedQuerysetMixin + OwnerScopeMixin
    - Response({'success': True, 'data': ...})
    - Redis caching with tag invalidation
    - Structured logging + SOC 2 audit trail
"""

import django_filters

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import (
    Count, Q, OuterRef, Subquery, Exists,
    Case, When, Value, IntegerField,
)
from django.utils import timezone
from datetime import timedelta

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
    CampaignType,
    CampaignStatus,
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
from app_modules.activities.models import Activity, ActivityStatus
from ..config.settings import CONFIG

logger = get_logger(__name__)


class CampaignFilterSet(django_filters.FilterSet):
    """
    Filterset for the campaign list.

    Standard exact filters plus a custom `team` filter that matches a
    campaign whose OWNER or EXECUTOR belongs to the given team (OR). A team
    view thus surfaces campaigns a colleague executes, not only those the
    team owns.
    """

    team = django_filters.CharFilter(method='filter_team')

    class Meta:
        model = Campaign
        fields = {
            'status': ['exact', 'in'],
            'campaign_type': ['exact'],
            'territories': ['exact'],
            'owner': ['exact'],
            'executor': ['exact'],
            'channel_override': ['exact'],
        }

    def filter_team(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(owner__team_id=value) | Q(executor__team_id=value)
        ).distinct()


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
    filterset_class = CampaignFilterSet
    search_fields = CONFIG.filters.campaign_search
    ordering_fields = ['name', 'status', 'campaign_type', 'start_date', 'end_date', 'created_at']
    ordering = CONFIG.filters.default_campaign_ordering

    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'campaigns'

    # Action policies
    action_policies = {
        'start': {'crud': 'update', 'scope': 'mine'},
        'pause': {'crud': 'update', 'scope': 'mine'},
        'resume': {'crud': 'update', 'scope': 'mine'},
        'complete': {'crud': 'update', 'scope': 'mine'},
        'cancel': {'crud': 'update', 'scope': 'mine'},
        'dashboard': {'crud': 'read', 'scope': 'client'},
        'summary': {'crud': 'read', 'scope': 'client'},
        'playlist': {'crud': 'read', 'scope': 'client'},
        'generate_activities': {'crud': 'update', 'scope': 'client'},
        'log_response': {'crud': 'create', 'scope': 'mine'},
        'cancel_planned': {'crud': 'delete', 'scope': 'mine'},
        'my_campaigns': {'crud': 'read', 'scope': 'mine'},
        'get_or_create_targeted': {'crud': 'read', 'scope': 'client'},
    }

    # ==========================================================================
    # CACHE HELPERS
    # ==========================================================================

    def _assert_not_targeted(self, campaign):
        """Raise 403 if campaign is TARGETED — lifecycle actions are not allowed."""
        if campaign.is_targeted:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.TARGETED_CAMPAIGN_LIFECYCLE_FORBIDDEN
            )

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

        # my_campaigns serializes with CampaignListSerializer and calls
        # filter_queryset too, so it must carry the SAME annotations as list —
        # notably _status_priority, which the default ordering
        # (['_status_priority', '-created_at']) orders by. Without it the
        # OrderingFilter raised FieldError -> 400. Folding it in here also
        # restores _accounts_count / _targets_total for its cards (the else
        # branch had neither). The else branch keeps its own owner__team join
        # for other list-style actions — now redundant for my_campaigns, left
        # as-is to avoid touching those actions.
        if self.action in ('list', 'my_campaigns'):
            # owner__team / executor__team join the attribution the list
            # serializer exposes (owner + team, executor + team) — without it
            # each card would trigger an N+1 into the team table.
            #
            # Target progress (targets_total / targets_worked) is counted with
            # SEPARATE correlated subqueries, NOT a Count over
            # campaign_accounts__campaign_contacts in this .annotate(). A deeper
            # Count would LEFT JOIN campaign_accounts × campaign_contacts and
            # multiply rows (A accounts × C contacts) per campaign, inflating the
            # intermediate result and forcing distinct= gymnastics on
            # _accounts_count. Isolated subqueries never join the outer FROM, so
            # every count stays exact — the same Subquery shape the retrieve
            # branch already uses (_expected_end_date). worked counts targets in
            # a final state (COMPLETED/STOPPED) via a filtered Count on the real
            # CampaignContact.status column. Coalesce → 0 because a GROUP BY
            # subquery returns no row (NULL) for a campaign with no contacts.
            from ..models import CampaignContact, FINAL_CONTACT_STATES
            from django.db.models.functions import Coalesce
            from app_modules.activities.models import Activity as _Activity
            from app_modules.activities.constants import ActivityStatus as _AS

            _contacts = CampaignContact.objects.filter(
                campaign_account__campaign=OuterRef('pk'),
            ).order_by().values('campaign_account__campaign')
            _total_sq = _contacts.annotate(c=Count('pk')).values('c')[:1]
            _worked_sq = _contacts.annotate(
                c=Count('pk', filter=Q(status__in=FINAL_CONTACT_STATES)),
            ).values('c')[:1]

            # "N activities to do today" — the SAME number the rep sees on the
            # playlist's "To do today" chip (CampaignPlaylistTab.todayActivities)
            # and get_playlist's today bucket. Card and chip must never disagree,
            # so the rule below reuses the chip's criterion verbatim. An Activity
            # counts iff:
            #   - status = PLANNED (ON_HOLD is bucketed separately, never counts),
            #   - date-eligible: scheduled_date IS NULL OR <= today (overdue ARE
            #     included — the max(scheduled_date, today) clamp is display-only),
            #   - first-planned for its contact: campaign_contact IS NULL, OR a
            #     callback, OR sequence_position IS NULL, OR no earlier PLANNED
            #     non-callback step of the same contact exists. That last clause
            #     is the complement of "superseded", expressed as ~Exists —
            #     mirroring only_next_pending_campaign_steps (todo_rules.py).
            # Campaign-wide (executor=None), matching the playlist's default view.
            # Isolated correlated subquery (same shape as _targets_total): it
            # filters Activity by campaign=OuterRef('pk') and never joins
            # campaign_accounts, so it neither multiplies rows nor skews
            # _accounts_count.
            _today = timezone.now().date()
            _earlier_pending_step = _Activity.objects.filter(
                campaign_contact_id=OuterRef('campaign_contact_id'),
                status=_AS.PLANNED,
                is_callback_followup=False,
                sequence_position__lt=OuterRef('sequence_position'),
            )
            _today_acts_sq = (
                _Activity.objects.filter(
                    campaign=OuterRef('pk'),
                    status=_AS.PLANNED,
                )
                .filter(
                    Q(scheduled_date__isnull=True) | Q(scheduled_date__lte=_today)
                )
                .filter(
                    Q(campaign_contact__isnull=True)
                    | Q(is_callback_followup=True)
                    | Q(sequence_position__isnull=True)
                    | ~Exists(_earlier_pending_step)
                )
                .order_by()
                .values('campaign')
                .annotate(c=Count('pk'))
                .values('c')[:1]
            )

            queryset = queryset.select_related(
                'owner__team', 'executor__team',
            ).prefetch_related(
                'territories',
                'objectives',
            ).annotate(
                _accounts_count=Count('campaign_accounts', distinct=True),
                _targets_total=Coalesce(Subquery(_total_sq), 0),
                _targets_worked=Coalesce(Subquery(_worked_sq), 0),
                _activities_today=Coalesce(Subquery(_today_acts_sq), 0),
                # Default list order groups by status priority (see the ordering
                # default in config.settings). Values per CampaignStatus
                # (constants.py:40-44); an unknown/new status sorts last (5).
                _status_priority=Case(
                    When(status=CampaignStatus.ACTIVE, then=Value(0)),
                    When(status=CampaignStatus.PAUSED, then=Value(1)),
                    When(status=CampaignStatus.DRAFT, then=Value(2)),
                    When(status=CampaignStatus.COMPLETED, then=Value(3)),
                    When(status=CampaignStatus.CANCELLED, then=Value(4)),
                    default=Value(5),
                    output_field=IntegerField(),
                ),
            )
        elif self.action == 'retrieve':
            from app_modules.activities.models import Activity as _Activity
            from app_modules.activities.constants import ActivityStatus as _AS

            _threshold = timezone.now().date() - timedelta(
                days=CONFIG.limits.inactivity_threshold_days
            )

            queryset = queryset.select_related(
                'owner', 'executor',
                'created_by', 'updated_by',
            ).prefetch_related(
                'territories',
                'objectives',
                'campaign_accounts',
            ).annotate(
                _accounts_count=Count('campaign_accounts', distinct=True),
                _expected_end_date=Subquery(
                    _Activity.objects.filter(
                        campaign=OuterRef('pk'),
                        status=_AS.PLANNED,
                    ).order_by('-scheduled_date').values('scheduled_date')[:1]
                ),
                _is_inactive=~Exists(
                    _Activity.objects.filter(
                        campaign=OuterRef('pk'),
                        status=_AS.COMPLETED,
                        completed_at__date__gte=_threshold,
                    )
                ),
            )
        else:
            # my-campaigns and other list-style actions serialize with
            # CampaignListSerializer too — carry the same owner/executor team
            # joins so the attribution block never N+1s.
            queryset = queryset.select_related(
                'owner__team', 'executor__team',
            ).prefetch_related('territories')

        # Apply owner scope filter (mine/team/all)
        queryset = self.apply_owner_scope_filter(queryset)

        queryset = queryset.exclude(
            campaign_type=CampaignType.TARGETED,
        ) | queryset.filter(
            campaign_type=CampaignType.TARGETED,
            owner=self.request.user,
        )

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

    def _primary_progress_map(self, campaigns):
        """Batch-compute each campaign's primary-objective advancement.

        One bounded pass (grouped by objective_type) so the card's list never
        does one calculation query per campaign. Mirrors the quotas list, which
        precomputes attainment in a single batch and hands it to the serializer
        via context.
        """
        from ..services.campaign_objective_progress import (
            compute_primary_objective_progress_batch,
        )
        return compute_primary_objective_progress_batch(
            campaigns, self.get_client_id()
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        progress_map = getattr(self, '_primary_objective_progress', None)
        if progress_map is not None:
            context['primary_objective_progress'] = progress_map
        return context

    def _list_uncached_data(self, request):
        """Produce list data dict (cache-friendly)."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            self._primary_objective_progress = self._primary_progress_map(page)
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

        objects = list(queryset)
        self._primary_objective_progress = self._primary_progress_map(objects)
        serializer = self.get_serializer(objects, many=True)
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

        Any campaign can be deleted. All linked activities are cascade-deleted.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()
        self._assert_not_targeted(instance)

        campaign_id = str(instance.id)
        campaign_name = instance.name

        logger.info("campaign_delete_requested", extra={
            **ctx,
            'campaign_id': campaign_id,
        })

        # Cascade-delete all activities linked to this campaign
        # (Activity.campaign FK is SET_NULL, so we must delete explicitly)
        deleted_activities_count, _ = Activity.objects.filter(campaign=instance).delete()

        instance.delete()

        audit_log(
            event='campaign_delete_success',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign',
            target_id=campaign_id,
            outcome='success',
            extra={
                'campaign_name': campaign_name,
                'activities_deleted': deleted_activities_count,
            },
        )

        client_id = self.get_client_id()
        self._invalidate_campaign_caches(client_id)

        logger.info("campaign_delete_success", extra={
            **ctx,
            'campaign_id': campaign_id,
            'activities_deleted': deleted_activities_count,
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
        self._assert_not_targeted(campaign)

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
        self._assert_not_targeted(campaign)

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
            'data': {
                'campaign': output.data,
                'activities_paused': result['activities_paused'],
            },
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
        self._assert_not_targeted(campaign)

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
                'activities_resumed': result['activities_resumed'],
                'callbacks_resumed': result['callbacks_resumed'],
            },
        })


    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        """
        Complete campaign: ACTIVE/PAUSED → COMPLETED.
        POST /campaigns/{id}/complete/

        Two-phase completion:
            - First call (no force): returns open contacts without completing.
              Frontend shows confirmation modal.
            - Second call (force=true): completes unconditionally.

        Body (optional):
            - force: bool — confirm completion despite open contacts
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()
        self._assert_not_targeted(campaign)

        force = bool(request.data.get('force', False))

        logger.info("campaign_complete_requested", extra={
            **ctx, 'campaign_id': str(campaign.id), 'force': force,
        })

        service = CampaignLifecycleService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.complete(campaign, force=force)

        self._invalidate_campaign_caches(self.get_client_id())

        open_contacts = result.get('open_contacts', [])
        completed = result.get('completed', False)
        output = CampaignDetailSerializer(result['campaign'], context={'request': request})

        return Response({
            'success': True,
            'data': {
                'campaign': output.data,
                'completed': completed,
                'requires_confirmation': not completed and len(open_contacts) > 0,
                'open_contacts': open_contacts,
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
        self._assert_not_targeted(campaign)

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
    
    @action(detail=False, methods=['get'], url_path='targeted')
    def get_or_create_targeted(self, request):
        """
        Get or create the TARGETED singleton campaign for this client.

        GET /campaigns/targeted/?sequence_type=TARGETED

        Returns the campaign (existing or newly created) always in ACTIVE status.
        The frontend uses this to navigate directly to the TARGETED workspace.
        """
        ctx = ctx_from_request(request)
        sequence_type = request.query_params.get('sequence_type', 'TARGETED')

        logger.info("targeted_campaign_requested", extra={
            **ctx, 'sequence_type': sequence_type,
        })

        service = CampaignCreationService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        campaign, created = service.get_or_create_targeted(sequence_type=sequence_type)

        if created:
            self._invalidate_campaign_caches(self.get_client_id())

        output = CampaignDetailSerializer(campaign, context={'request': request})
        return Response({
            'success': True,
            'data': output.data,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

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

        # Optional result limit — default 200, clamped to [1, 500]. Applied
        # AFTER the service's priority sort so top-priority activities are
        # never cut. total_count remains the pre-slice total.
        limit = 200
        limit_param = request.query_params.get('limit')
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except (TypeError, ValueError):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='limit')
                )
            limit = max(1, min(limit, 500))

        service = CampaignExecutionService(
            user=request.user,
            client_id=self.get_client_id(),
        )
        result = service.get_playlist(campaign, executor=executor)

        # Serialize activities (sliced to the limit, post-priority-sort)
        from app_modules.activities.serializers import ActivityListSerializer
        serializer = ActivityListSerializer(
            result['activities'][:limit], many=True, context={'request': request}
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
    
    @action(detail=True, methods=['post'], url_path='log-response')
    @transaction.atomic
    def log_response(self, request, pk=None):
        """
        Log an async response received from a contact (email reply, callback, LinkedIn, etc.).
        POST /campaigns/{id}/log-response/
        Body:
            - activity_id:     UUID  (required) — completed activity that triggered the response
            - response:        str   (required) — POSITIVE | NEGATIVE | MEETING_BOOKED |
                                                  CALLBACK_REQUESTED | NO_RESPONSE
            - response_date:   date  (optional) — required when response is MEETING_BOOKED
                                                  or CALLBACK_REQUESTED (YYYY-MM-DD)
            - notes:           str   (optional)
        Delegates entirely to CampaignExecutionService.process_result():
        updates activity outcome, CampaignAccount state, and cancels downstream
        sequence activities when the outcome is terminal.
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()
        client_id = self.get_client_id()

        # --- Validate required fields ---
        activity_id = request.data.get('activity_id')
        response = request.data.get('response')
        response_date = request.data.get('response_date')
        callback_time = request.data.get('callback_time')
        notes = request.data.get('notes', '')

        if not activity_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='activity_id')
            )
        if not response:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='response')
            )

        try:
            activity = Activity.objects.select_related(
                'campaign_account',
                'campaign_contact',
            ).get(
                id=activity_id,
                campaign=campaign,
                client_id=client_id,
            )
        except Activity.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        if activity.status == ActivityStatus.CANCELLED:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.EXECUTION_FAILED.format(
                    reason="Cannot log a response on a cancelled activity"
                )
            )

        # --- Map response → outcome ---
        outcome = CONFIG.validation.response_to_outcome.get(response, 'OTHER')

        # --- Process result via service (handles outcome + CampaignAccount + sequence cancellation) ---
        service = CampaignExecutionService(
            user=request.user,
            client_id=str(client_id),
        )
        service.process_result(activity, {
            'outcome': outcome,
            'outcome_notes': notes or None,
            'callback_date': response_date if response == 'CALLBACK_REQUESTED' else None,
            'callback_time': callback_time if response == 'CALLBACK_REQUESTED' else None,
        })

        self._invalidate_campaign_caches(client_id)

        audit_log(
            event='campaign_response_logged',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='activity',
            target_id=str(activity.id),
            outcome='success',
            extra={
                'campaign_id': str(campaign.id),
                'response': response,
                'outcome': outcome,
            },
        )

        logger.info("campaign_response_logged", extra={
            **ctx,
            'campaign_id': str(campaign.id),
            'activity_id': str(activity.id),
            'response': response,
        })

        return Response({
            'success': True,
            'data': {
                'activity_id': str(activity.id),
                'response': response,
                'outcome': outcome,
            },
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['delete'], url_path='cancel-planned')
    @transaction.atomic
    def cancel_planned(self, request, pk=None):
        """
        Cancel all PLANNED activities for a contact, a department, or an entire account.
        DELETE /campaigns/{id}/cancel-planned/
        Body:
            - scope:         str   'contact' | 'department' | 'account'  (required)
            - account_id:    UUID  (required)
            - contact_id:    UUID  (required when scope = 'contact')
            - department_id: int   (required when scope = 'department')
        """
        ctx = ctx_from_request(request)
        campaign = self.get_object()
        client_id = self.get_client_id()

        scope = request.data.get('scope')
        account_id = request.data.get('account_id')
        contact_id = request.data.get('contact_id')
        department_id = request.data.get('department_id')

        if scope not in ('contact', 'department', 'account'):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='scope (contact|department|account)')
            )
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='account_id')
            )
        if scope == 'contact' and not contact_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='contact_id')
            )
        if scope == 'department' and not department_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='department_id')
            )

        from app_modules.accounts.models import CompanyAccount
        from app_modules.contacts.models import Contact

        # Validate account belongs to this client
        try:
            account = CompanyAccount.objects.get(id=account_id, client_id=client_id)
        except CompanyAccount.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        # Validate contact belongs to this account (scope = contact)
        if scope == 'contact':
            try:
                Contact.objects.get(id=contact_id, account=account, client_id=client_id)
            except Contact.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        qs = Activity.objects.filter(
            campaign=campaign,
            account=account,
            client_id=client_id,
            status=ActivityStatus.PLANNED,
        )

        if scope == 'contact':
            qs = qs.filter(contacts__id=contact_id)
        elif scope == 'department':
            qs = qs.filter(contacts__standard_department_id=department_id)

        cancelled_count = qs.update(
            status=ActivityStatus.CANCELLED,
            outcome_notes='Manually cancelled after terminal response',
            updated_at=timezone.now(),
        )

        if cancelled_count == 0:
            logger.warning("campaign_cancel_planned_no_activities", extra={
                **ctx,
                'campaign_id': str(campaign.id),
                'scope': scope,
                'account_id': str(account_id),
            })

        # --- Sync CampaignContact status after bulk cancellation ---
        # Find contacts affected by this scope that are not yet in a final state
        from ..models import CampaignContact, CampaignContactStatus, FINAL_CONTACT_STATES
        from app_modules.accounts.models import CompanyAccount as _CA

        cc_qs = CampaignContact.objects.filter(
            campaign_account__campaign=campaign,
            campaign_account__account=account,
        ).exclude(status__in=FINAL_CONTACT_STATES).select_related('campaign_account')

        if scope == 'contact':
            cc_qs = cc_qs.filter(contact_id=contact_id)
        elif scope == 'department':
            cc_qs = cc_qs.filter(contact__standard_department_id=department_id)

        execution_service = CampaignExecutionService(
            user=request.user,
            client_id=str(client_id),
        )

        affected_campaign_accounts = set()
        for cc in cc_qs:
            # Only stop contacts that have no PLANNED activities left
            has_planned = Activity.objects.filter(
                campaign_contact=cc,
                status=ActivityStatus.PLANNED,
            ).exists()
            if not has_planned:
                cc.mark_stopped(
                    user=request.user,
                    notes="All planned activities cancelled",
                )
                affected_campaign_accounts.add(cc.campaign_account)

        for ca in affected_campaign_accounts:
            execution_service._check_account_completion(ca)

        self._invalidate_campaign_caches(client_id)

        audit_log(
            event='campaign_planned_activities_cancelled',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign',
            target_id=str(campaign.id),
            outcome='success',
            extra={
                'scope': scope,
                'account_id': str(account_id),
                'contact_id': str(contact_id) if contact_id else None,
                'department_id': str(department_id) if department_id else None,
                'cancelled_count': cancelled_count,
            },
        )

        logger.info("campaign_planned_activities_cancelled", extra={
            **ctx,
            'campaign_id': str(campaign.id),
            'scope': scope,
            'cancelled_count': cancelled_count,
        })

        return Response({
            'success': True,
            'data': {
                'cancelled_count': cancelled_count,
                'scope': scope,
            },
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

        
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            context = {
                'request': request,
                'primary_objective_progress': self._primary_progress_map(page),
            }
            serializer = CampaignListSerializer(page, many=True, context=context)
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                },
            })

        objects = list(queryset)
        context = {
            'request': request,
            'primary_objective_progress': self._primary_progress_map(objects),
        }
        serializer = CampaignListSerializer(objects, many=True, context=context)
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            },
        })