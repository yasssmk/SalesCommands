# backend/app_modules/territories/views/viewsets.py
"""
ViewSet for Territory module.

Follows CompanyAccountViewSet patterns for consistency.
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
    filterset_fields = {
        'type': ['exact'],
        'is_system': ['exact'],
        'is_default': ['exact'],
        'owner': ['exact'],
    }
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
    ordering = ['-is_system', 'name']
    
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
            queryset = queryset.select_related('owner')
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
        Delete a territory.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        # TEST ERROR MESSAGE ERRORDISPLAY IN FRONT
        raise StandardizedValidationError(
            'Territory deletion is currently disabled.',)
        
        # Prevent deletion of system territories
        if instance.is_system:
            raise StandardizedValidationError(
                CoreErrorMessages.CANNOT_DELETE,
                field='system territories'
            )
        
        logger.info("territory_delete_requested", extra={
            **ctx,
            'territory_id': str(instance.id),
            'territory_name': instance.name
        })
        
        territory_id = str(instance.id)
        territory_name = instance.name
        client_id = self.get_client_id()
        
        with transaction.atomic():
            instance.delete()

            # Audit log 
            audit_log(
                event='territory_delete_success',
                action='delete',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_id=territory_id, 
                extra={'territory_name': territory_name},  
                outcome='success',
                )
            
            
            # Invalidate cache after commit
            transaction.on_commit(lambda: self._invalidate_all_related_caches(client_id))
    
        
        logger.info("territory_delete_success", extra={
            **ctx,
            'territory_id': territory_id,
            'territory_name': territory_name
        })
        
        return Response({
            'success': True,
            'message': f'Territory "{territory_name}" deleted successfully.'
        }, status=status.HTTP_200_OK)
    
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
        """Count accounts matching territory filters."""
        from app_modules.accounts.models import CompanyAccount
        
        queryset = CompanyAccount.objects.filter(client_id=self.get_client_id())
        
        if not territory.filter_definition:
            return queryset.count()
        
        filters = territory.filter_definition
        
        # Type filter
        if filters.get('type'):
            type_val = filters['type']
            if isinstance(type_val, list):
                queryset = queryset.filter(type__in=type_val)
            else:
                queryset = queryset.filter(type=type_val)
        
        # Classification filter
        if filters.get('classification'):
            class_val = filters['classification']
            if isinstance(class_val, list):
                queryset = queryset.filter(classification__in=class_val)
            else:
                queryset = queryset.filter(classification=class_val)
        
        # Industry filter
        if filters.get('industry'):
            industry_val = filters['industry']
            if isinstance(industry_val, list):
                queryset = queryset.filter(industry__in=industry_val)
            else:
                queryset = queryset.filter(industry=industry_val)
        
        # Country filter
        if filters.get('country'):
            country_val = filters['country']
            if isinstance(country_val, list):
                queryset = queryset.filter(country__in=country_val)
            else:
                queryset = queryset.filter(country=country_val)
        
        # Account owner filter
        if filters.get('account_owner'):
            queryset = queryset.filter(account_owner_id=filters['account_owner'])
        
        # Account scope filter (mine/team)
        if filters.get('account_scope'):
            scope = filters['account_scope']
            if scope == 'mine':
                queryset = queryset.filter(account_owner=request.user)
            elif scope == 'team':
                if request.user.team_id:
                    queryset = queryset.filter(account_owner__team_id=request.user.team_id)
        
        return queryset.count()

    def _count_contacts_for_territory(self, territory, request):
        """Count contacts matching territory filters."""
        from app_modules.contacts.models import Contact
        
        queryset = Contact.objects.filter(client_id=self.get_client_id())
        
        if not territory.filter_definition:
            return queryset.count()
        
        filters = territory.filter_definition
        
        # Influence level filter
        if filters.get('influence_level'):
            level_val = filters['influence_level']
            if isinstance(level_val, list):
                queryset = queryset.filter(influence_level__in=level_val)
            else:
                queryset = queryset.filter(influence_level=level_val)
        
        # Standard department filter
        if filters.get('standard_department'):
            dept_val = filters['standard_department']
            if isinstance(dept_val, list):
                queryset = queryset.filter(standard_department_id__in=dept_val)
            else:
                queryset = queryset.filter(standard_department_id=dept_val)
        
        # Has buying authority filter
        if filters.get('has_buying_authority') is not None:
            queryset = queryset.filter(has_buying_authority=filters['has_buying_authority'])
        
        # Contact scope filter (mine/team) - filter by account owner
        if filters.get('contact_scope'):
            scope = filters['contact_scope']
            if scope == 'mine':
                queryset = queryset.filter(account__account_owner=request.user)
            elif scope == 'team':
                if request.user.team_id:
                    queryset = queryset.filter(account__account_owner__team_id=request.user.team_id)
        
        return queryset.count()
    
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
