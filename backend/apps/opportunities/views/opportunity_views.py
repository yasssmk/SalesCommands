# apps/opportunities/views/opportunity_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.opportunities.models import (
    Opportunity, OpportunityFinancialSummary, OpportunityLineItem,
    OpportunitySource, OpportunityActivity, OpportunityHistory
)
from apps.opportunities.serializers import (
    OpportunitySerializer, OpportunityListSerializer, OpportunityWithFinancialsSerializer,
    OpportunityLineItemSerializer, OpportunityFinancialSummarySerializer,
    OpportunitySourceSerializer, OpportunityActivitySerializer, OpportunityHistorySerializer,
    LeadConversionSerializer
)
from apps.leads.models import Lead
from end_users.models import User


class OpportunityViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing opportunities
    """
    queryset = Opportunity.objects.all()
    serializer_class = OpportunitySerializer
    entity_name = 'opportunity'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'opportunity_type', 'deal_owner', 'account']
    search_fields = ['title', 'description', 'contact__first_name', 'contact__last_name', 'account__company_name']
    ordering_fields = ['created_at', 'date_open', 'expected_close_date', 'title']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return OpportunityListSerializer
        elif self.action in ['retrieve', 'with_financials']:
            return OpportunityWithFinancialsSerializer
        elif self.action == 'convert_lead':
            return LeadConversionSerializer
        return OpportunitySerializer
    
    def get_serializer_context(self):
        """Add client_id to serializer context"""
        context = super().get_serializer_context()
        context['client_id'] = self.get_client_id()
        return context
    
    def get_queryset(self):
        """Get opportunities for the current client with filters"""
        queryset = Opportunity.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Prefetch related objects for performance
        queryset = queryset.select_related(
            'account', 'contact', 'deal_owner', 'source_lead'
        ).prefetch_related(
            'line_items', 'line_items__product', 'line_items__pricing',
            'activity_links', 'activity_links__activity',
            'history'
        )
        
        # Filter by owner
        my_opportunities = self.request.query_params.get('my_opportunities', None)
        if my_opportunities and my_opportunities.lower() == 'true':
            queryset = queryset.filter(deal_owner=self.request.user)
        
        # Filter by date range
        created_after = self.request.query_params.get('created_after', None)
        created_before = self.request.query_params.get('created_before', None)
        
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        # Filter by expected close date range
        close_after = self.request.query_params.get('close_after', None)
        close_before = self.request.query_params.get('close_before', None)
        
        if close_after:
            queryset = queryset.filter(expected_close_date__gte=close_after)
        
        if close_before:
            queryset = queryset.filter(expected_close_date__lte=close_before)
        
        # Filter by financial metrics
        min_amount = self.request.query_params.get('min_amount', None)
        max_amount = self.request.query_params.get('max_amount', None)
        
        if min_amount:
            queryset = queryset.filter(financial_summary__total_amount__gte=min_amount)
        
        if max_amount:
            queryset = queryset.filter(financial_summary__total_amount__lte=max_amount)
        
        min_probability = self.request.query_params.get('min_probability', None)
        max_probability = self.request.query_params.get('max_probability', None)
        
        if min_probability:
            queryset = queryset.filter(financial_summary__probability__gte=min_probability)
        
        if max_probability:
            queryset = queryset.filter(financial_summary__probability__lte=max_probability)
        
        # Filter by forecast category
        forecast_category = self.request.query_params.get('forecast_category', None)
        if forecast_category:
            queryset = queryset.filter(financial_summary__forecast_category=forecast_category)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new opportunity with client scoping"""
        client_id = self.get_client_id()
        opportunity = serializer.save(client_id=client_id, user=self.request.user)
        
        # Create financial summary if not exists
        OpportunityFinancialSummary.objects.get_or_create(opportunity=opportunity)
        
        return opportunity
    
    def perform_update(self, serializer):
        """Update an opportunity with validation and client scoping"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Prevent client_id modification
        if 'client_id' in serializer.validated_data:
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_IMMUTABLE)
        
        # Check if user has permission to update this opportunity
        if instance.deal_owner != self.request.user and not self.request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only update opportunities assigned to you")
        
        return serializer.save(user=self.request.user)
    
    def perform_destroy(self, instance):
        """Delete an opportunity with validation and client scoping"""
        self.validate_client_id(instance)
        
        # Check if user has permission to delete this opportunity
        if instance.deal_owner != self.request.user and not self.request.user.has_perm('opportunities.delete_opportunity'):
            raise StandardizedValidationError("You can only delete opportunities assigned to you")
        
        # Don't allow deletion of won/lost opportunities
        if instance.status in [Opportunity.OpportunityStatus.WON, Opportunity.OpportunityStatus.LOST]:
            raise StandardizedValidationError("Cannot delete closed opportunities")
        
        instance.delete()
    
    @action(detail=True, methods=['get'])
    def with_financials(self, request, pk=None):
        """Get opportunity with detailed financial information"""
        opportunity = self.get_object()
        serializer = self.get_serializer(opportunity)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_as_won(self, request, pk=None):
        """Mark opportunity as won"""
        opportunity = self.get_object()
        
        # Validate ownership
        if opportunity.deal_owner != request.user and not request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only update opportunities assigned to you")
        
        # Check if already won
        if opportunity.status == Opportunity.OpportunityStatus.WON:
            return Response({
                'success': False,
                'message': 'Opportunity is already marked as won'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get close date if provided, otherwise use today
        close_date = request.data.get('close_date', timezone.now().date())
        notes = request.data.get('notes')
        
        # Mark as won
        opportunity.mark_as_won(close_date=close_date)
        
        # Add notes if provided
        if notes:
            if opportunity.notes:
                opportunity.notes += f"\n\nWon: {notes}"
            else:
                opportunity.notes = f"Won: {notes}"
            opportunity.save(update_fields=['notes'])
        
        serializer = OpportunitySerializer(opportunity, context={'client_id': self.get_client_id()})
        return Response({
            'success': True,
            'message': 'Opportunity marked as won',
            'opportunity': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def mark_as_lost(self, request, pk=None):
        """Mark opportunity as lost"""
        opportunity = self.get_object()
        
        # Validate ownership
        if opportunity.deal_owner != request.user and not request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only update opportunities assigned to you")
        
        # Check if already lost
        if opportunity.status == Opportunity.OpportunityStatus.LOST:
            return Response({
                'success': False,
                'message': 'Opportunity is already marked as lost'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get close date and reason
        close_date = request.data.get('close_date', timezone.now().date())
        reason = request.data.get('reason')
        
        # Mark as lost
        opportunity.mark_as_lost(reason=reason, close_date=close_date)
        
        serializer = OpportunitySerializer(opportunity, context={'client_id': self.get_client_id()})
        return Response({
            'success': True,
            'message': 'Opportunity marked as lost',
            'opportunity': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign opportunity to a different user"""
        opportunity = self.get_object()
        
        # Check permission
        if not request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You don't have permission to reassign opportunities")
        
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
            old_assignee = opportunity.deal_owner
            opportunity.deal_owner = new_assignee
            opportunity.save()
            
            # Create history entry
            opportunity.create_history_entry(
                'OWNER_CHANGE',
                f"Reassigned from {old_assignee.get_full_name() if old_assignee else 'Unassigned'} to {new_assignee.get_full_name()}"
            )
            
            return Response({
                'success': True,
                'message': f'Opportunity reassigned to {new_assignee.get_full_name()}',
                'opportunity': OpportunitySerializer(opportunity, context={'client_id': self.get_client_id()}).data
            })
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def convert_lead(self, request):
        """Convert a lead to an opportunity"""
        # Validate lead id
        lead_id = request.data.get('lead_id')
        if not lead_id:
            return Response({
                'success': False,
                'error': 'lead_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get the lead and validate ownership
            lead = Lead.objects.get(id=lead_id, client_id=self.get_client_id())
            
            if lead.assigned_to != request.user and not request.user.has_perm('leads.change_lead'):
                raise StandardizedValidationError("You can only convert leads assigned to you")
            
            # Check if lead can be converted
            if not lead.can_convert():
                return Response({
                    'success': False,
                    'message': 'Lead must be qualified and not already converted'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate conversion data
            serializer = LeadConversionSerializer(
                data=request.data,
                context={'client_id': self.get_client_id()}
            )
            serializer.is_valid(raise_exception=True)
            
            # Get validated data
            opportunity_data = serializer.validated_data
            assign_to = opportunity_data.pop('assign_to', None)
            conversion_notes = opportunity_data.pop('conversion_notes', None)
            
            # Create the opportunity
            opportunity = Opportunity.objects.create(
                account=lead.account,
                contact=lead.contact,
                deal_owner=lead.assigned_to,  # Initially assign to lead owner
                title=opportunity_data['title'],
                description=opportunity_data.get('description', ''),
                opportunity_type=opportunity_data.get('opportunity_type', Opportunity.OpportunityType.NEW_BUSINESS),
                expected_close_date=opportunity_data['expected_close_date'],
                notes=opportunity_data.get('notes', ''),
                client_id=self.get_client_id(),
                created_by=request.user,
                updated_by=request.user
            )
            
            # Create financial summary
            OpportunityFinancialSummary.objects.create(opportunity=opportunity)
            
            # Create source tracking
            source = OpportunitySource.from_lead(
                opportunity=opportunity,
                lead=lead,
                assignee=assign_to,
                notes=conversion_notes
            )
            
            # Update the lead
            lead.lead_status = Lead.LeadStatus.CONVERTED
            lead.conversion_date = timezone.now()
            lead.converted_to_opportunity = opportunity
            lead.save()
            
            # Transfer lead activities to opportunity
            if lead.activities.exists():
                for activity in lead.activities.all():
                    OpportunityActivity.objects.create(
                        opportunity=opportunity,
                        activity=activity,
                        created_by=request.user
                    )
            
            return Response({
                'success': True,
                'message': 'Lead converted to opportunity successfully',
                'opportunity': OpportunityWithFinancialsSerializer(
                    opportunity, 
                    context={'client_id': self.get_client_id()}
                ).data,
                'requires_approval': source.conversion_status == OpportunitySource.ConversionStatus.PENDING
            })
            
        except Lead.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Lead not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get history for an opportunity"""
        opportunity = self.get_object()
        history = opportunity.history.all().order_by('-change_date')
        serializer = OpportunityHistorySerializer(history, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary statistics for opportunities"""
        queryset = self.get_queryset()
        
        # Calculate statistics
        total_opportunities = queryset.count()
        
        # Status breakdown
        status_counts = {}
        for status_choice in Opportunity.OpportunityStatus.choices:
            status_code = status_choice[0]
            status_display = status_choice[1]
            count = queryset.filter(status=status_code).count()
            status_counts[status_code] = {
                'display': status_display,
                'count': count
            }
        
        # Type breakdown
        type_counts = {}
        for type_choice in Opportunity.OpportunityType.choices:
            type_code = type_choice[0]
            type_display = type_choice[1]
            count = queryset.filter(opportunity_type=type_code).count()
            type_counts[type_code] = {
                'display': type_display,
                'count': count
            }
        
        # Financial metrics
        with_financials = queryset.filter(financial_summary__isnull=False)
        
        total_value = 0
        won_value = 0
        expected_revenue = 0
        
        if with_financials.exists():
            financial_metrics = with_financials.aggregate(
                total_value=Sum('financial_summary__total_amount'),
                won_value=Sum('financial_summary__total_amount', filter=Q(status='WON')),
                expected_revenue=Sum('financial_summary__expected_revenue')
            )
            
            total_value = financial_metrics['total_value'] or 0
            won_value = financial_metrics['won_value'] or 0
            expected_revenue = financial_metrics['expected_revenue'] or 0
        
        # Win rate
        closed_count = queryset.filter(status__in=['WON', 'LOST']).count()
        won_count = queryset.filter(status='WON').count()
        win_rate = (won_count / closed_count * 100) if closed_count > 0 else 0
        
        # Average sales cycle (days)
        closed_opps_with_dates = queryset.filter(
            status__in=['WON', 'LOST'],
            date_open__isnull=False,
            closed_date__isnull=False
        )
        
        avg_sales_cycle = 0
        if closed_opps_with_dates.exists():
            # This is a bit tricky in Django ORM, so we'll calculate manually
            total_days = 0
            count = 0
            
            for opp in closed_opps_with_dates:
                delta = opp.closed_date - opp.date_open.date()
                total_days += delta.days
                count += 1
            
            avg_sales_cycle = total_days / count if count > 0 else 0
        
        return Response({
            'total_opportunities': total_opportunities,
            'status_breakdown': status_counts,
            'type_breakdown': type_counts,
            'financial_metrics': {
                'total_value': total_value,
                'won_value': won_value,
                'expected_revenue': expected_revenue,
                'currency': 'USD'  # Default, could be dynamic
            },
            'win_rate': round(win_rate, 1),
            'average_sales_cycle_days': round(avg_sales_cycle, 1),
            'closed_count': closed_count,
            'won_count': won_count
        })