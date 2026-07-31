# backend/app_modules/territories/views/viewsets.py
"""
ViewSet for Territory module.

Follows CompanyAccountViewSet patterns for consistency.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Exists, OuterRef

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.cache_utils import invalidate_tag

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ..models import Territory, TerritoryType
from ..serializers import (
    TerritorySerializer,
    TerritoryListSerializer,
    TerritoryCreateSerializer,
    TerritoryUpdateSerializer,
)

logger = get_logger(__name__)


class TerritoryFilterSet(django_filters.FilterSet):
    """
    Filterset for the territory list.

    Standard exact filters plus a custom `team` filter matching territories
    whose OWNER belongs to the given team. Territory has no executor, so this
    is owner__team only (unlike CampaignFilterSet's owner-OR-executor).
    """

    team = django_filters.CharFilter(method='filter_team')

    class Meta:
        model = Territory
        fields = {
            'type': ['exact'],
            'is_system': ['exact'],
            'is_default': ['exact'],
            'owner': ['exact'],
        }

    def filter_team(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(owner__team_id=value)


class TerritoryViewSet(OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing territories with client scoping.
    
    Features:
    - Client-scoped data isolation (multi-tenant)
    - Permission-based access control
    - Structured logging + SOC 2 audit trail
    - Query optimization with annotations
    
    Endpoints:
        - GET    /territories/           - List all territories
        - POST   /territories/           - Create territory
        - GET    /territories/{id}/      - Retrieve territory
        - PUT    /territories/{id}/      - Update territory (full)
        - PATCH  /territories/{id}/      - Update territory (partial)
        - DELETE /territories/{id}/      - Delete territory
    
    Permissions:
        - Read: authenticated users (scoped to client)
        - Write/Update/Delete: according to permission registry
    """
    
    queryset = Territory.objects.all()
    serializer_class = TerritorySerializer
    entity_name = 'territory'
    
    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TerritoryFilterSet
    # Search is limited to the territory name and its owner's name. Territory
    # has no separate executor, so owner is the only person field.
    search_fields = ['name', 'owner__first_name', 'owner__last_name']
    ordering_fields = [
        'name',
        'type',
        'is_system',
        'is_default',
        'created_at',
        'updated_at',
    ]
    ordering = ['-created_at']
    
    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'territories'
    
    # Action policies for custom actions
    action_policies = {
        'accounts_count': {
            'crud': 'read',
            'scope': 'client'
        },
        'workspace': {
        'crud': 'read',
        'scope': 'client'
    },
}

    def get_serializer_class(self):
        """Choose serializer based on action."""
        if self.action == 'list':
            return TerritoryListSerializer
        elif self.action == 'create':
            return TerritoryCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TerritoryUpdateSerializer
        return TerritorySerializer
    
    def get_queryset(self):
        """Get territories with optimized queries."""
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'TerritoryViewSet'
        })
        
        queryset = super().get_queryset()
        
        # Optimize based on action
        if self.action == 'list':
            # Campaign is imported locally to avoid a circular import at module
            # load. is_in_active_campaign is a single Exists subquery for the
            # whole page (no per-territory query); owner__team backs the cheap
            # team field on the list serializer.
            from app_modules.campaigns.models import Campaign, CampaignStatus

            active_campaign = Campaign.objects.filter(
                territories=OuterRef('pk'),
                status=CampaignStatus.ACTIVE,
            )
            queryset = queryset.select_related('owner', 'owner__team').annotate(
                _is_in_active_campaign=Exists(active_campaign),
            )
        elif self.action == 'retrieve':
            queryset = queryset.select_related(
                'owner',
                'created_by',
                'updated_by'
            )
        else:
            queryset = queryset.select_related('owner')

        # Apply owner scope filter (mine/team/all)
        queryset = self.apply_owner_scope_filter(queryset)
        
        return queryset
    
    def _invalidate_all_related_caches(self, client_id):
        """
        Invalidate all caches related to territories.
        
        Args:
            client_id: Client UUID
        """
        if not client_id:
            return
        
        invalidate_tag(client_id, 'territories')
        
        logger.info('cache_invalidation_territories', extra={
            'event': 'cache_invalidation',
            'client_id': str(client_id),
            'tags': ['territories']
        })
    
    # ==========================================================================
    # CRUD OVERRIDES
    # ==========================================================================
    
    def list(self, request, *args, **kwargs):
        """
        List territories with pagination.
        
        Returns paginated list of territories for current client.
        """
        ctx = ctx_from_request(request)
        logger.info("territory_list_requested", extra=ctx)
        
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            
            logger.info("territory_list_success", extra={
                **ctx,
                'count': response.data.get('count', 0)
            })
            
            return Response({
                'success': True,
                'data': response.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single territory.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        logger.info("territory_retrieve_success", extra={
            **ctx,
            'territory_id': str(instance.id)
        })
        
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """
        Create a new territory.
        """
        ctx = ctx_from_request(request)
        logger.info("territory_create_requested", extra=ctx)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            instance = serializer.save()
            
            # Audit log
            audit_log(
            event='territory_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='territory',
            target_id=str(instance.id),
            outcome='success',
            extra={'territory_name': instance.name}
        )
            
            # Invalidate cache after commit
            client_id = self.get_client_id()
            transaction.on_commit(lambda: self._invalidate_all_related_caches(client_id))
                
        logger.info("territory_create_success", extra={
            **ctx,
            'territory_id': str(instance.id),
            'territory_name': instance.name
        })
        
        # Return with detail serializer
        output_serializer = TerritorySerializer(instance)
        return Response({
            'success': True,
            'data': output_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """
        Update a territory (PUT).
        """
        return self._perform_update(request, partial=False, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """
        Partial update a territory (PATCH).
        """
        return self._perform_update(request, partial=True, *args, **kwargs)
    
    def _perform_update(self, request, partial=False, *args, **kwargs):
        """
        Common update logic for PUT and PATCH.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        # Prevent modification of system territories
        if instance.is_system:
            raise StandardizedValidationError(
                'Cannot modify system territory.',
                code='system_territory_update'
            )
        
        logger.info("territory_update_requested", extra={
            **ctx,
            'territory_id': str(instance.id),
            'partial': partial
        })
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            instance = serializer.save()
            
            # Audit log
            audit_log(
                event='territory_update_success',
                action='partial_update',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='territory',
                target_id=str(instance.id),
                outcome='success',
                extra={'territory_name': instance.name}
            )

            # Invalidate cache after commit
            client_id = self.get_client_id()
            transaction.on_commit(lambda: self._invalidate_all_related_caches(client_id))
        
        logger.info("territory_update_success", extra={
            **ctx,
            'territory_id': str(instance.id)
        })
        
        # Return with detail serializer
        output_serializer = TerritorySerializer(instance)
        return Response({
            'success': True,
            'data': output_serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a territory, conditional on the campaigns that use it.

        Campaign→Territory is a M2M (Campaign.territories, related_name
        'campaigns'); TARGETED campaigns never carry a territory. Rules:
          - Linked to >=1 ACTIVE campaign -> blocked (4xx, clear message).
          - Linked only to NON-active campaigns:
              * a NON-active OUTBOUND campaign whose SOLE territory is this one
                -> cascade-deleted (campaign + CampaignAccount/CampaignContact);
                its activities are never deleted — pending non-DC ones are
                cancelled, everything else is kept, all detached via SET_NULL;
              * any other linked campaign (multi-territory, or — defensively —
                non-OUTBOUND) -> the territory is removed from it (M2M detach),
                the campaign is kept.
          - Linked to no campaign -> simple delete.
        TARGETED is never deleted: it never carries a territory, and the cascade
        branch is guarded on campaign_type == OUTBOUND. The whole operation is
        atomic — a mid-cascade failure rolls everything back.
        """
        from app_modules.campaigns.constants import CampaignStatus, CampaignType

        ctx = ctx_from_request(request)
        instance = self.get_object()

        # System territories are never deletable.
        if instance.is_system:
            raise StandardizedValidationError(
                CoreErrorMessages.CANNOT_DELETE.format(fields='system territories')
            )

        # Reverse M2M — every campaign that lists this territory as a source.
        linked_campaigns = list(instance.campaigns.all())

        # Rule 1 — any ACTIVE campaign blocks deletion.
        if any(c.status == CampaignStatus.ACTIVE for c in linked_campaigns):
            raise StandardizedValidationError(
                CoreErrorMessages.TERRITORY_DELETE_ACTIVE_CAMPAIGN
            )

        logger.info("territory_delete_requested", extra={
            **ctx,
            'territory_id': str(instance.id),
            'territory_name': instance.name,
            'linked_campaigns': len(linked_campaigns),
        })

        territory_id = str(instance.id)
        territory_name = instance.name
        client_id = self.get_client_id()

        cascaded, detached = 0, 0
        with transaction.atomic():
            for campaign in linked_campaigns:
                is_sole_territory = campaign.territories.count() == 1
                if is_sole_territory and campaign.campaign_type == CampaignType.OUTBOUND:
                    # This territory is the campaign's only source → the campaign
                    # cannot survive without it → cascade-delete it.
                    self._cascade_delete_outbound_campaign(campaign, request.user)
                    cascaded += 1
                else:
                    # Multi-territory (or, defensively, TARGETED) → detach only.
                    campaign.territories.remove(instance)
                    detached += 1

            instance.delete()

            audit_log(
                event='territory_delete_success',
                action='delete',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_id=territory_id,
                extra={
                    'territory_name': territory_name,
                    'campaigns_cascaded': cascaded,
                    'campaigns_detached': detached,
                },
                outcome='success',
            )

            # Invalidate cache after commit
            transaction.on_commit(lambda: self._invalidate_all_related_caches(client_id))

        logger.info("territory_delete_success", extra={
            **ctx,
            'territory_id': territory_id,
            'territory_name': territory_name,
        })

        return Response({
            'success': True,
            'message': f'Territory "{territory_name}" deleted successfully.'
        }, status=status.HTTP_200_OK)

    def _cascade_delete_outbound_campaign(self, campaign, user):
        """
        Cascade-delete a NON-active OUTBOUND campaign whose sole territory is
        being removed.

        Activities are NEVER deleted (locked rule). Pending activities not tied
        to a decision cycle are marked CANCELLED and kept; already-terminal
        activities and DC-linked activities are left untouched. All of them are
        then detached (campaign/campaign_account/campaign_contact -> NULL) via
        the existing SET_NULL when the campaign (and its CASCADE-linked
        CampaignAccount/CampaignContact) is removed.

        Must run inside a transaction (the caller wraps it) so a failure leaves
        no half-deleted state.
        """
        from django.utils import timezone
        from app_modules.activities.models import Activity, ActivityStatus

        # Cancel (never delete) pending non-DC activities; everything else is
        # left untouched. The campaign delete below detaches the survivors.
        Activity.objects.filter(
            campaign=campaign,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
            decision_cycle__isnull=True,
        ).update(status=ActivityStatus.CANCELLED, updated_at=timezone.now())

        # CASCADE removes CampaignAccount + CampaignContact; every activity is
        # detached (campaign/campaign_account/campaign_contact -> NULL) but
        # preserved, DC-linked ones with their decision_cycle intact.
        campaign.delete()

    # ==========================================================================
    # CUSTOM ACTIONS
    # ==========================================================================
    
    @action(detail=True, methods=['get'], url_path='accounts-count')
    def accounts_count(self, request, pk=None):
        """
        Get the count of accounts matching this territory's filters.
        
        This is a placeholder - actual implementation will query accounts
        with the territory's filter_definition.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        # TODO: Implement actual account counting based on filter_definition
        # For now, return 0 or implement basic counting
        
        logger.info("territory_accounts_count_requested", extra={
            **ctx,
            'territory_id': str(instance.id)
        })
        
        # Placeholder response
        return Response({
            'success': True,
            'data': {
                'territory_id': str(instance.id),
                'territory_name': instance.name,
                'accounts_count': 0,  # TODO: Calculate from filter_definition
                'filter_definition': instance.filter_definition
            }
        })
    
    @action(detail=True, methods=['get'], url_path='workspace')
    def workspace(self, request, pk=None):
        """
        Get territory workspace data.
        
        Returns territory details + stats for the workspace page.
        Handles both ACCOUNT and CONTACT territory types.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        logger.info("territory_workspace_requested", extra={
            **ctx,
            'territory_id': str(instance.id),
            'territory_type': instance.type
        })
        
        # Get territory data
        serializer = TerritorySerializer(instance)
        
        # Calculate stats based on territory type
        accounts_count = 0
        contacts_count = 0
        
        if instance.type == TerritoryType.ACCOUNT:
            # Account territory - count accounts
            accounts_count = self._count_accounts_for_territory(instance, request)
        else:
            # Contact territory - count contacts
            contacts_count = self._count_contacts_for_territory(instance, request)
        
        stats = {
            'accounts_count': accounts_count,
            'contacts_count': contacts_count,
            'activities_count': 0,  # TODO: Connect to activities module
        }
        
        logger.info("territory_workspace_success", extra={
            **ctx,
            'territory_id': str(instance.id),
            'territory_type': instance.type,
            'accounts_count': accounts_count,
            'contacts_count': contacts_count
        })
        
        return Response({
            'success': True,
            'data': {
                'territory': serializer.data,
                'stats': stats
            }
        })

    def _count_accounts_for_territory(self, territory, request):
        """
        Count accounts matching the territory's filter_definition.

        Delegates to AccountFilterService — the same canonical evaluator used by
        territory coverage — so card, coverage, and workspace counts share one
        source. Scope keys (account_scope mine/team) resolve against the
        territory owner, matching the coverage core rather than the requester,
        so the count is deterministic per territory regardless of who views it.
        """
        from app_modules.accounts.models import CompanyAccount
        from app_modules.accounts.services.filter_service import AccountFilterService

        client_id = self.get_client_id()
        base = CompanyAccount.objects.filter(client_id=client_id)
        accounts = AccountFilterService.apply_filters(
            base, territory.filter_definition or {},
            client_id=client_id, user=territory.owner,
        )
        return accounts.count()

    def _count_contacts_for_territory(self, territory, request):
        """
        Count contacts matching the territory's filter_definition.

        Delegates to ContactFilterService so workspace and the batched counts
        endpoint share one evaluator. Scope keys resolve against the territory
        owner (see _count_accounts_for_territory).
        """
        from app_modules.contacts.models import Contact
        from app_modules.contacts.services.filter_service import ContactFilterService

        base = Contact.objects.filter(client_id=self.get_client_id())
        contacts = ContactFilterService.apply_filters(
            base, territory.filter_definition or {},
            user=territory.owner,
        )
        return contacts.count()
    
    @action(detail=False, methods=['get'], url_path='choices')
    def choices(self, request):
        """
        Get available choices for territory fields.
        
        Returns type choices for frontend dropdowns.
        """
        ctx = ctx_from_request(request)
        logger.info("territory_choices_requested", extra=ctx)
        
        return Response({
            'success': True,
            'data': {
                'type': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in TerritoryType.choices
                ]
            }
        })
