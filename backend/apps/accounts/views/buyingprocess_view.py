# apps/accounts/views/buyingprocess_view.py

from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Max, F
from core.apps_shared_methods import BaseAPIView
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.accounts.models.buyingProcess import BuyingProcessStep, BuyingProcessStepContact
from apps.accounts.serializers.buyingprocess_serializer import BuyingProcessStepSerializer
from apps.core_apps.views import HistoricalTrackingViewMixin

class BuyingProcessStepView(BaseAPIView, HistoricalTrackingViewMixin):
    """
    API view for managing buying process steps with lifecycle tracking.
    """
    queryset = BuyingProcessStep.objects.select_related('account').prefetch_related('contacts')
    serializer_class = BuyingProcessStepSerializer
    entity_name = 'buying_process_step'
    
    # Fields to track for BuyingProcessStep model
    tracked_fields = {
        'step_index', 'department_name', 'step_description', 
        'step_goal', 'influence_score', 'average_time_in_days'
    }
    
    # JSON fields to track
    tracked_json_fields = {
        'criterias', 'metrics'
    }
    
    def get_queryset(self):
        """Filter queryset by account if specified"""
        queryset = super().get_queryset()
        
        # Filter by account if provided in query params
        account_id = self.request.query_params.get('account_id')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
            
        # Order by step_index by default
        return queryset.order_by('account_id', 'step_index')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a buying process step with proper positioning.
        
        If step_index is provided, shifts other steps to make room.
        If not provided, adds the step to the end of the process.
        """
        # Check if position/step_index is provided
        step_index = request.data.get('step_index')
        account_id = request.data.get('account_id')
        
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
            )
        
        # Get the current max step_index for this account
        max_step = BuyingProcessStep.objects.filter(
            account_id=account_id
        ).aggregate(max_step=Max('step_index'))['max_step'] or -1
        
        data = request.data.copy()
        
        # If no step_index provided, append to the end
        if step_index is None:
            data['step_index'] = max_step + 1
        else:
            step_index = int(step_index)
            
            # Shift existing steps to make room if needed
            if 0 <= step_index <= max_step + 1:
                # Move all steps with equal or higher index up by one
                BuyingProcessStep.objects.filter(
                    account_id=account_id,
                    step_index__gte=step_index
                ).update(step_index=F('step_index') + 1)
                
                data['step_index'] = step_index
            else:
                # If index is beyond the current max, just append
                data['step_index'] = max_step + 1
        
        # Create the step using the standard process
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        # Use the user from the request for tracking
        instance = serializer.save(user=request.user)
        
        # Track changes for all fields
        for field in self.tracked_fields:
            if hasattr(instance, field) and getattr(instance, field) is not None:
                value = getattr(instance, field)
                reason = request.data.get('change_reason', 'Initial creation')
                instance.track_field_change(field, None, value, request.user, None, reason)
                
        # Track JSON fields
        for field in self.tracked_json_fields:
            if hasattr(instance, field) and getattr(instance, field) is not None:
                value = getattr(instance, field)
                reason = request.data.get('change_reason', 'Initial creation')
                instance.track_field_change(field, None, value, request.user, None, reason)
        
        return Response(
            self.get_serializer(instance).data,
            status=status.HTTP_201_CREATED
        )
    
    @transaction.atomic
    def update_position(self, request, pk=None):
        """
        Update the position of a step in the buying process.
        
        POST /api/buying-process-steps/{id}/position
        Requires new_index in the request data.
        """
        step = self.get_object()
        account_id = step.account_id
        
        try:
            new_index = int(request.data.get('new_index'))
        except (TypeError, ValueError):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="new_index as integer")
            )
        
        # Get the current index
        current_index = step.step_index
        
        # Get the max index in the process
        max_index = BuyingProcessStep.objects.filter(
            account_id=account_id
        ).aggregate(max_idx=Max('step_index'))['max_idx'] or 0
        
        # Validate the new index
        if new_index < 0 or new_index > max_index:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field=f"Index must be between 0 and {max_index}"
                )
            )
        
        # If no actual change, return early
        if new_index == current_index:
            return Response(self.get_serializer(step).data)
        
        # Track the change
        old_value = current_index
        reason = request.data.get('change_reason', 'Position changed')
        
        # Shift indexes based on move direction
        if new_index > current_index:
            # Moving down - shift steps in between down
            BuyingProcessStep.objects.filter(
                account_id=account_id,
                step_index__gt=current_index,
                step_index__lte=new_index
            ).update(step_index=F('step_index') - 1)
        else:
            # Moving up - shift steps in between up
            BuyingProcessStep.objects.filter(
                account_id=account_id,
                step_index__gte=new_index,
                step_index__lt=current_index
            ).update(step_index=F('step_index') + 1)
        
        # Update the step's position
        step.step_index = new_index
        step.save(update_fields=['step_index'])
        
        # Track the change in historical data
        step.track_field_change('step_index', old_value, new_index, request.user, None, reason)
        
        return Response(self.get_serializer(step).data)
    
    @transaction.atomic
    def update_contacts(self, request, pk=None):
        """
        Update contacts for a buying process step.
        
        POST /api/buying-process-steps/{id}/contacts
        """
        step = self.get_object()
        
        contact_ids = request.data.get('contact_ids', [])
        if not isinstance(contact_ids, list):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="contact_ids must be a list")
            )
            
        # Validate contacts belong to the same account
        from apps.accounts.models.contacts import Contact
        
        # Get existing contacts
        existing_contacts = set(step.contacts.values_list('id', flat=True))
        
        # Convert to set for easy comparison
        new_contacts = set(contact_ids)
        
        # Find contacts to add and remove
        contacts_to_add = new_contacts - existing_contacts
        contacts_to_remove = existing_contacts - new_contacts
        
        # Validate new contacts
        if contacts_to_add:
            invalid_contacts = Contact.objects.filter(
                id__in=contacts_to_add
            ).exclude(
                account_id=step.account_id
            ).count()
            
            if invalid_contacts > 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Contacts must belong to the same account"
                    )
                )
        
        # Track the change
        old_value = list(existing_contacts)
        new_value = list(new_contacts)
        reason = request.data.get('change_reason', 'Contacts updated')
        
        # Remove contacts
        if contacts_to_remove:
            BuyingProcessStepContact.objects.filter(
                step=step,
                contact_id__in=contacts_to_remove
            ).delete()
            
        # Add new contacts
        for contact_id in contacts_to_add:
            BuyingProcessStepContact.objects.create(
                step=step,
                contact_id=contact_id,
                client_id=step.client_id,
                created_by=request.user
            )
        
        # Track the change in historical data
        step.track_field_change('contacts', old_value, new_value, request.user, None, reason)
        
        # Get updated step
        step.refresh_from_db()
        return Response(self.get_serializer(step).data)
    
    def get_by_account(self, request, account_id=None):
        """
        Get all steps for a specific account, ordered by step_index.
        
        GET /api/buying-process-steps/account/{account_id}
        """
        # Validate the account_id
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
            )
            
        # Get steps for this account
        steps = self.queryset.filter(account_id=account_id).order_by('step_index')
        
        # Paginate if needed
        page = self.paginate_queryset(steps)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(steps, many=True)
        return Response(serializer.data)
    
    def dispatch(self, request, *args, **kwargs):
        """Custom dispatch to handle different endpoints"""
        path = request.path.split('/')
        
        # Handle account-specific endpoint
        if len(path) > 3 and path[3] == 'account' and len(path) > 4:
            account_id = path[4]
            if request.method == 'GET':
                return self.get_by_account(request, account_id)
        
        # Handle step-specific endpoints
        if len(path) > 4:
            endpoint_type = path[4]
            
            if endpoint_type == 'position':
                if request.method == 'POST':
                    return self.update_position(request, *args, **kwargs)
                    
            elif endpoint_type == 'contacts':
                if request.method == 'POST':
                    return self.update_contacts(request, *args, **kwargs)
        
        # Default to standard dispatch
        return super().dispatch(request, *args, **kwargs)