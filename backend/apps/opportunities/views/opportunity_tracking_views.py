# apps/opportunities/views/opportunity_tracking_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.opportunities.models import (
    Opportunity, OpportunitySource, OpportunityActivity, OpportunityHistory
)
from apps.opportunities.serializers import (
    OpportunitySourceSerializer, OpportunityActivitySerializer, OpportunityHistorySerializer
)
from apps.activities.models import Activity
from apps.activities.serializers import ActivitySerializer


class OpportunitySourceViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing opportunity sources
    """
    queryset = OpportunitySource.objects.all()
    serializer_class = OpportunitySourceSerializer
    entity_name = 'opportunity_source'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['opportunity', 'source_type', 'conversion_status']
    ordering_fields = ['conversion_date']
    ordering = ['-conversion_date']
    
    def get_queryset(self):
        """Get opportunity sources for the current client with filters"""
        queryset = OpportunitySource.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Optimize queries
        queryset = queryset.select_related(
            'opportunity', 'source_lead', 'source_campaign', 'partner',
            'created_by', 'assigned_to'
        )
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new opportunity source with client scoping"""
        client_id = self.get_client_id()
        source = serializer.save(client_id=client_id)
        
        # Create history entry
        source.opportunity.create_history_entry(
            'CREATED',
            f"Opportunity created from {source.get_source_type_display()}"
        )
        
        return source
    
    def perform_update(self, serializer):
        """Update an opportunity source with validation and client scoping"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Validate opportunity ownership
        opportunity = instance.opportunity
        if opportunity.deal_owner != self.request.user and not self.request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only update sources for opportunities assigned to you")
        
        return serializer.save()
    
    @action(detail=True, methods=['post'])
    def accept_conversion(self, request, pk=None):
        """Accept a pending opportunity conversion"""
        source = self.get_object()
        
        # Check if pending approval
        if source.conversion_status != OpportunitySource.ConversionStatus.PENDING:
            return Response({
                'success': False,
                'message': 'This opportunity is not pending approval'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get notes if provided
        notes = request.data.get('notes')
        
        # Accept the conversion
        source.accept_conversion(user=request.user, notes=notes)
        
        return Response({
            'success': True,
            'message': 'Conversion accepted successfully',
            'source': OpportunitySourceSerializer(source, context={'client_id': self.get_client_id()}).data
        })
    
    @action(detail=True, methods=['post'])
    def reject_conversion(self, request, pk=None):
        """Reject a pending opportunity conversion"""
        source = self.get_object()
        
        # Check if pending approval
        if source.conversion_status != OpportunitySource.ConversionStatus.PENDING:
            return Response({
                'success': False,
                'message': 'This opportunity is not pending approval'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get reason if provided
        reason = request.data.get('reason')
        
        # Reject the conversion
        source.reject_conversion(reason=reason)
        
        return Response({
            'success': True,
            'message': 'Conversion rejected',
            'source': OpportunitySourceSerializer(source, context={'client_id': self.get_client_id()}).data
        })


class OpportunityActivityViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing opportunity activities
    """
    queryset = OpportunityActivity.objects.all()
    serializer_class = OpportunityActivitySerializer
    entity_name = 'opportunity_activity'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['opportunity', 'activity', 'is_key_activity']
    ordering_fields = ['created_at', 'activity__scheduled_start']
    ordering = ['-activity__scheduled_start']
    
    def get_queryset(self):
        """Get opportunity activities for the current client with filters"""
        queryset = OpportunityActivity.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Optimize queries
        queryset = queryset.select_related(
            'opportunity', 'activity', 'activity__owner', 'created_by'
        )
        
        # Filter by opportunity
        opportunity_id = self.request.query_params.get('opportunity_id')
        if opportunity_id:
            queryset = queryset.filter(opportunity_id=opportunity_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new opportunity activity link with client scoping"""
        client_id = self.get_client_id()
        
        # Set created_by to current user
        serializer.validated_data['created_by'] = self.request.user
        
        return serializer.save(client_id=client_id)
    
    def perform_update(self, serializer):
        """Update an opportunity activity link with validation and client scoping"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Validate opportunity ownership
        opportunity = instance.opportunity
        if opportunity.deal_owner != self.request.user and not self.request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only update activities for opportunities assigned to you")
        
        return serializer.save()
    
    def perform_destroy(self, instance):
        """Delete an opportunity activity link with validation and client scoping"""
        self.validate_client_id(instance)
        
        # Validate opportunity ownership
        opportunity = instance.opportunity
        if opportunity.deal_owner != self.request.user and not self.request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only delete activities for opportunities assigned to you")
        
        instance.delete()
    
    @action(detail=False, methods=['post'])
    def create_activity(self, request):
        """Create a new activity and link it to an opportunity"""
        # Get opportunity ID
        opportunity_id = request.data.get('opportunity_id')
        if not opportunity_id:
            return Response({
                'success': False,
                'error': 'opportunity_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get the opportunity
            opportunity = Opportunity.objects.get(id=opportunity_id, client_id=self.get_client_id())
            
            # Validate ownership
            if opportunity.deal_owner != request.user and not request.user.has_perm('opportunities.change_opportunity'):
                raise StandardizedValidationError("You can only create activities for opportunities assigned to you")
            
            # Create activity data
            activity_data = request.data.copy()
            
            # Ensure activity is linked to the opportunity's account
            activity_data['account'] = opportunity.account.id
            
            # Default to current user as owner if not specified
            if 'owner' not in activity_data:
                activity_data['owner'] = request.user.id
            
            # Create the activity
            activity_serializer = ActivitySerializer(data=activity_data, context={'request': request})
            activity_serializer.is_valid(raise_exception=True)
            activity = activity_serializer.save()
            
            # Create the opportunity activity link
            opportunity_activity = OpportunityActivity.objects.create(
                opportunity=opportunity,
                activity=activity,
                is_key_activity=request.data.get('is_key_activity', False),
                notes=request.data.get('notes'),
                created_by=request.user,
                client_id=self.get_client_id()
            )
            
            return Response({
                'success': True,
                'message': 'Activity created and linked to opportunity',
                'activity': ActivitySerializer(activity).data,
                'opportunity_activity': OpportunityActivitySerializer(opportunity_activity).data
            })
            
        except Opportunity.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Opportunity not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def opportunity_timeline(self, request):
        """Get timeline of activities for an opportunity"""
        # Get opportunity ID
        opportunity_id = request.query_params.get('opportunity_id')
        if not opportunity_id:
            return Response({
                'success': False,
                'error': 'opportunity_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get the opportunity
            opportunity = Opportunity.objects.get(id=opportunity_id, client_id=self.get_client_id())
            
            # Get all activities linked to this opportunity
            links = OpportunityActivity.objects.filter(
                opportunity=opportunity
            ).select_related('activity', 'activity__owner', 'created_by')
            
            # Extract activities and sort by date
            activities = []
            for link in links:
                activity = link.activity
                activities.append({
                    'id': activity.id,
                    'link_id': link.id,
                    'title': activity.title,
                    'activity_type': activity.activity_type,
                    'activity_type_display': activity.get_activity_type_display(),
                    'status': activity.status,
                    'status_display': activity.get_status_display(),
                    'scheduled_start': activity.scheduled_start,
                    'completed_at': activity.completed_at,
                    'owner': activity.owner.get_full_name(),
                    'is_key_activity': link.is_key_activity,
                    'notes': link.notes,
                    'outcome_notes': activity.outcome_notes
                })
            
            # Sort by date (scheduled_start or completed_at if available)
            activities.sort(key=lambda x: x['completed_at'] or x['scheduled_start'], reverse=True)
            
            # Get history entries for the opportunity
            history_entries = OpportunityHistory.objects.filter(
                opportunity=opportunity
            ).order_by('-change_date')
            
            history = []
            for entry in history_entries:
                history.append({
                    'id': entry.id,
                    'change_type': entry.change_type,
                    'change_type_display': entry.get_change_type_display(),
                    'description': entry.description,
                    'details': entry.details,
                    'change_date': entry.change_date,
                    'changed_by': entry.changed_by.get_full_name() if entry.changed_by else None
                })
            
            # Merge activities and history into a timeline
            timeline = []
            
            # Add activities
            for activity in activities:
                timeline.append({
                    'type': 'ACTIVITY',
                    'date': activity['completed_at'] or activity['scheduled_start'],
                    'data': activity
                })
            
            # Add history entries
            for entry in history:
                timeline.append({
                    'type': 'HISTORY',
                    'date': entry['change_date'],
                    'data': entry
                })
            
            # Sort timeline by date (newest first)
            timeline.sort(key=lambda x: x['date'], reverse=True)
            
            return Response({
                'opportunity': {
                    'id': opportunity.id,
                    'title': opportunity.title,
                    'status': opportunity.status,
                    'status_display': opportunity.get_status_display(),
                    'date_open': opportunity.date_open,
                    'days_open': opportunity.get_days_open()
                },
                'timeline': timeline
            })
            
        except Opportunity.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Opportunity not found'
            }, status=status.HTTP_404_NOT_FOUND)