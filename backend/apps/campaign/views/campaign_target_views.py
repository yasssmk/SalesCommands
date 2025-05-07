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
    filterset_fields = ['campaign', 'status', 'sequence_created']
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
        """Create multiple campaign targets at once"""
        # Get campaign ID
        campaign_id = request.data.get('campaign_id', None)
        if not campaign_id:
            raise StandardizedValidationError("Campaign ID is required")
            
        # Get account IDs
        account_ids = request.data.get('account_ids', [])
        if not account_ids or not isinstance(account_ids, list):
            raise StandardizedValidationError("Account IDs list is required")
            
        # Get optional fields
        expected_value = request.data.get('expected_value', None)
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
            
        # Get accounts
        from apps.accounts.models import Account
        accounts = Account.objects.filter(
            id__in=account_ids,
            client_id=self.get_client_id()
        )
        
        if len(accounts) != len(account_ids):
            raise StandardizedValidationError("One or more accounts not found")
            
        # Check for existing targets
        existing_targets = CampaignTarget.objects.filter(
            campaign=campaign,
            account__in=accounts
        ).values_list('account_id', flat=True)
        
        # Create targets
        created_targets = []
        skipped_targets = []
        
        for account in accounts:
            if account.id in existing_targets:
                skipped_targets.append({
                    'account_id': account.id,
                    'company_name': account.company_name,
                    'reason': 'Already a target for this campaign'
                })
                continue
                
            target = CampaignTarget.objects.create(
                campaign=campaign,
                account=account,
                expected_value=expected_value,
                notes=notes
            )
            
            created_targets.append(CampaignTargetSerializer(target).data)
            
        return Response({
            'created': created_targets,
            'skipped': skipped_targets,
            'total_created': len(created_targets),
            'total_skipped': len(skipped_targets)
        })