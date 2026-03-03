# app_modules/campaigns/views/campaign_member_views.py
"""
CampaignMemberViewSet — CRUD for campaign member management.

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

from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.cache_utils import invalidate_tag

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

from ..models import (
    CampaignMember,
)
from ..serializers import (
    CampaignMemberListSerializer,
    CampaignMemberSerializer,
)
from ..config.settings import CONFIG

logger = get_logger(__name__)


class CampaignMemberViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing Campaign Members.

    Endpoints:
        GET    /campaign-members/                   - List members
        POST   /campaign-members/                   - Add member
        GET    /campaign-members/{id}/              - Retrieve member
        PATCH  /campaign-members/{id}/              - Update member (role, is_primary_owner)
        DELETE /campaign-members/{id}/              - Remove member

        GET    /campaign-members/by-campaign/       - Filter by campaign_id
    """

    queryset = CampaignMember.objects.all()
    serializer_class = CampaignMemberSerializer
    entity_name = 'campaign_member'

    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'campaign': ['exact'],
        'user': ['exact'],
        'role': ['exact', 'in'],
        'is_primary_owner': ['exact'],
    }
    search_fields = CONFIG.filters.member_search
    ordering_fields = ['role', 'is_primary_owner', 'added_at', 'created_at']
    ordering = CONFIG.filters.default_member_ordering

    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'campaigns'

    # Action policies
    action_policies = {
        'by_campaign': {'crud': 'read', 'scope': 'client'},
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
            return CampaignMemberListSerializer
        return CampaignMemberSerializer

    # ==========================================================================
    # QUERYSET
    # ==========================================================================

    def get_queryset(self):
        """Get filtered queryset with optimized prefetching."""
        queryset = super().get_queryset()

        if self.action == 'list':
            queryset = queryset.select_related(
                'campaign', 'user', 'added_by',
            )
        elif self.action == 'retrieve':
            queryset = queryset.select_related(
                'campaign', 'user', 'added_by',
                'created_by', 'updated_by',
            )
        else:
            queryset = queryset.select_related('campaign', 'user')

        return queryset

    # ==========================================================================
    # LIST
    # ==========================================================================

    def list(self, request, *args, **kwargs):
        """
        List campaign members with pagination.
        GET /campaign-members/
        """
        ctx = ctx_from_request(request)
        logger.info("campaign_members_list_requested", extra=ctx)

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
        Retrieve a single campaign member.
        GET /campaign-members/{id}/
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("campaign_member_retrieved", extra={
            **ctx, 'campaign_member_id': str(instance.id),
        })

        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})

    # ==========================================================================
    # CREATE
    # ==========================================================================

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Add a member to a campaign.
        POST /campaign-members/

        Body:
            - campaign_id: UUID
            - user_id: UUID
            - role: OWNER | EXECUTOR | RECEIVER | OBSERVER
            - is_primary_owner: bool (optional, default false)
        """
        ctx = ctx_from_request(request)
        logger.info("campaign_member_create_requested", extra=ctx)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='campaign_member_added',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_member',
            target_id=str(instance.id),
            outcome='success',
            extra={
                'campaign_id': str(instance.campaign_id),
                'user_id': str(instance.user_id),
                'role': instance.role,
            },
        )

        self._invalidate_caches(self.get_client_id())

        logger.info("campaign_member_created", extra={
            **ctx,
            'campaign_member_id': str(instance.id),
            'role': instance.role,
        })

        # Return with full serializer for response
        output = CampaignMemberSerializer(instance, context={'request': request})
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
        Update campaign member (role, is_primary_owner).
        PATCH /campaign-members/{id}/

        Note: campaign_id and user_id are immutable after creation.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("campaign_member_update_requested", extra={
            **ctx, 'campaign_member_id': str(instance.id),
        })

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='campaign_member_updated',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_member',
            target_id=str(instance.id),
            outcome='success',
            extra={'role': instance.role, 'is_primary_owner': instance.is_primary_owner},
        )

        self._invalidate_caches(self.get_client_id())

        logger.info("campaign_member_updated", extra={
            **ctx, 'campaign_member_id': str(instance.id),
        })

        output = CampaignMemberSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': output.data})

    # ==========================================================================
    # DELETE
    # ==========================================================================

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Remove a member from a campaign.
        DELETE /campaign-members/{id}/

        Rules:
            - Cannot remove the primary owner
            - Campaign must have at least one OWNER after removal
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        # Cannot remove primary owner
        if instance.is_primary_owner:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CANNOT_REMOVE_PRIMARY_OWNER
            )

        # Ensure at least one owner remains
        if instance.role == CampaignMember.MemberRole.OWNER:
            remaining_owners = CampaignMember.objects.filter(
                campaign=instance.campaign,
                role=CampaignMember.MemberRole.OWNER,
            ).exclude(id=instance.id).count()

            if remaining_owners == 0:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.OWNER_REQUIRED
                )

        member_id = str(instance.id)
        campaign_id = str(instance.campaign_id)
        user_id = str(instance.user_id)
        role = instance.role

        logger.info("campaign_member_delete_requested", extra={
            **ctx, 'campaign_member_id': member_id,
        })

        instance.delete()

        audit_log(
            event='campaign_member_removed',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_member',
            target_id=member_id,
            outcome='success',
            extra={
                'campaign_id': campaign_id,
                'user_id': user_id,
                'role': role,
            },
        )

        self._invalidate_caches(self.get_client_id())

        logger.info("campaign_member_deleted", extra={
            **ctx, 'campaign_member_id': member_id,
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
        Get members for a specific campaign.
        GET /campaign-members/by-campaign/?campaign_id={uuid}
        """
        ctx = ctx_from_request(request)
        campaign_id = request.query_params.get('campaign_id')

        if not campaign_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='campaign_id')
            )

        logger.info("campaign_members_by_campaign_requested", extra={
            **ctx, 'campaign_id': campaign_id,
        })

        queryset = self.get_queryset().filter(campaign_id=campaign_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CampaignMemberListSerializer(
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

        serializer = CampaignMemberListSerializer(
            queryset, many=True, context={'request': request}
        )
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            },
        })