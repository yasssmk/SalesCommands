# apps/leads/views/lead_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.leads.models import Lead
from apps.activities.models import Activity
from core.error_messages import CoreErrorMessages
from end_users.models import User
from apps.leads.serializers import (
    LeadSerializer, 
    LeadListSerializer, 
    LeadConversionSerializer,
    LeadActivitySerializer
)


class LeadViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing leads
    """
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    entity_name = 'lead'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['lead_status', 'lead_source', 'assigned_to', 'is_qualified', 'account', 'campaign']
    search_fields = ['title', 'description', 'contact__first_name', 'contact__last_name', 'account__company_name']
    ordering_fields = ['created_at', 'last_activity_date', 'title']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail views"""
        if self.action == 'list':
            return LeadListSerializer
        elif self.action == 'convert':
            return LeadConversionSerializer
        elif self.action in ['activities', 'add_activity', 'remove_activity']:
            return LeadActivitySerializer
        return LeadSerializer
    
    def get_serializer_context(self):
        """Add client_id to serializer context"""
        context = super().get_serializer_context()
        context['client_id'] = self.get_client_id()
        return context
    
    def get_queryset(self):
        """Get leads for the current client with filters"""
        queryset = Lead.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Prefetch related objects for performance
        queryset = queryset.select_related(
            'account', 'contact', 'campaign', 'assigned_to', 
            'source_activity', 'converted_to_opportunity'
        ).prefetch_related('activities')
        
        # Filter by assigned user if requested
        my_leads = self.request.query_params.get('my_leads', None)
        if my_leads and my_leads.lower() == 'true':
            queryset = queryset.filter(assigned_to=self.request.user)
        
        # Filter by conversion status
        converted = self.request.query_params.get('converted', None)
        if converted:
            if converted.lower() == 'true':
                queryset = queryset.filter(lead_status=Lead.LeadStatus.CONVERTED)
            else:
                queryset = queryset.exclude(lead_status=Lead.LeadStatus.CONVERTED)
        
        # Filter by date range
        created_after = self.request.query_params.get('created_after', None)
        created_before = self.request.query_params.get('created_before', None)
        
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new lead with client scoping"""
        client_id = self.get_client_id()
        lead = serializer.save(client_id=client_id, user=self.request.user)
        
        # If created from a campaign activity, update campaign metrics
        if lead.campaign and lead.source_activity:
            self._update_campaign_metrics(lead)
        
        return lead
    
    def perform_update(self, serializer):
        """Update a lead with validation and client scoping"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Prevent client_id modification
        if 'client_id' in serializer.validated_data:
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_IMMUTABLE)
        
        # Check if user has permission to update this lead
        if instance.assigned_to != self.request.user and not self.request.user.has_perm('leads.change_lead'):
            raise StandardizedValidationError("You can only update leads assigned to you")
        
        return serializer.save(user=self.request.user)
    
    def perform_destroy(self, instance):
        """Delete a lead with validation and client scoping"""
        self.validate_client_id(instance)
        
        # Check if user has permission to delete this lead
        if instance.assigned_to != self.request.user and not self.request.user.has_perm('leads.delete_lead'):
            raise StandardizedValidationError("You can only delete leads assigned to you")
        
        # Don't allow deletion of converted leads
        if instance.lead_status == Lead.LeadStatus.CONVERTED:
            raise StandardizedValidationError("Cannot delete converted leads")
        
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def qualify(self, request, pk=None):
        """Mark a lead as qualified"""
        lead = self.get_object()
        
        # Validate ownership
        if lead.assigned_to != request.user and not request.user.has_perm('leads.change_lead'):
            raise StandardizedValidationError("You can only qualify leads assigned to you")
        
        # Check if already qualified
        if lead.lead_status == Lead.LeadStatus.QUALIFIED:
            return Response({
                'success': False,
                'message': 'Lead is already qualified'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update lead status
        lead.lead_status = Lead.LeadStatus.QUALIFIED
        lead.save()
        
        return Response({
            'success': True,
            'message': 'Lead qualified successfully',
            'lead': LeadSerializer(lead, context={'client_id': self.get_client_id()}).data
        })
    
    @action(detail=True, methods=['post'])
    def disqualify(self, request, pk=None):
        """Mark a lead as unqualified"""
        lead = self.get_object()
        
        # Validate ownership
        if lead.assigned_to != request.user and not request.user.has_perm('leads.change_lead'):
            raise StandardizedValidationError("You can only disqualify leads assigned to you")
        
        # Check if already converted
        if lead.lead_status == Lead.LeadStatus.CONVERTED:
            return Response({
                'success': False,
                'message': 'Cannot disqualify converted leads'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get reason for disqualification
        reason = request.data.get('reason', '')
        
        # Update lead
        lead.lead_status = Lead.LeadStatus.UNQUALIFIED
        if reason:
            lead.notes = f"{lead.notes}\n\nDisqualified: {reason}" if lead.notes else f"Disqualified: {reason}"
        lead.save()
        
        return Response({
            'success': True,
            'message': 'Lead disqualified',
            'lead': LeadSerializer(lead, context={'client_id': self.get_client_id()}).data
        })
    
    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Convert a qualified lead to opportunity"""
        lead = self.get_object()
        
        # Validate ownership
        if lead.assigned_to != request.user and not request.user.has_perm('leads.change_lead'):
            raise StandardizedValidationError("You can only convert leads assigned to you")
        
        # Check if can convert
        if not lead.can_convert():
            return Response({
                'success': False,
                'message': 'Lead must be qualified and not already converted'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate conversion data
        serializer = LeadConversionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # This will be implemented when Opportunity model is created
            # For now, just update the lead status
            opportunity = lead.convert_to_opportunity(serializer.validated_data)
            
            return Response({
                'success': True,
                'message': 'Lead converted successfully',
                'lead': LeadSerializer(lead, context={'client_id': self.get_client_id()}).data,
                # 'opportunity': OpportunitySerializer(opportunity).data
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get all activities for this lead"""
        lead = self.get_object()
        
        # Get activities ordered by scheduled date
        activities = lead.activities.all().order_by('-scheduled_start', '-created_at')
        
        # Apply status filter if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            activities = activities.filter(status=status_filter)
        
        # Serialize activities
        serializer = LeadActivitySerializer(activities, many=True)
        
        return Response({
            'lead_id': lead.id,
            'lead_title': lead.title,
            'total_activities': lead.activities.count(),
            'activities': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def add_activity(self, request, pk=None):
        """Add an existing activity to this lead"""
        lead = self.get_object()
        
        # Validate ownership
        if lead.assigned_to != request.user and not request.user.has_perm('leads.change_lead'):
            raise StandardizedValidationError("You can only modify activities for leads assigned to you")
        
        # Get activity ID
        activity_id = request.data.get('activity_id')
        if not activity_id:
            return Response({
                'success': False,
                'error': 'activity_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            activity = Activity.objects.get(id=activity_id)
            
            # Validate activity belongs to same account
            if activity.account != lead.account:
                raise StandardizedValidationError("Activity must belong to the same account as the lead")
            
            # Add activity to lead
            lead.activities.add(activity)
            lead.update_activity_tracking()
            
            return Response({
                'success': True,
                'message': 'Activity added to lead',
                'lead': LeadSerializer(lead, context={'client_id': self.get_client_id()}).data
            })
        except Activity.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Activity not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def remove_activity(self, request, pk=None):
        """Remove an activity from this lead"""
        lead = self.get_object()
        
        # Validate ownership
        if lead.assigned_to != request.user and not request.user.has_perm('leads.change_lead'):
            raise StandardizedValidationError("You can only modify activities for leads assigned to you")
        
        # Get activity ID
        activity_id = request.data.get('activity_id')
        if not activity_id:
            return Response({
                'success': False,
                'error': 'activity_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            activity = lead.activities.get(id=activity_id)
            
            # Remove activity from lead
            lead.activities.remove(activity)
            lead.update_activity_tracking()
            
            return Response({
                'success': True,
                'message': 'Activity removed from lead',
                'lead': LeadSerializer(lead, context={'client_id': self.get_client_id()}).data
            })
        except Activity.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Activity not found in this lead'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign lead to a different user"""
        lead = self.get_object()
        
        # Check permission
        if not request.user.has_perm('leads.change_lead'):
            raise StandardizedValidationError("You don't have permission to reassign leads")
        
        # Get new assignee
        assignee_id = request.data.get('assigned_to')
        if not assignee_id:
            return Response({
                'success': False,
                'error': 'assigned_to is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_assignee = User.objects.get(id=assignee_id)
            
            # Update assignment
            old_assignee = lead.assigned_to
            lead.assigned_to = new_assignee
            lead.save()
            
            return Response({
                'success': True,
                'message': f'Lead reassigned from {old_assignee} to {new_assignee}',
                'lead': LeadSerializer(lead, context={'client_id': self.get_client_id()}).data
            })
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary statistics for leads"""
        queryset = self.get_queryset()
        
        # Calculate statistics
        total_leads = queryset.count()
        
        # Status breakdown
        status_counts = {}
        for status_choice in Lead.LeadStatus.choices:
            status_code = status_choice[0]
            status_display = status_choice[1]
            count = queryset.filter(lead_status=status_code).count()
            status_counts[status_code] = {
                'display': status_display,
                'count': count
            }
        
        # Source breakdown
        source_counts = {}
        for source_choice in Lead.LeadSource.choices:
            source_code = source_choice[0]
            source_display = source_choice[1]
            count = queryset.filter(lead_source=source_code).count()
            source_counts[source_code] = {
                'display': source_display,
                'count': count
            }
        
        # Conversion rate
        converted_count = queryset.filter(lead_status=Lead.LeadStatus.CONVERTED).count()
        conversion_rate = (converted_count / total_leads * 100) if total_leads > 0 else 0
        
        # Activity metrics
        activity_metrics = queryset.aggregate(
            avg_touches=Avg('activities__count'),
            total_activities=Count('activities')
        )
        
        return Response({
            'total_leads': total_leads,
            'status_breakdown': status_counts,
            'source_breakdown': source_counts,
            'conversion_rate': round(conversion_rate, 1),
            'converted_count': converted_count,
            'average_touches': round(activity_metrics['avg_touches'] or 0, 1),
            'total_activities': activity_metrics['total_activities']
        })
    
    def _update_campaign_metrics(self, lead):
        """Update campaign metrics when lead is created from campaign"""
        # This will be expanded when we implement campaign objectives for leads
        pass