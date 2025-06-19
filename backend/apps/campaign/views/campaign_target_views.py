# apps/campaign/views/campaign_target_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign_target import CampaignTarget
from apps.campaign.serializers.campaign_target_serializer import CampaignTargetSerializer
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder,
    CampaignSuccessMessages
)
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin

class CampaignTargetViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaign targets
    Now returns standardized responses consistently with centralized permissions
    """
    serializer_class = CampaignTargetSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign', 'status', 'activities_generated']
    search_fields = ['account__company_name', 'notes']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['campaign', 'created_at']
    
    def get_queryset(self):
        """Get campaign targets for the current client with filters"""
        try:
            queryset = CampaignTarget.objects.all()
            
            # Apply client scoping through related campaign
            queryset = queryset.filter(campaign__client_id=self.get_client_id())
            
            return queryset
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to retrieve campaign targets")
            )
    
    def perform_create(self, serializer):
        """Create a new campaign target with validation"""
        try:

            campaign = self.get_validated_campaign_from_data('campaign', allow_stakeholders=False)
                
            return serializer.save()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason="Target creation failed")
            )
    
    def perform_update(self, serializer):
        """Update a campaign target with validation"""
        try:
            instance = serializer.instance
            self.validate_campaign_related_object(instance, allow_stakeholders=False)
                
            return serializer.save()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target update failed")
            )
    
    def perform_destroy(self, instance):
        """Delete a campaign target with validation"""
        try:

            self.validate_campaign_related_object(instance, allow_stakeholders=False)
                
            instance.delete()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target deletion failed")
            )
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Update the status of a campaign target
        Now returns standardized response
        """
        try:
            target = self.get_object()

            self.validate_campaign_related_object(target, allow_stakeholders=False)
                
            # Get new status from request
            new_status = request.data.get('status', None)
            if new_status is None:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="status")
                )
                
            # Validate status value
            valid_statuses = [choice[0] for choice in CampaignTarget.Status.choices]
            if new_status not in valid_statuses:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="status")
                )
                
            # Store old status for response
            old_status = target.status
            old_status_display = target.get_status_display()
            
            # Update status
            target.update_status(new_status)
            
            # Prepare response data
            data = {
                'target_id': target.id,
                'target_type': target.get_target_type(),
                'target_name': target.get_target().company_name if hasattr(target.get_target(), 'company_name') else str(target.get_target()),
                'old_status': old_status,
                'old_status_display': old_status_display,
                'new_status': target.status,
                'new_status_display': target.get_status_display(),
                'campaign_id': target.campaign.id,
                'campaign_name': target.campaign.name
            }
            
            meta = {
                'operation': 'target_status_update',
                'status_changed': old_status != new_status
            }
            
            # Return standardized success response
            return StandardizedSuccessResponse.success(
                message=f"Target status updated from {old_status_display} to {target.get_status_display()}",
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Status update failed")
            )
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Create multiple campaign targets at once
        Now returns standardized response with detailed results
        
        Expected payload:
        {
            "campaign_id": 1,
            "account_ids": [1, 2, 3],     # Optional list of account IDs
            "contact_ids": [4, 5, 6],     # Optional list of contact IDs
            "lead_ids": [7, 8, 9],        # Optional list of lead IDs
            "opportunity_ids": [10, 11],  # Optional list of opportunity IDs
            "notes": "Optional notes"     # Optional notes
        }
        """
        try:
            # Get campaign ID
            campaign_id = request.data.get('campaign_id', None)
            if not campaign_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="campaign_id")
                )
                
            # Get target IDs for each type
            account_ids = request.data.get('account_ids', [])
            contact_ids = request.data.get('contact_ids', [])
            lead_ids = request.data.get('lead_ids', [])
            opportunity_ids = request.data.get('opportunity_ids', [])
            
            # Ensure at least one target type is provided
            if not any([account_ids, contact_ids, lead_ids, opportunity_ids]):
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="at least one target type (accounts, contacts, leads, or opportunities)")
                )
            
            # Get optional fields
            notes = request.data.get('notes', None)
            
            campaign = self.get_validated_campaign(pk=campaign_id, require_ownership=True)
                
            # Created and skipped targets tracking
            successful = []
            failed = []
            
            # Process account targets
            if account_ids:
                account_results = self._create_account_targets(campaign, account_ids, notes)
                successful.extend(account_results['successful'])
                failed.extend(account_results['failed'])
            
            # Process contact targets
            if contact_ids:
                contact_results = self._create_contact_targets(campaign, contact_ids, notes)
                successful.extend(contact_results['successful'])
                failed.extend(contact_results['failed'])
            
            # Process lead targets
            if lead_ids:
                lead_results = self._create_lead_targets(campaign, lead_ids, notes)
                successful.extend(lead_results['successful'])
                failed.extend(lead_results['failed'])
            
            # Process opportunity targets
            if opportunity_ids:
                opportunity_results = self._create_opportunity_targets(campaign, opportunity_ids, notes)
                successful.extend(opportunity_results['successful'])
                failed.extend(opportunity_results['failed'])
            
            # Use CampaignResponseBuilder for bulk operation
            return CampaignResponseBuilder.bulk_operation(
                operation_type='target_creation',
                successful_items=successful,
                failed_items=failed,
                custom_message=CampaignSuccessMessages.BULK_OPERATION_COMPLETED.format(
                    successful=len(successful),
                    total=len(successful) + len(failed)
                )
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.BULK_OPERATION_FAILED.format(operation="target creation")
            )
    
    def _create_account_targets(self, campaign, account_ids, notes):
        """Helper method to create account targets"""
        from apps.accounts.models import Account
        return self._create_targets_of_type(
            campaign=campaign,
            target_ids=account_ids,
            target_type='account',
            notes=notes,
            model_class=Account,
            model_filter={'id__in': account_ids, 'client_id': self.get_client_id()},
            existing_filter_field='account',
            target_create_field='account',
            name_getter=lambda obj: obj.company_name
        )

    def _create_contact_targets(self, campaign, contact_ids, notes):
        """Helper method to create contact targets"""
        from apps.accounts.models import Contact
        return self._create_targets_of_type(
            campaign=campaign,
            target_ids=contact_ids,
            target_type='contact',
            notes=notes,
            model_class=Contact,
            model_filter={'id__in': contact_ids, 'account__client_id': self.get_client_id()},
            existing_filter_field='contact',
            target_create_field='contact',
            name_getter=lambda obj: f"{obj.first_name} {obj.last_name}"
        )

    def _create_lead_targets(self, campaign, lead_ids, notes):
        """Helper method to create lead targets"""
        from apps.leads.models import Lead
        return self._create_targets_of_type(
            campaign=campaign,
            target_ids=lead_ids,
            target_type='lead',
            notes=notes,
            model_class=Lead,
            model_filter={'id__in': lead_ids, 'client_id': self.get_client_id()},
            existing_filter_field='lead',
            target_create_field='lead',
            name_getter=lambda obj: obj.title
        )

    def _create_opportunity_targets(self, campaign, opportunity_ids, notes):
        """Helper method to create opportunity targets"""
        from apps.opportunities.models import Opportunity
        return self._create_targets_of_type(
            campaign=campaign,
            target_ids=opportunity_ids,
            target_type='opportunity',
            notes=notes,
            model_class=Opportunity,
            model_filter={'id__in': opportunity_ids, 'client_id': self.get_client_id()},
            existing_filter_field='target_opportunity',
            target_create_field='target_opportunity',
            name_getter=lambda obj: obj.name
        )

    def _create_targets_of_type(self, campaign, target_ids, target_type, notes, model_class, 
                          model_filter, existing_filter_field, target_create_field, name_getter):
        """
        Méthode helper locale pour éliminer la duplication entre les 4 types de targets
        Reste dans le ViewSet, pas dans le mixin
        """
        successful = []
        failed = []
        
        # Get objects with proper error handling
        try:
            objects = model_class.objects.filter(**model_filter)
        except Exception as e:
            # Si on ne peut pas récupérer les objets, c'est une erreur système
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Failed to retrieve {target_type} objects")
            )
        
        # Check for existing targets
        try:
            existing_filter = {f'{existing_filter_field}__in': objects}
            existing_targets = CampaignTarget.objects.filter(
                campaign=campaign,
                **existing_filter
            ).values_list(f'{existing_filter_field}_id', flat=True)
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Failed to check existing {target_type} targets")
            )
        
        # Traiter chaque objet individuellement
        for obj in objects:
            try:
                if obj.id in existing_targets:
                    failed.append({
                        'target_type': target_type,
                        'target_id': obj.id,
                        'target_name': name_getter(obj),
                        'error': 'Already a target for this campaign'
                    })
                    continue
                    
                # Create target
                create_kwargs = {
                    'campaign': campaign,
                    target_create_field: obj,
                    'notes': notes,
                    'client_id': self.get_client_id()
                }
                target = CampaignTarget.objects.create(**create_kwargs)
                
                successful.append({
                    'target_id': target.id,
                    'target_type': target_type,
                    'target_name': name_getter(obj),
                    'created_at': target.created_at.isoformat()
                })
                
            except Exception as e:
                # ✅ Erreur spécifique à cet objet, on l'ajoute aux failed mais on continue
                failed.append({
                    'target_type': target_type,
                    'target_id': obj.id,
                    'target_name': name_getter(obj),
                    'error': f"Creation failed: {str(e)}"
                })
        
        # Vérifier si on a des IDs qui n'ont pas été trouvés
        found_ids = [obj.id for obj in objects]
        missing_ids = set(target_ids) - set(found_ids)
        
        for missing_id in missing_ids:
            failed.append({
                'target_type': target_type,
                'target_id': missing_id,
                'target_name': 'Unknown',
                'error': CoreErrorMessages.OBJECT_NOT_FOUND
            })
        
        return {'successful': successful, 'failed': failed}