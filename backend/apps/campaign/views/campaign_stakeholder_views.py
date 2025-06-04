# apps/campaign/views/campaign_stakeholder_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign import Campaign
from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
from apps.campaign.serializers.campaign_stakeholders_serializer import CampaignStakeholderSerializer


class CampaignStakeholderViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaign stakeholders
    """
    queryset = CampaignStakeholder.objects.all()
    serializer_class = CampaignStakeholderSerializer
    entity_name = 'campaign_stakeholder'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['campaign', 'user', 'role']
    ordering_fields = ['added_at', 'role']
    ordering = ['campaign', 'role', 'added_at']
    
    def get_queryset(self):
        """Get campaign stakeholders for the current client with filters"""
        queryset = CampaignStakeholder.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Prefetch related objects for performance
        queryset = queryset.select_related('campaign', 'user', 'added_by')
        
        # Filter by campaign
        campaign_id = self.request.query_params.get('campaign_id')
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new campaign stakeholder with client scoping"""
        client_id = self.get_client_id()
        
        # Validate campaign access
        campaign = serializer.validated_data['campaign']
        if campaign.client_id != client_id:
            raise StandardizedValidationError(
                CoreErrorMessages.ENTITY_NOT_FOUND.format(entity="Campaign")
            )
        
        # Set added_by to current user
        serializer.save(
            client_id=client_id,
            added_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Update a campaign stakeholder with validation and client scoping"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Validate campaign access
        campaign = serializer.validated_data.get('campaign', instance.campaign)
        if campaign.client_id != self.get_client_id():
            raise StandardizedValidationError(
                CoreErrorMessages.ENTITY_NOT_FOUND.format(entity="Campaign")
            )
        
        serializer.save()
    
    @action(detail=False, methods=['post'], url_path='bulk-add')
    def bulk_add(self, request):
        """Add multiple stakeholders to a campaign at once"""
        # Get campaign ID
        campaign_id = request.data.get('campaign_id')
        if not campaign_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="campaign_id"),
                field_name="campaign_id"
            )
        
        # Get stakeholder data
        stakeholders_data = request.data.get('stakeholders', [])
        if not stakeholders_data:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="stakeholders"),
                field_name="stakeholders"
            )
        
        try:
            # Get the campaign
            campaign = Campaign.objects.get(id=campaign_id, client_id=self.get_client_id())
            
            # Add stakeholders
            added = []
            errors = []
            
            for data in stakeholders_data:
                user_id = data.get('user_id')
                role = data.get('role')
                
                if not user_id or not role:
                    errors.append({
                        'data': data,
                        'error': CoreErrorMessages.REQUIRED_FIELD.format(
                            field="user_id and role"
                        )
                    })
                    continue
                
                try:
                    # Get user
                    User = get_user_model()
                    user = User.objects.get(id=user_id)
                    
                    # Add stakeholder
                    stakeholder = campaign.add_stakeholder(
                        user=user,
                        role=role,
                        added_by=request.user
                    )
                    
                    added.append(CampaignStakeholderSerializer(stakeholder).data)
                except User.DoesNotExist:
                    errors.append({
                        'data': data,
                        'error': CoreErrorMessages.ENTITY_NOT_FOUND.format(entity="User")
                    })
                except Exception as e:
                    errors.append({
                        'data': data,
                        'error': str(e)
                    })
            
            return Response({
                'success': True,
                'added': added,
                'errors': errors
            })
            
        except Campaign.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.ENTITY_NOT_FOUND.format(entity="Campaign"),
                field_name="campaign_id"
            )
    
    @action(detail=False, methods=['post'], url_path='bulk-remove')
    def bulk_remove(self, request):
        """Remove multiple stakeholders from a campaign at once"""
        # Get campaign ID
        campaign_id = request.data.get('campaign_id')
        if not campaign_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="campaign_id"),
                field_name="campaign_id"
            )
        
        # Get stakeholder data
        stakeholders_data = request.data.get('stakeholders', [])
        if not stakeholders_data:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="stakeholders"),
                field_name="stakeholders"
            )
        
        try:
            # Get the campaign
            campaign = Campaign.objects.get(id=campaign_id, client_id=self.get_client_id())
            
            # Remove stakeholders
            removed = []
            errors = []
            
            for data in stakeholders_data:
                user_id = data.get('user_id')
                role = data.get('role')  # Role is optional
                
                if not user_id:
                    errors.append({
                        'data': data,
                        'error': CoreErrorMessages.REQUIRED_FIELD.format(field="user_id")
                    })
                    continue
                
                try:
                    # Get user
                    User = get_user_model()
                    user = User.objects.get(id=user_id)
                    
                    # Remove stakeholder
                    result = campaign.remove_stakeholder(user=user, role=role)
                    
                    if result > 0:
                        removed.append({
                            'user_id': user_id,
                            'role': role,
                            'count': result
                        })
                except User.DoesNotExist:
                    errors.append({
                        'data': data,
                        'error': CoreErrorMessages.ENTITY_NOT_FOUND.format(entity="User")
                    })
                except Exception as e:
                    errors.append({
                        'data': data,
                        'error': str(e)
                    })
            
            return Response({
                'success': True,
                'removed': removed,
                'errors': errors
            })
            
        except Campaign.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.ENTITY_NOT_FOUND.format(entity="Campaign"),
                field_name="campaign_id"
            )