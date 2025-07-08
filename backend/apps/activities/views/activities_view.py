# apps/activities/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, timedelta

from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from core.error_messages import CoreErrorMessages, ActivityErrorMessages
from apps.accounts.models import Account, Contact
from apps.opportunities.models import Opportunity

from ..models import Activity, ActivitySequence, ActivityCampaign
from ..serializers import (
    ActivitySerializer,
    ActivityWithCampaignSerializer,
    ActivityCompletionSerializer,
    ActivitySequenceSerializer
)


class ActivityAPIView(BaseAPIView):
    """
    API View for Activity management with sequence and campaign handling.
    """
    
    queryset = Activity.objects.select_related(
        'account',
        'owner', 
        'opportunity',
        'previous_activity',
        'next_activity'
    ).prefetch_related(
        'contacts',
        'sequence_info',
        'campaign_info'
    )
    
    serializer_class = ActivitySerializer
    entity_name = 'activity'

    mass_update_allowed_fields = {
        'status', 'activity_type', 'owner_id', 'scheduled_start', 'scheduled_end'
    }

    def get_queryset(self):
        """Extend base queryset with activity-specific filtering"""
        queryset = super().get_queryset()
        
        # Basic filtering
        filter_mappings = {
            'owner_ids': 'owner_id__in',
            'account_ids': 'account_id__in',
            'statuses': 'status__in',
            'activity_types': 'activity_type__in',
            'opportunity_ids': 'opportunity_id__in'
        }
        
        try:
            for param, field in filter_mappings.items():
                values = self.request.query_params.get(param)
                if values:
                    filter_list = [v.strip() for v in values.split(',')]
                    queryset = queryset.filter(**{field: filter_list})
            
            # Date filtering
            start_date = self.request.query_params.get('start_date')
            end_date = self.request.query_params.get('end_date')
            
            if start_date:
                try:
                    start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    queryset = queryset.filter(scheduled_start__gte=start_date)
                except ValueError:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(detail="Invalid start_date format")
                    )
            
            if end_date:
                try:
                    end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    queryset = queryset.filter(scheduled_start__lte=end_date)
                except ValueError:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(detail="Invalid end_date format")
                    )
            
            # Sequence filtering
            sequence_position = self.request.query_params.get('sequence_position')
            if sequence_position:
                queryset = queryset.filter(sequence_info__sequence_position=sequence_position)
            
            sequence_outcome = self.request.query_params.get('sequence_outcome')
            if sequence_outcome:
                queryset = queryset.filter(sequence_info__sequence_outcome=sequence_outcome)
            
            # Campaign filtering
            campaign_ids = self.request.query_params.get('campaign_ids')
            if campaign_ids:
                campaign_list = [v.strip() for v in campaign_ids.split(',')]
                queryset = queryset.filter(campaign_info__campaign_id__in=campaign_list)
            
            # Status filtering shortcuts
            overdue = self.request.query_params.get('overdue')
            if overdue and overdue.lower() == 'true':
                queryset = queryset.filter(
                    status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS],
                    scheduled_start__lt=timezone.now()
                )
            
            upcoming = self.request.query_params.get('upcoming')
            if upcoming and upcoming.lower() == 'true':
                next_days = int(self.request.query_params.get('upcoming_days', 7))
                end_time = timezone.now() + timedelta(days=next_days)
                queryset = queryset.filter(
                    status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS],
                    scheduled_start__range=[timezone.now(), end_time]
                )
                    
        except ValueError as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FILTER.format(detail=str(e))
            )
            
        return queryset

    def get_serializer_context(self):
        """Add filter parameters to serializer context"""
        context = super().get_serializer_context()
        
        # Set 'many' flag for serializer context
        context['many'] = getattr(self, '_is_list_request', False)
        
        return context

    def get_serializer_class(self):
        """Return appropriate serializer based on request"""
        # Check if this is a completion request
        if hasattr(self, '_is_complete_action') and self._is_complete_action:
            return ActivityCompletionSerializer
        elif self.request.method == 'POST' and self.request.data and 'campaign_id' in self.request.data:
            return ActivityWithCampaignSerializer
        return self.serializer_class

    def dispatch(self, request, *args, **kwargs):
        """Custom dispatch to handle different endpoints"""
        # Check if this is a custom action endpoint
        path = request.path.split('/')
        
        # Path will contain segments like ['', 'api', 'activities', '1', 'complete', '']
        if len(path) > 4:
            endpoint_type = path[4]  # Get the endpoint type
            
            if endpoint_type == 'complete':
                if request.method == 'POST':
                    self._is_complete_action = True
                    return self.complete(request, *args, **kwargs)
            
            elif endpoint_type == 'increment_call_attempts':
                if request.method == 'POST':
                    return self.increment_call_attempts(request, *args, **kwargs)
        
        # Check for collection endpoints (no pk in kwargs)
        if 'pk' not in kwargs:
            endpoint = path[-2] if len(path) > 2 else ''
            self._is_list_request = True
            
            if endpoint == 'my_activities':
                if request.method == 'GET':
                    return self.my_activities(request, *args, **kwargs)
            
            elif endpoint == 'overdue':
                if request.method == 'GET':
                    return self.overdue(request, *args, **kwargs)
            
            elif endpoint == 'upcoming':
                if request.method == 'GET':
                    return self.upcoming(request, *args, **kwargs)
            
            elif endpoint == 'sequence_activities':
                if request.method == 'GET':
                    return self.sequence_activities(request, *args, **kwargs)
        
        # Default to standard dispatch
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        """Get a single object with client scope validation"""
        pk = self.kwargs.get('pk')
        if not pk:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        objects = self.get_objects([pk])
        if not objects.exists():
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        return objects.first()

    def complete(self, request, pk=None):
        """
        Complete an activity with outcome information.
        
        POST /api/activities/{id}/complete/
        """
        try:
            activity = self.get_object()
            
            # Validate activity can be completed
            if activity.status == Activity.Status.COMPLETED:
                raise StandardizedValidationError(
                    ActivityErrorMessages.ACTIVITY_ALREADY_COMPLETED
                )
            
            # Validate completion data
            serializer = ActivityCompletionSerializer(data=request.data)
            if not serializer.is_valid():
                raise StandardizedValidationError(serializer.errors)
            
            completion_data = serializer.validated_data
            
            with transaction.atomic():
                # Mark activity as completed
                activity.complete(
                    outcome_notes=completion_data.get('outcome_notes'),
                    save=False
                )
                
                # Handle campaign-specific outcomes
                if hasattr(activity, 'campaign_info') and activity.campaign_info:
                    campaign_info = activity.campaign_info
                    if completion_data.get('meeting_scheduled'):
                        campaign_info.meeting_scheduled = True
                        campaign_info.save()
                    
                    if completion_data.get('opportunity_created'):
                        campaign_info.opportunity_created = True
                        campaign_info.save()
                
                # Handle sequence-specific outcomes
                if hasattr(activity, 'sequence_info') and activity.sequence_info:
                    sequence_info = activity.sequence_info
                    sequence_outcome = completion_data.get('sequence_outcome')
                    callback_date = completion_data.get('callback_requested_date')
                    
                    if sequence_outcome:
                        sequence_info.set_outcome(
                            outcome=sequence_outcome,
                            notes=completion_data.get('outcome_notes'),
                            callback_date=callback_date,
                            save=True
                        )
                
                activity.save()
            
            # Return updated activity
            response_serializer = self.serializer_class(activity)
            return Response(response_serializer.data)
            
        except Exception as e:
            return self.handle_exception(e)

    def increment_call_attempts(self, request, pk=None):
        """
        Increment call attempts for sequence activities.
        
        POST /api/activities/{id}/increment_call_attempts/
        """
        try:
            activity = self.get_object()
            
            # Validate activity has sequence info and is a call
            if not hasattr(activity, 'sequence_info') or not activity.sequence_info:
                raise StandardizedValidationError(
                    "Activity is not part of a sequence"
                )
            
            if activity.activity_type != Activity.ActivityType.CALL:
                raise StandardizedValidationError(
                    "Only call activities can have call attempts incremented"
                )
            
            sequence_info = activity.sequence_info
            attempts = sequence_info.increment_call_attempts()
            
            return Response({
                'call_attempts': attempts,
                'max_attempts_reached': attempts >= 3,
                'activity_completed': activity.status == Activity.Status.COMPLETED
            })
            
        except Exception as e:
            return self.handle_exception(e)

    def my_activities(self, request):
        """
        Get activities assigned to the current user.
        
        GET /api/activities/my_activities/
        """
        try:
            # Filter by current user
            queryset = self.get_queryset().filter(owner=request.user)
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.serializer_class(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.serializer_class(queryset, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return self.handle_exception(e)

    def overdue(self, request):
        """
        Get overdue activities.
        
        GET /api/activities/overdue/
        """
        try:
            # Filter overdue activities
            queryset = self.get_queryset().filter(
                status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS],
                scheduled_start__lt=timezone.now()
            )
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.serializer_class(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.serializer_class(queryset, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return self.handle_exception(e)

    def upcoming(self, request):
        """
        Get upcoming activities.
        
        GET /api/activities/upcoming/
        """
        try:
            # Get number of days to look ahead
            days = int(request.query_params.get('days', 7))
            end_time = timezone.now() + timedelta(days=days)
            
            # Filter upcoming activities
            queryset = self.get_queryset().filter(
                status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS],
                scheduled_start__range=[timezone.now(), end_time]
            ).order_by('scheduled_start')
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.serializer_class(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.serializer_class(queryset, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return self.handle_exception(e)

    def sequence_activities(self, request):
        """
        Get activities that are part of sequences.
        
        GET /api/activities/sequence_activities/
        """
        try:
            # Filter sequence activities
            queryset = self.get_queryset().filter(
                sequence_info__isnull=False
            ).select_related('sequence_info')
            
            # Optional filtering by sequence type or position
            sequence_type = request.query_params.get('sequence_type')
            if sequence_type:
                queryset = queryset.filter(sequence_info__sequence_type=sequence_type)
            
            sequence_position = request.query_params.get('sequence_position')
            if sequence_position:
                queryset = queryset.filter(sequence_info__sequence_position=sequence_position)
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.serializer_class(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.serializer_class(queryset, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return self.handle_exception(e)


class ActivityChoicesView(APIView):
    """
    API endpoint for retrieving activity type and status choices.
    No client scoping needed as these are global choices.
    """
    def get(self, request):
        return Response({
            'activity_types': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in Activity.ActivityType.choices
            ],
            'statuses': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in Activity.Status.choices
            ],
            'sequence_outcomes': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in ActivitySequence.SequenceOutcome.choices
            ],
            'source_types': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in ActivitySequence.SourceType.choices
            ]
        })