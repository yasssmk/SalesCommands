# apps/campaign/views/campaign_target_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign_target import CampaignTarget
from apps.campaign.serializers.campaign_target_serializer import CampaignTargetSerializer

class CampaignTargetViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaign targets
    """
    serializer_class = CampaignTargetSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign', 'status', 'activities_generated']
    search_fields = ['account__company_name', 'notes']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['campaign', 'created_at']
    
    def get_queryset(self):
        """Get campaign targets for the current client with filters"""
        queryset = CampaignTarget.objects.all()
        
        # Apply client scoping through related campaign
        queryset = queryset.filter(campaign__client_id=self.get_client_id())
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new campaign target with validation"""
        # Get campaign and validate ownership
        campaign = serializer.validated_data['campaign']
        if campaign.owner != self.request.user:
            raise StandardizedValidationError("You can only add targets to your own campaigns")
            
        return serializer.save()
    
    def perform_update(self, serializer):
        """Update a campaign target with validation"""
        instance = serializer.instance
        
        # Validate client scope via campaign
        if str(instance.campaign.client_id) != str(self.get_client_id()):
            raise StandardizedValidationError("Client mismatch")
            
        # Validate owner permissions
        if instance.campaign.owner != self.request.user:
            raise StandardizedValidationError("You can only modify targets for your own campaigns")
            
        return serializer.save()
    
    def perform_destroy(self, instance):
        """Delete a campaign target with validation"""
        # Validate client scope via campaign
        if str(instance.campaign.client_id) != str(self.get_client_id()):
            raise StandardizedValidationError("Client mismatch")
            
        # Validate owner permissions
        if instance.campaign.owner != self.request.user:
            raise StandardizedValidationError("You can only delete targets for your own campaigns")
            
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update the status of a campaign target"""
        target = self.get_object()
        
        # Validate owner permissions
        if target.campaign.owner != self.request.user:
            raise StandardizedValidationError("You can only update status for your own campaigns")
            
        # Get new status from request
        new_status = request.data.get('status', None)
        if new_status is None:
            raise StandardizedValidationError("Status is required")
            
        # Validate status value
        valid_statuses = [choice[0] for choice in CampaignTarget.Status.choices]
        if new_status not in valid_statuses:
            raise StandardizedValidationError("Invalid status value")
            
        # Update status
        target.update_status(new_status)
        
        return Response({
            'id': target.id,
            'status': target.status,
            'status_display': target.get_status_display()
        })
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple campaign targets at once
        
        Expected payload:
        {
            "campaign_id": 1,
            "account_ids": [1, 2, 3],     # Optional list of account IDs
            "contact_ids": [4, 5, 6],     # Optional list of contact IDs
            "lead_ids": [7, 8, 9],        # Optional list of lead IDs
            "opportunity_ids": [10, 11],  # Optional list of opportunity IDs
            "expected_value": 5000,       # Optional expected value
            "notes": "Optional notes"     # Optional notes
        }
        """
        # Get campaign ID
        campaign_id = request.data.get('campaign_id', None)
        if not campaign_id:
            raise StandardizedValidationError("Campaign ID is required")
            
        # Get target IDs for each type
        account_ids = request.data.get('account_ids', [])
        contact_ids = request.data.get('contact_ids', [])
        lead_ids = request.data.get('lead_ids', [])
        opportunity_ids = request.data.get('opportunity_ids', [])
        
        # Ensure at least one target type is provided
        if not any([account_ids, contact_ids, lead_ids, opportunity_ids]):
            raise StandardizedValidationError("At least one target type (accounts, contacts, leads, or opportunities) is required")
        
        # Get optional fields
        notes = request.data.get('notes', None)
        
        # Validate campaign
        from apps.campaign.models.campaign import Campaign
        try:
            campaign = Campaign.objects.get(id=campaign_id, client_id=self.get_client_id())
            
            # Validate ownership
            if campaign.owner != self.request.user:
                raise StandardizedValidationError("You can only add targets to your own campaigns")
                
        except Campaign.DoesNotExist:
            raise StandardizedValidationError("Campaign not found")
            
        # Created and skipped targets tracking
        created_targets = []
        skipped_targets = []
        
        # Process account targets
        if account_ids:
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
                    skipped_targets.append({
                        'target_type': 'account',
                        'id': account.id,
                        'name': account.company_name,
                        'reason': 'Already a target for this campaign'
                    })
                    continue
                    
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    account=account,
                    notes=notes,
                    client_id=self.get_client_id()
                )
                
                created_targets.append(CampaignTargetSerializer(target).data)
        
        # Process contact targets
        if contact_ids:
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
                    skipped_targets.append({
                        'target_type': 'contact',
                        'id': contact.id,
                        'name': f"{contact.first_name} {contact.last_name}",
                        'reason': 'Already a target for this campaign'
                    })
                    continue
                    
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    contact=contact,
                    notes=notes,
                    client_id=self.get_client_id()
                )
                
                created_targets.append(CampaignTargetSerializer(target).data)
        
        # Process lead targets
        if lead_ids:
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
                    skipped_targets.append({
                        'target_type': 'lead',
                        'id': lead.id,
                        'name': lead.title,
                        'reason': 'Already a target for this campaign'
                    })
                    continue
                    
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    lead=lead,
                    notes=notes,
                    client_id=self.get_client_id()
                )
                
                created_targets.append(CampaignTargetSerializer(target).data)
        
        # Process opportunity targets
        if opportunity_ids:
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
                    skipped_targets.append({
                        'target_type': 'opportunity',
                        'id': opportunity.id,
                        'name': opportunity.name,
                        'reason': 'Already a target for this campaign'
                    })
                    continue
                    
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    target_opportunity=opportunity,
                    notes=notes,
                    client_id=self.get_client_id()
                )
                
                created_targets.append(CampaignTargetSerializer(target).data)
            
        return Response({
            'created': created_targets,
            'skipped': skipped_targets,
            'total_created': len(created_targets),
            'total_skipped': len(skipped_targets)
        })