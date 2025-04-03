# apps/accounts/views/buyingprocess_view.py

from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Max, F
from core.apps_shared_methods import BaseAPIView
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.accounts.models.buyingProcess import BuyingProcess, BuyingProcessStep, BuyingProcessStepContact
from apps.accounts.serializers.buyingprocess_serializer import BuyingProcessSerializer, BuyingProcessStepSerializer
from apps.core_apps.views import SignalAwareViewMixin, BuyingProcessTrackingMixin, BuyingProcessStepTrackingMixin

class BuyingProcessView(BaseAPIView, SignalAwareViewMixin, BuyingProcessTrackingMixin):
    """
    API view for managing buying processes with lifecycle tracking.
    """
    queryset = BuyingProcess.objects.select_related('account').prefetch_related('steps')
    serializer_class = BuyingProcessSerializer
    entity_name = 'buying_process'
    
    # Fields to track for BuyingProcess model
    tracked_fields = {
        'name', 'description', 'status', 'estimated_timeline_days', 'product'
    }
    
    def get_queryset(self):
        """Filter queryset by account if specified"""
        queryset = super().get_queryset()
        
        # Filter by account if provided in query params
        account_id = self.request.query_params.get('account_id')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
            
        return queryset
    
    def get_with_steps(self, request, pk=None):
        """
        Get a buying process with all its steps.
        
        GET /api/buying-processes/{id}/with-steps
        """
        process = self.get_object()
        
        # Get steps ordered by index
        steps = process.steps.all().order_by('step_index')
        
        # Create response with nested steps
        process_data = self.get_serializer(process).data
        process_data['steps'] = BuyingProcessStepSerializer(steps, many=True).data
        
        return Response(process_data)

class BuyingProcessStepView(BaseAPIView,SignalAwareViewMixin, BuyingProcessStepTrackingMixin):
    """
    API view for managing buying process steps.
    """
    queryset = BuyingProcessStep.objects.select_related('process', 'account').prefetch_related('contacts')
    serializer_class = BuyingProcessStepSerializer
    entity_name = 'buying_process_step'
    
    # Fields to track for BuyingProcessStep model
    tracked_fields = {
        'step_index', 'depends_on_steps', 'stakeholder', 'department_name', 
        'step_description', 'step_goal', 'influence_score', 'average_time_in_days'
    }
    
    # JSON fields to track
    tracked_json_fields = {
        'criterias', 'metrics'
    }
    
    def get_queryset(self):
        """Filter queryset by process or account if specified"""
        queryset = super().get_queryset()
        
        # Filter by process if provided
        process_id = self.request.query_params.get('process_id')
        if process_id:
            queryset = queryset.filter(process_id=process_id)
        
        # Filter by account if provided
        account_id = self.request.query_params.get('account_id')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
            
        # Order by process and step_index by default
        return queryset.order_by('process_id', 'step_index')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a buying process step with proper positioning.
        
        If step_index is provided, shifts other steps to make room.
        If not provided, adds the step to the end of the process.
        """
        # Check if position/step_index is provided
        step_index = request.data.get('step_index')
        process_id = request.data.get('process_id')
        
        if not process_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="process_id")
            )
        
        # Get the current max step_index for this process
        max_step = BuyingProcessStep.objects.filter(
            process_id=process_id
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
                    process_id=process_id,
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
        
        # Track the creation in the parent process's historical data
        try:
            process = BuyingProcess.objects.get(id=process_id)
            reason = request.data.get('change_reason', 'Step added')
            
            # Get all steps for the process
            steps_data = [
                {
                    'id': step.id,
                    'index': step.step_index,
                    'description': step.step_description
                }
                for step in process.steps.all().order_by('step_index')
            ]
            
            # Track the addition of this step in the process's historical data
            process.track_field_change('steps', None, steps_data, request.user, None, reason)
            
        except Exception as e:
            # Log but continue - step creation succeeded even if tracking failed
            print(f"Error tracking step creation in process history: {str(e)}")
        
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
        process_id = step.process_id
        
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
            process_id=process_id
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
                process_id=process_id,
                step_index__gt=current_index,
                step_index__lte=new_index
            ).update(step_index=F('step_index') - 1)
        else:
            # Moving up - shift steps in between up
            BuyingProcessStep.objects.filter(
                process_id=process_id,
                step_index__gte=new_index,
                step_index__lt=current_index
            ).update(step_index=F('step_index') + 1)
        
        # Update the step's position
        step.step_index = new_index
        step.save(update_fields=['step_index'])
        
        # Also update the process's historical record
        try:
            process = step.process
            
            # Get updated steps data
            steps_data = [
                {
                    'id': s.id,
                    'index': s.step_index,
                    'description': s.step_description
                }
                for s in process.steps.all().order_by('step_index')
            ]
            
            # Track changes to step ordering in the process
            process.track_field_change('step_ordering', None, steps_data, request.user, None, f"Step {step.id} moved to position {new_index}")
            
        except Exception as e:
            # Log but continue - step reordering succeeded even if tracking failed
            print(f"Error tracking step reordering in process history: {str(e)}")
        
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
        new_value = list(contact_ids)
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
        
        # Also update the process's historical record
        try:
            process = step.process
            
            # Track the contact change in the process
            contacts_data = {
                'step_id': step.id,
                'step_index': step.step_index,
                'old_contacts': old_value,
                'new_contacts': new_value
            }
            
            process.track_field_change('step_contacts', None, contacts_data, request.user, None, reason)
            
        except Exception as e:
            # Log but continue - contact update succeeded even if tracking failed
            print(f"Error tracking contact update in process history: {str(e)}")
        
        # Get updated step
        step.refresh_from_db()
        return Response(self.get_serializer(step).data)
    
    def get_by_process(self, request, process_id=None):
        """
        Get all steps for a specific process, ordered by step_index.
        
        GET /api/buying-process-steps/process/{process_id}
        """
        # Validate the process_id
        if not process_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="process_id")
            )
            
        # Get steps for this process
        steps = self.queryset.filter(process_id=process_id).order_by('step_index')
        
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
        
        # Handle process-specific endpoint
        if len(path) > 3 and path[3] == 'process' and len(path) > 4:
            process_id = path[4]
            if request.method == 'GET':
                return self.get_by_process(request, process_id)
        
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