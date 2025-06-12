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
            # ✅ AVANT: Validation répétée
            # campaign = serializer.validated_data['campaign']
            # if campaign.owner != self.request.user:
            #     raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
            
            # ✅ APRÈS: Validation centralisée
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
        successful = []
        failed = []
        
        try:
            from apps.accounts.models import Account
            accounts = Account.objects.filter(
                id__in=account_ids,
                client_id=self.get_client_id()
            )
            
            # Check for existing targets
            existing_account_targets = CampaignTarget.objects.filter(
                campaign=campaign,
                account__in=accounts
            ).values_list('account_id', flat=True)
            
            for account in accounts:
                if account.id in existing_account_targets:
                    failed.append({
                        'target_type': 'account',
                        'target_id': account.id,
                        'target_name': account.company_name,
                        'error': 'Already a target for this campaign'
                    })
                    continue
                    
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    account=account,
                    notes=notes,
                    client_id=self.get_client_id()
                )
                
                successful.append({
                    'target_id': target.id,
                    'target_type': 'account',
                    'target_name': account.company_name,
                    'created_at': target.created_at.isoformat()
                })
                
        except Exception as e:
            # If there's an error processing accounts, add all to failed
            for account_id in account_ids:
                failed.append({
                    'target_type': 'account',
                    'target_id': account_id,
                    'target_name': 'Unknown',
                    'error': str(e)
                })
        
        return {'successful': successful, 'failed': failed}
    
    def _create_contact_targets(self, campaign, contact_ids, notes):
        """Helper method to create contact targets"""
        successful = []
        failed = []
        
        try:
            from apps.accounts.models import Contact
            contacts = Contact.objects.filter(
                id__in=contact_ids,
                account__client_id=self.get_client_id()
            )
            
            # Check for existing targets
            existing_contact_targets = CampaignTarget.objects.filter(
                campaign=campaign,
                contact__in=contacts
            ).values_list('contact_id', flat=True)
            
            for contact in contacts:
                if contact.id in existing_contact_targets:
                    failed.append({
                        'target_type': 'contact',
                        'target_id': contact.id,
                        'target_name': f"{contact.first_name} {contact.last_name}",
                        'error': 'Already a target for this campaign'
                    })
                    continue
                    
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    contact=contact,
                    notes=notes,
                    client_id=self.get_client_id()
                )
                
                successful.append({
                    'target_id': target.id,
                    'target_type': 'contact',
                    'target_name': f"{contact.first_name} {contact.last_name}",
                    'created_at': target.created_at.isoformat()
                })
                
        except Exception as e:
            # If there's an error processing contacts, add all to failed
            for contact_id in contact_ids:
                failed.append({
                    'target_type': 'contact',
                    'target_id': contact_id,
                    'target_name': 'Unknown',
                    'error': str(e)
                })
        
        return {'successful': successful, 'failed': failed}
    
    def _create_lead_targets(self, campaign, lead_ids, notes):
        """Helper method to create lead targets"""
        successful = []
        failed = []
        
        try:
            from apps.leads.models import Lead
            leads = Lead.objects.filter(
                id__in=lead_ids,
                client_id=self.get_client_id()
            )
            
            # Check for existing targets
            existing_lead_targets = CampaignTarget.objects.filter(
                campaign=campaign,
                lead__in=leads
            ).values_list('lead_id', flat=True)
            
            for lead in leads:
                if lead.id in existing_lead_targets:
                    failed.append({
                        'target_type': 'lead',
                        'target_id': lead.id,
                        'target_name': lead.title,
                        'error': 'Already a target for this campaign'
                    })
                    continue
                    
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    lead=lead,
                    notes=notes,
                    client_id=self.get_client_id()
                )
                
                successful.append({
                    'target_id': target.id,
                    'target_type': 'lead',
                    'target_name': lead.title,
                    'created_at': target.created_at.isoformat()
                })
                
        except Exception as e:
            # If there's an error processing leads, add all to failed
            for lead_id in lead_ids:
                failed.append({
                    'target_type': 'lead',
                    'target_id': lead_id,
                    'target_name': 'Unknown',
                    'error': str(e)
                })
        
        return {'successful': successful, 'failed': failed}
    
    def _create_opportunity_targets(self, campaign, opportunity_ids, notes):
        """Helper method to create opportunity targets"""
        successful = []
        failed = []
        
        try:
            from apps.opportunities.models import Opportunity
            opportunities = Opportunity.objects.filter(
                id__in=opportunity_ids,
                client_id=self.get_client_id()
            )
            
            # Check for existing targets
            existing_opportunity_targets = CampaignTarget.objects.filter(
                campaign=campaign,
                target_opportunity__in=opportunities
            ).values_list('target_opportunity_id', flat=True)
            
            for opportunity in opportunities:
                if opportunity.id in existing_opportunity_targets:
                    failed.append({
                        'target_type': 'opportunity',
                        'target_id': opportunity.id,
                        'target_name': opportunity.name,
                        'error': 'Already a target for this campaign'
                    })
                    continue
                    
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    target_opportunity=opportunity,
                    notes=notes,
                    client_id=self.get_client_id()
                )
                
                successful.append({
                    'target_id': target.id,
                    'target_type': 'opportunity',
                    'target_name': opportunity.name,
                    'created_at': target.created_at.isoformat()
                })
                
        except Exception as e:
            # If there's an error processing opportunities, add all to failed
            for opportunity_id in opportunity_ids:
                failed.append({
                    'target_type': 'opportunity',
                    'target_id': opportunity_id,
                    'target_name': 'Unknown',
                    'error': str(e)
                })
        
        return {'successful': successful, 'failed': failed}