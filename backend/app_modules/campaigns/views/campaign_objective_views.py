# app_modules/campaigns/views/campaign_objective_views.py
"""
CampaignObjectiveViewSet — CRUD for campaign objective management.

Follows ActivityViewSet / TerritoryViewSet patterns:
    - BaseAPIView + ScopedQuerysetMixin
    - Response({'success': True, 'data': ...})
    - Structured logging + SOC 2 audit trail
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.cache_utils import invalidate_tag

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

from ..models import (
    CampaignObjective,
    ObjectiveType,
)
from ..serializers import (
    CampaignObjectiveListSerializer,
    CampaignObjectiveSerializer,
)
from ..config.settings import CONFIG

logger = get_logger(__name__)


class CampaignObjectiveViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing Campaign Objectives.

    Endpoints:
        GET    /campaign-objectives/                    - List objectives
        POST   /campaign-objectives/                    - Create objective
        GET    /campaign-objectives/{id}/               - Retrieve objective
        PATCH  /campaign-objectives/{id}/               - Update objective
        DELETE /campaign-objectives/{id}/               - Delete objective

        GET    /campaign-objectives/by-campaign/        - Filter by campaign_id
        GET    /campaign-objectives/choices/            - Objective type choices
    """

    queryset = CampaignObjective.objects.all()
    serializer_class = CampaignObjectiveSerializer
    entity_name = 'campaign_objective'

    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'campaign': ['exact'],
        'objective_type': ['exact', 'in'],
        'is_primary': ['exact'],
    }
    search_fields = ['name']
    ordering_fields = ['name', 'objective_type', 'target_value', 'is_primary', 'created_at']
    ordering = CONFIG.filters.default_objective_ordering

    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'campaigns'

    # Action policies
    action_policies = {
        'by_campaign': {'crud': 'read', 'scope': 'client'},
        'choices': {'crud': 'read', 'scope': 'client'},
    }

    # ==========================================================================
    # CACHE HELPERS
    # ==========================================================================

    def _invalidate_caches(self, client_id):
        """Invalidate campaign-related caches."""
        client_id_str = str(client_id)
        invalidate_tag(client_id_str, 'campaigns')

    # ==========================================================================
    # SERIALIZER SELECTION
    # ==========================================================================

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return CampaignObjectiveListSerializer
        return CampaignObjectiveSerializer

    # ==========================================================================
    # QUERYSET
    # ==========================================================================

    def get_queryset(self):
        """Get filtered queryset with optimized prefetching."""
        queryset = super().get_queryset()

        if self.action in ['list', 'retrieve']:
            queryset = queryset.select_related('campaign')

        if self.action == 'retrieve':
            queryset = queryset.select_related(
                'campaign', 'created_by', 'updated_by',
            )

        return queryset

    # ==========================================================================
    # LIST
    # ==========================================================================

    def list(self, request, *args, **kwargs):
        """
        List campaign objectives with pagination.
        GET /campaign-objectives/
        """
        ctx = ctx_from_request(request)
        logger.info("campaign_objectives_list_requested", extra=ctx)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                },
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            },
        })

    # ==========================================================================
    # RETRIEVE
    # ==========================================================================

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single campaign objective with computed progress.
        GET /campaign-objectives/{id}/
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("campaign_objective_retrieved", extra={
            **ctx, 'campaign_objective_id': str(instance.id),
        })

        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})

    # ==========================================================================
    # CREATE
    # ==========================================================================

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a campaign objective.
        POST /campaign-objectives/

        Body:
            - campaign_id: UUID
            - name: str
            - objective_type: MEETINGS | DECISION_CYCLES | CONTACTS_REACHED |
                              PIPELINE_VALUE | REVENUE_WON | NEW_LOGOS
            - target_value: decimal (> 0)
            - is_primary: bool (optional, default false)
        """
        ctx = ctx_from_request(request)
        logger.info("campaign_objective_create_requested", extra=ctx)

        # Check max objectives limit
        campaign_id = request.data.get('campaign_id')
        if campaign_id:
            current_count = CampaignObjective.objects.filter(
                campaign_id=campaign_id,
                client_id=self.get_client_id(),
            ).count()
            if current_count >= CONFIG.limits.max_objectives_per_campaign:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.MAX_OBJECTIVES_EXCEEDED.format(
                        max=CONFIG.limits.max_objectives_per_campaign
                    )
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='campaign_objective_created',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_objective',
            target_id=str(instance.id),
            outcome='success',
            extra={
                'campaign_id': str(instance.campaign_id),
                'objective_type': instance.objective_type,
                'target_value': float(instance.target_value),
                'is_primary': instance.is_primary,
            },
        )

        self._invalidate_caches(self.get_client_id())

        logger.info("campaign_objective_created", extra={
            **ctx,
            'campaign_objective_id': str(instance.id),
            'objective_type': instance.objective_type,
        })

        output = CampaignObjectiveSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': output.data,
        }, status=status.HTTP_201_CREATED)

    # ==========================================================================
    # UPDATE
    # ==========================================================================

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """
        Update campaign objective (name, target_value, is_primary).
        PATCH /campaign-objectives/{id}/

        Note: campaign_id and objective_type are immutable after creation.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("campaign_objective_update_requested", extra={
            **ctx, 'campaign_objective_id': str(instance.id),
        })

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='campaign_objective_updated',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_objective',
            target_id=str(instance.id),
            outcome='success',
            extra={
                'target_value': float(instance.target_value),
                'is_primary': instance.is_primary,
            },
        )

        self._invalidate_caches(self.get_client_id())

        logger.info("campaign_objective_updated", extra={
            **ctx, 'campaign_objective_id': str(instance.id),
        })

        output = CampaignObjectiveSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': output.data})

    # ==========================================================================
    # DELETE
    # ==========================================================================

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a campaign objective.
        DELETE /campaign-objectives/{id}/

        Rules:
            - Cannot delete the only primary objective of an active campaign
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        # Protect primary objective on active campaigns
        if instance.is_primary and instance.campaign.status not in ('DRAFT', 'CANCELLED'):
            remaining_primary = CampaignObjective.objects.filter(
                campaign=instance.campaign,
                is_primary=True,
            ).exclude(id=instance.id).count()

            if remaining_primary == 0:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.CANNOT_DELETE_PRIMARY_OBJECTIVE
                )

        objective_id = str(instance.id)
        campaign_id = str(instance.campaign_id)
        objective_type = instance.objective_type

        logger.info("campaign_objective_delete_requested", extra={
            **ctx, 'campaign_objective_id': objective_id,
        })

        instance.delete()

        audit_log(
            event='campaign_objective_deleted',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_objective',
            target_id=objective_id,
            outcome='success',
            extra={
                'campaign_id': campaign_id,
                'objective_type': objective_type,
            },
        )

        self._invalidate_caches(self.get_client_id())

        logger.info("campaign_objective_deleted", extra={
            **ctx, 'campaign_objective_id': objective_id,
        })

        return Response({
            'success': True,
            'data': None,
        }, status=status.HTTP_204_NO_CONTENT)

    # ==========================================================================
    # LIST ACTIONS
    # ==========================================================================

    @action(detail=False, methods=['get'], url_path='by-campaign')
    def by_campaign(self, request):
        """
        Get objectives for a specific campaign.
        GET /campaign-objectives/by-campaign/?campaign_id={uuid}
        """
        ctx = ctx_from_request(request)
        campaign_id = request.query_params.get('campaign_id')

        if not campaign_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='campaign_id')
            )

        logger.info("campaign_objectives_by_campaign_requested", extra={
            **ctx, 'campaign_id': campaign_id,
        })

        queryset = self.get_queryset().filter(campaign_id=campaign_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CampaignObjectiveListSerializer(
                page, many=True, context={'request': request}
            )
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                },
            })

        serializer = CampaignObjectiveListSerializer(
            queryset, many=True, context={'request': request}
        )
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            },
        })

    @action(detail=False, methods=['get'])
    def choices(self, request):
        """
        Get available objective type choices.
        GET /campaign-objectives/choices/
        """
        ctx = ctx_from_request(request)
        logger.info("campaign_objective_choices_requested", extra=ctx)

        return Response({
            'success': True,
            'data': {
                'objective_types': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in ObjectiveType.choices
                ],
            },
        })