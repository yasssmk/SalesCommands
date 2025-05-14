from django.shortcuts import render
# apps/activities/views/activity_views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.activities.models import Activity, ActivityCampaign, ActivitySequence
from apps.activities.serializers import (
    ActivitySerializer,
    ActivityWithCampaignSerializer,
    ActivityCompletionSerializer,
    ActivityCampaignSerializer,
    ActivitySequenceSerializer
)


class ActivityViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing activities
    """
    serializer_class = ActivitySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'activity_type', 'status', 'owner', 'account', 
        'campaign_info__campaign', 'sequence_info__source_type'
    ]
    search_fields = ['title', 'description', 'account__company_name']
    ordering_fields = ['scheduled_start', 'created_at', 'title']
    ordering = ['scheduled_start']
    
    def get_queryset(self):
        """Get activities for the current client with optimized queries"""
        queryset = Activity.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Optimize queries with select_related and prefetch_related
        queryset = queryset.select_related(
            'account', 'owner', 'opportunity',
            'campaign_info__campaign', 'campaign_info__campaign_target',
            'sequence_info'
        ).prefetch_related('contacts')
        
        # Filter by current user's activities if requested
        my_activities = self.request.query_params.get('my_activities', None)
        if my_activities and my_activities.lower() == 'true':
            queryset = queryset.filter(owner=self.request.user)
        
        # Filter by today's activities if requested
        today = self.request.query_params.get('today', None)
        if today and today.lower() == 'true':
            today_date = timezone.now().date()
            queryset = queryset.filter(scheduled_start__date=today_date)
        
        # Filter by pending activities
        pending = self.request.query_params.get('pending', None)
        if pending and pending.lower() == 'true':
            queryset = queryset.filter(status=Activity.Status.PLANNED)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'complete':
            return ActivityCompletionSerializer
        elif self.action == 'create' and self.request.data.get('campaign_id'):
            return ActivityWithCampaignSerializer
        return self.serializer_class
    
    def perform_create(self, serializer):
        """Create a new activity with validation"""
        # Validate client ownership of related objects
        return serializer.save()
    
    def perform_update(self, serializer):
        """Update an activity with validation"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Only owner can modify
        if instance.owner != self.request.user:
            raise StandardizedValidationError("You can only modify your own activities")
        
        return serializer.save()
    
    def perform_destroy(self, instance):
        """Delete an activity with validation"""
        self.validate_client_id(instance)
        
        # Only owner can delete
        if instance.owner != self.request.user:
            raise StandardizedValidationError("You can only delete your own activities")
        
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete an activity with outcome tracking"""
        activity = self.get_object()
        
        # Validate owner permissions
        if activity.owner != self.request.user:
            raise StandardizedValidationError("You can only complete your own activities")
        
        # Check if already completed
        if activity.status == Activity.Status.COMPLETED:
            raise StandardizedValidationError("Activity is already completed")
        
        # Get completion data
        serializer = ActivityCompletionSerializer(data=request.data)
        if not serializer.is_valid():
            raise StandardizedValidationError(serializer.errors)
        
        completion_data = serializer.validated_data
        
        # Complete the activity using transaction
        with transaction.atomic():
            # Complete the base activity
            activity.complete(
                outcome_notes=completion_data.get('outcome_notes'),
                save=False
            )
            
            # Update campaign information if exists
            if hasattr(activity, 'campaign_info'):
                campaign_info = activity.campaign_info
                campaign_info.meeting_scheduled = completion_data.get('meeting_scheduled', False)
                campaign_info.opportunity_created = completion_data.get('opportunity_created', False)
                campaign_info.save()
                
                # Update campaign objectives if needed
                self._update_campaign_objectives(activity, completion_data)
            
            # Update sequence information if exists
            if hasattr(activity, 'sequence_info'):
                sequence_info = activity.sequence_info
                
                # Set sequence outcome
                if 'sequence_outcome' in completion_data:
                    sequence_info.set_outcome(
                        completion_data['sequence_outcome'],
                        notes=completion_data.get('outcome_notes'),
                        callback_date=completion_data.get('callback_requested_date'),
                        save=False
                    )
                
                sequence_info.save()
                
                # Handle sequence progression
                self._handle_sequence_progression(activity, completion_data)
            
            # Save the activity
            activity.save()
        
        # Return the updated activity
        serializer = self.get_serializer(activity)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an activity"""
        activity = self.get_object()
        
        # Validate owner permissions
        if activity.owner != self.request.user:
            raise StandardizedValidationError("You can only cancel your own activities")
        
        # Get cancellation reason
        reason = request.data.get('reason', None)
        
        activity.cancel(reason=reason)
        
        serializer = self.get_serializer(activity)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def attempt_call(self, request, pk=None):
        """Record a call attempt for sequence activities"""
        activity = self.get_object()
        
        # Validate owner permissions
        if activity.owner != self.request.user:
            raise StandardizedValidationError("You can only record attempts for your own activities")
        
        # Check if activity is a call
        if activity.activity_type != Activity.ActivityType.CALL:
            raise StandardizedValidationError("Call attempts can only be recorded for call activities")
        
        # Check if activity has sequence info
        if not hasattr(activity, 'sequence_info'):
            raise StandardizedValidationError("This activity is not part of a sequence")
        
        sequence_info = activity.sequence_info
        
        # Check if can still attempt
        if sequence_info.call_attempts >= 3:
            raise StandardizedValidationError("Maximum call attempts (3) already reached")
        
        # Increment attempts
        sequence_info.increment_call_attempts()
        
        # Return updated information
        data = {
            'call_attempts': sequence_info.call_attempts,
            'max_attempts': 3,
            'can_attempt_again': sequence_info.call_attempts < 3,
            'is_completed': activity.status == Activity.Status.COMPLETED
        }
        
        return Response(data)
    
    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """Reschedule an activity"""
        activity = self.get_object()
        
        # Validate owner permissions
        if activity.owner != self.request.user:
            raise StandardizedValidationError("You can only reschedule your own activities")
        
        # Get new date
        new_date = request.data.get('scheduled_start')
        if not new_date:
            raise StandardizedValidationError("New scheduled date is required")
        
        # Update activity
        activity.scheduled_start = new_date
        
        # Update end date if provided
        if request.data.get('scheduled_end'):
            activity.scheduled_end = request.data.get('scheduled_end')
        
        # Add notes about reschedule
        if request.data.get('notes'):
            if activity.outcome_notes:
                activity.outcome_notes += f"\n\nRescheduled: {request.data.get('notes')}"
            else:
                activity.outcome_notes = f"Rescheduled: {request.data.get('notes')}"
        
        # If this is a sequence activity, handle sequence pausing
        if hasattr(activity, 'sequence_info'):
            sequence_info = activity.sequence_info
            if request.data.get('pause_sequence_until'):
                sequence_info.pause_until(request.data.get('pause_sequence_until'))
        
        activity.save()
        
        serializer = self.get_serializer(activity)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def sequence_overview(self, request):
        """Get overview of sequence activities for campaigns"""
        campaign_id = request.query_params.get('campaign_id')
        if not campaign_id:
            raise StandardizedValidationError("Campaign ID is required")
        
        # Get all sequence activities for the campaign
        activities = Activity.objects.filter(
            campaign_info__campaign_id=campaign_id,
            campaign_info__campaign__owner=request.user,
            sequence_info__isnull=False
        ).select_related('sequence_info', 'account').order_by(
            'account', 'sequence_info__sequence_position'
        )
        
        # Group by account
        sequence_data = {}
        for activity in activities:
            account_id = activity.account.id
            if account_id not in sequence_data:
                sequence_data[account_id] = {
                    'account': {
                        'id': activity.account.id,
                        'company_name': activity.account.company_name
                    },
                    'activities': [],
                    'current_step': None,
                    'completion_rate': 0
                }
            
            # Add activity data
            sequence_data[account_id]['activities'].append({
                'id': activity.id,
                'position': activity.sequence_info.sequence_position,
                'type': activity.activity_type,
                'status': activity.status,
                'outcome': activity.sequence_info.sequence_outcome,
                'scheduled_start': activity.scheduled_start
            })
            
            # Calculate current step and completion rate
            if activity.status == Activity.Status.PLANNED and not sequence_data[account_id]['current_step']:
                sequence_data[account_id]['current_step'] = activity.sequence_info.sequence_position
        
        # Calculate completion rates
        for account_data in sequence_data.values():
            total_activities = len(account_data['activities'])
            completed_activities = len([a for a in account_data['activities'] if a['status'] == 'COMPLETED'])
            account_data['completion_rate'] = (completed_activities / total_activities * 100) if total_activities > 0 else 0
        
        return Response(list(sequence_data.values()))
    
    def _update_campaign_objectives(self, activity, completion_data):
        """Update campaign objectives based on activity completion"""
        if not hasattr(activity, 'campaign_info'):
            return
        
        campaign = activity.campaign_info.campaign
        
        # Update various objectives based on the outcome
        from apps.campaign.models.campaign_objective import CampaignObjective
        
        # Update meeting objectives
        if completion_data.get('meeting_scheduled'):
            meeting_objectives = campaign.objectives.filter(
                objective_type=CampaignObjective.ObjectiveType.MEETINGS
            )
            for objective in meeting_objectives:
                objective.update_progress(1, increment=True)
        
        # Update opportunity objectives
        if completion_data.get('opportunity_created'):
            opportunity_objectives = campaign.objectives.filter(
                objective_type=CampaignObjective.ObjectiveType.OPPORTUNITIES
            )
            for objective in opportunity_objectives:
                objective.update_progress(1, increment=True)
    
    def _handle_sequence_progression(self, activity, completion_data):
        """Handle what happens next in the sequence"""
        if not hasattr(activity, 'sequence_info'):
            return
        
        sequence_info = activity.sequence_info
        sequence_outcome = completion_data.get('sequence_outcome')
        
        # Handle different outcomes
        if sequence_outcome == ActivitySequence.SequenceOutcome.NO_ANSWER:
            # Create next activity in sequence if not at the end
            if sequence_info.sequence_position < 10:  # Chasing sequence has 10 steps
                self._create_next_sequence_activity(activity)
        
        elif sequence_outcome == ActivitySequence.SequenceOutcome.NOT_INTERESTED:
            # End sequence for this contact/account
            # This will be implemented based on business rules
            pass
        
        elif sequence_outcome == ActivitySequence.SequenceOutcome.MEETING_SCHEDULED:
            # Create meeting activity
            # Update campaign target status
            if hasattr(activity, 'campaign_info'):
                campaign_target = activity.campaign_info.campaign_target
                campaign_target.update_status('MEETING_SECURED')
    
    def _create_next_sequence_activity(self, current_activity):
        """Create the next activity in the sequence"""
        # This will be implemented when we create the sequence service
        # For now, just return None
        pass
