# apps/activities/views.py
from rest_framework.views import APIView
from rest_framework import viewsets, status, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, timedelta
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from core.error_messages import CoreErrorMessages, ActivityErrorMessages
from ..models import Activity, ActivitySequence
from ..serializers import (
    ActivitySerializer,
    ActivityWithCampaignSerializer,
    ActivityCompletionSerializer,
)


class ActivityViewSet(BaseAPIView, viewsets.ModelViewSet):
    """API endpoints for managing activities"""
    
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    entity_name = 'activity'  
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'activity_type', 'status', 'owner', 'account', 
        'campaign_info__campaign', 'sequence_info__source_type'
    ]
    search_fields = ['title', 'description', 'account__company_name']
    ordering_fields = ['scheduled_start', 'created_at', 'title']
    ordering = ['scheduled_start']

    def get_queryset(self):

        """Extend base queryset with activity-specific filtering"""
        queryset = Activity.objects.all()
    
        # ✅ Apply client scoping (obligatoire)
        queryset = self.filter_queryset_by_client(queryset)

        queryset = queryset.select_related(
            'account', 'owner', 'opportunity',
            'campaign_info__campaign', 'campaign_info__campaign_target',
            'sequence_info'
        ).prefetch_related('contacts')
        
        # ✅ Additional filters
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
        
        return queryset

    def get_serializer_context(self):
        """Add client_id to serializer context"""
        context = super().get_serializer_context()
        context['client_id'] = self.get_client_id()
        return context

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'complete':
            return ActivityCompletionSerializer
        elif self.action == 'create' and self.request.data.get('campaign_id'):
            return ActivityWithCampaignSerializer
        return self.serializer_class

    def list(self, request, *args, **kwargs):
        """
        List activities with additional filtering options
        """

        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
        

    
    def create(self, request, *args, **kwargs):
        """
        Create a new activity with validation
        """
        client_id = self.get_client_id()
            
        # Valider les données
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # ✅ BaseAPIView handles client_id and user automatically
        activity = serializer.save(client_id=client_id, user=request.user)
        
        return Response({
            'success': True,
            'message': f'Activity "{activity.title}" created successfully',
            'data': {
                'activity_id': activity.id,
                'title': activity.title,
                'activity_type': activity.activity_type,
                'status': activity.status,
                'owner': activity.owner.get_full_name() if activity.owner else None,
                'scheduled_start': activity.scheduled_start
            }
        }, status=status.HTTP_201_CREATED)  

    
    def update(self, request, *args, **kwargs):
        """
        Met à jour une activité existante
        """
        instance = self.get_object()
        partial = kwargs.pop('partial', False)
        
        # ✅ Validate ownership
        if instance.owner != self.request.user:
            raise StandardizedValidationError(
                ActivityErrorMessages.PERMISSION_DENIED
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        serializer.save(user=request.user)
        
        return Response({
            'success': True,
            'message': f'Activity "{instance.title}" updated successfully',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """
        Supprime une activité
        """
        instance = self.get_object()
        
        # ✅ Validate ownership
        if instance.owner != self.request.user:
            raise StandardizedValidationError(
                ActivityErrorMessages.PERMISSION_DENIED
            )
        
        activity_title = instance.title
        instance.delete()
        
        return Response({
            'success': True,
            'message': f'Activity "{activity_title}" deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
            

    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Complete an activity with outcome tracking
        """
        activity = self.get_object()
        
        # ✅ Validate ownership
        if activity.owner != self.request.user:
            raise StandardizedValidationError(
                ActivityErrorMessages.PERMISSION_DENIED
            )
        
        # ✅ Check if already completed
        if activity.status == Activity.Status.COMPLETED:
            raise StandardizedValidationError(
                ActivityErrorMessages.ACTIVITY_ALREADY_COMPLETED
            )
        
        # ✅ Use completion serializer
        serializer = ActivityCompletionSerializer(
            activity, 
            data=request.data, 
            partial=True,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        
        # ✅ Complete the activity
        with transaction.atomic():
            activity = serializer.save(
                status=Activity.Status.COMPLETED,
                completed_at=timezone.now(),
                user=request.user
            )
        
        return Response({
            'success': True,
            'message': f'Activity "{activity.title}" completed successfully',
            'data': {
                'activity_id': activity.id,
                'title': activity.title,
                'status': activity.status,
                'completed_at': activity.completed_at
            }
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def increment_call_attempts(self, request, pk=None):
        """
        Increment call attempts for sequence activities
        """
        activity = self.get_object()
        
        # ✅ Validate ownership
        if activity.owner != self.request.user:
            raise StandardizedValidationError(
                ActivityErrorMessages.PERMISSION_DENIED
            )
        
        # ✅ Check if activity has sequence info
        if not hasattr(activity, 'sequence_info'):
            raise StandardizedValidationError(
                ActivityErrorMessages.ACTIVITY_INVALID_STATE.format(
                    current_state="Activity is not part of a sequence"
                )
            )
        
        # ✅ Increment call attempts
        sequence_info = activity.sequence_info
        sequence_info.call_attempts += 1
        sequence_info.save()
        
        return Response({
            'success': True,
            'message': 'Call attempts incremented successfully',
            'data': {
                'call_attempts': sequence_info.call_attempts,
                'can_attempt_call': sequence_info.call_attempts < 3
            }
        })
    
    @action(detail=False, methods=['get'])
    def my_activities(self, request):
        """
        Get current user's activities
        """
        queryset = self.get_queryset().filter(owner=request.user)
        queryset = self.filter_queryset(queryset)
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get overdue activities
        """
        now = timezone.now()
        queryset = self.get_queryset().filter(
            status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS],
            scheduled_start__lt=now
        ).order_by('scheduled_start')
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming activities
        """
        # Get number of days to look ahead
        days = int(request.query_params.get('days', 7))
        end_time = timezone.now() + timedelta(days=days)
        
        queryset = self.get_queryset().filter(
            status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS],
            scheduled_start__range=[timezone.now(), end_time]
        ).order_by('scheduled_start')
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def sequence_activities(self, request):
        """
        Get activities that are part of sequences
        """
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
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ActivityChoicesView(BaseAPIView):
    """
    API endpoint for retrieving activity type and status choices.
    No client scoping needed as these are global choices.
    """
    
    # ✅ Attributs requis pour BaseAPIView
    queryset = Activity.objects.none()  # Pas de queryset nécessaire pour les choices
    serializer_class = ActivitySerializer  # Requis même si pas utilisé
    entity_name = 'activity_choices'
    
    def get(self, request, *args, **kwargs):
        """
        Return available choices for activity fields
        """
        choices = {
            'activity_types': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in Activity.ActivityType.choices
            ],
            'statuses': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in Activity.Status.choices
            ]
        }
        return Response(choices)