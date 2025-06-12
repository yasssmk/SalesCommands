# apps/campaign/views/campaign_stakeholder_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign import Campaign
from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
from apps.campaign.serializers.campaign_stakeholders_serializer import CampaignStakeholderSerializer
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder,
    CampaignSuccessMessages
)
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin


class CampaignStakeholderViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaign stakeholders
    Now returns standardized responses consistently with centralized permissions
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
        try:
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
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to retrieve campaign stakeholders")
            )
    
    def perform_create(self, serializer):
        """Create a new campaign stakeholder with client scoping"""
        try:
            client_id = self.get_client_id()
            
            campaign = self.get_validated_campaign_from_data('campaign', allow_stakeholders=False)
            
            # Set added_by to current user
            serializer.save(
                client_id=client_id,
                added_by=self.request.user
            )
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason="Stakeholder creation failed")
            )
    
    def perform_update(self, serializer):
        """Update a campaign stakeholder with validation and client scoping"""
        try:
            instance = serializer.instance
            
            self.validate_campaign_related_object(instance, allow_stakeholders=False)
            
            serializer.save()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Stakeholder update failed")
            )
    
    def perform_destroy(self, instance):
        """Delete a campaign stakeholder with validation"""
        try:

            self.validate_campaign_related_object(instance, allow_stakeholders=False)
            
            instance.delete()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Stakeholder deletion failed")
            )
    
    @action(detail=False, methods=['post'], url_path='bulk-add')
    def bulk_add(self, request):
        """
        Add multiple stakeholders to a campaign at once
        Now returns standardized response with detailed results
        """
        try:
            # Get campaign ID
            campaign_id = request.data.get('campaign_id')
            if not campaign_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="campaign_id")
                )
            
            # Get stakeholder data
            stakeholders_data = request.data.get('stakeholders', [])
            if not stakeholders_data:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="stakeholders")
                )
            

            campaign = self.get_validated_campaign(pk=campaign_id, require_ownership=True)
            
            # Add stakeholders
            successful = []
            failed = []
            
            for data in stakeholders_data:
                user_id = data.get('user_id')
                role = data.get('role')
                
                if not user_id or not role:
                    failed.append({
                        'data': data,
                        'error': CoreErrorMessages.REQUIRED_FIELD.format(field="user_id and role")
                    })
                    continue
                
                try:
                    # Get user
                    User = get_user_model()
                    user = User.objects.get(id=user_id)
                    
                    # Add stakeholder using Campaign method
                    stakeholder = campaign.add_stakeholder(
                        user=user,
                        role=role,
                        added_by=request.user
                    )
                    
                    # Serialize the created stakeholder
                    stakeholder_data = CampaignStakeholderSerializer(stakeholder).data
                    successful.append(stakeholder_data)
                    
                except User.DoesNotExist:
                    failed.append({
                        'data': data,
                        'error': CoreErrorMessages.OBJECT_NOT_FOUND
                    })
                except Exception as e:
                    failed.append({
                        'data': data,
                        'error': str(e)
                    })
            
            # Use CampaignResponseBuilder for bulk operation
            return CampaignResponseBuilder.bulk_operation(
                operation_type='stakeholder_addition',
                successful_items=successful,
                failed_items=failed,
                custom_message=CampaignSuccessMessages.BULK_OPERATION_COMPLETED.format(
                    successful=len(successful),
                    total=len(stakeholders_data)
                )
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.BULK_OPERATION_FAILED.format(operation="stakeholder addition")
            )
    
    @action(detail=False, methods=['post'], url_path='bulk-remove')
    def bulk_remove(self, request):
        """
        Remove multiple stakeholders from a campaign at once
        Now returns standardized response with detailed results
        """
        try:
            # Get campaign ID
            campaign_id = request.data.get('campaign_id')
            if not campaign_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="campaign_id")
                )
            
            # Get stakeholder data
            stakeholders_data = request.data.get('stakeholders', [])
            if not stakeholders_data:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="stakeholders")
                )
            

            campaign = self.get_validated_campaign(pk=campaign_id, require_ownership=True)
            
            # Remove stakeholders
            successful = []
            failed = []
            
            for data in stakeholders_data:
                user_id = data.get('user_id')
                role = data.get('role')  # Role is optional for removal
                
                if not user_id:
                    failed.append({
                        'data': data,
                        'error': CoreErrorMessages.REQUIRED_FIELD.format(field="user_id")
                    })
                    continue
                
                try:
                    # Get user
                    User = get_user_model()
                    user = User.objects.get(id=user_id)
                    
                    # Remove stakeholder using Campaign method
                    removed_count = campaign.remove_stakeholder(user=user, role=role)
                    
                    if removed_count > 0:
                        successful.append({
                            'user_id': user_id,
                            'user_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                            'role': role,
                            'stakeholders_removed': removed_count
                        })
                    else:
                        failed.append({
                            'data': data,
                            'error': 'No matching stakeholder found to remove'
                        })
                        
                except User.DoesNotExist:
                    failed.append({
                        'data': data,
                        'error': CoreErrorMessages.OBJECT_NOT_FOUND
                    })
                except Exception as e:
                    failed.append({
                        'data': data,
                        'error': str(e)
                    })
            
            # Use CampaignResponseBuilder for bulk operation
            return CampaignResponseBuilder.bulk_operation(
                operation_type='stakeholder_removal',
                successful_items=successful,
                failed_items=failed,
                custom_message=f"Bulk stakeholder removal: {len(successful)}/{len(stakeholders_data)} successful"
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.BULK_OPERATION_FAILED.format(operation="stakeholder removal")
            )