# apps/opportunities/views/opportunity_financial_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.opportunities.models import (
    Opportunity, OpportunityLineItem, OpportunityFinancialSummary
)
from apps.opportunities.serializers import (
    OpportunityLineItemSerializer, OpportunityFinancialSummarySerializer
)
from apps.products.models import Product, Pricing


class OpportunityLineItemViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing opportunity line items (products)
    """
    queryset = OpportunityLineItem.objects.all()
    serializer_class = OpportunityLineItemSerializer
    entity_name = 'line_item'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['opportunity', 'product', 'pricing']
    ordering_fields = ['id', 'line_total']
    ordering = ['id']
    
    def get_queryset(self):
        """Get line items for the current client with filters"""
        queryset = OpportunityLineItem.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Optimize queries
        queryset = queryset.select_related(
            'opportunity', 'product', 'pricing'
        )
        
        # Filter by opportunity
        opportunity_id = self.request.query_params.get('opportunity_id')
        if opportunity_id:
            queryset = queryset.filter(opportunity_id=opportunity_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new line item with client scoping"""
        client_id = self.get_client_id()
        line_item = serializer.save(client_id=client_id)
        
        # Update opportunity financials
        line_item.opportunity.update_financials()
        
        return line_item
    
    def perform_update(self, serializer):
        """Update a line item with validation and client scoping"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Validate opportunity ownership
        opportunity = instance.opportunity
        if opportunity.deal_owner != self.request.user and not self.request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only update line items for opportunities assigned to you")
        
        line_item = serializer.save()
        
        # Update opportunity financials
        line_item.opportunity.update_financials()
        
        return line_item
    
    def perform_destroy(self, instance):
        """Delete a line item with validation and client scoping"""
        self.validate_client_id(instance)
        
        # Validate opportunity ownership
        opportunity = instance.opportunity
        if opportunity.deal_owner != self.request.user and not self.request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only delete line items for opportunities assigned to you")
        
        # Store opportunity reference before deletion
        opportunity_ref = opportunity
        
        # Delete the line item
        instance.delete()
        
        # Update opportunity financials
        opportunity_ref.update_financials()
    
    @action(detail=False, methods=['get'])
    def available_products(self, request):
        """Get products available for adding to an opportunity"""
        # Get products for the current client
        products = Product.objects.filter(
            client_id=self.get_client_id()
        ).select_related().prefetch_related('pricing_models')
        
        # Serialize products with minimal info
        data = []
        for product in products:
            pricing_options = []
            for pricing in product.pricing_models.all():
                pricing_options.append({
                    'id': pricing.id,
                    'pricing_type': pricing.pricing_type,
                    'pricing_type_display': pricing.get_pricing_type_display(),
                    'unit_price': pricing.unit_price,
                    'base_price': pricing.base_price,
                    'currency': pricing.currency,
                    'contract_payment_term': pricing.contract_payment_term,
                    'contract_payment_term_display': pricing.get_contract_payment_term_display(),
                    'unit_of_measure': pricing.unit_of_measure,
                    'revenue_type': pricing.get_recurrency_label()
                })
            
            data.append({
                'id': product.id,
                'product_name': product.product_name,
                'description': product.description,
                'pricing_options': pricing_options
            })
        
        return Response(data)


class OpportunityFinancialSummaryViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing opportunity financial summaries
    """
    queryset = OpportunityFinancialSummary.objects.all()
    serializer_class = OpportunityFinancialSummarySerializer
    entity_name = 'financial_summary'
    http_method_names = ['get', 'patch', 'head', 'options']  # Only allow GET and PATCH
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['opportunity', 'forecast_category']
    
    def get_queryset(self):
        """Get financial summaries for the current client with filters"""
        queryset = OpportunityFinancialSummary.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Optimize queries
        queryset = queryset.select_related('opportunity')
        
        return queryset
    
    def perform_update(self, serializer):
        """Update a financial summary with validation and client scoping"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Validate opportunity ownership
        opportunity = instance.opportunity
        if opportunity.deal_owner != self.request.user and not self.request.user.has_perm('opportunities.change_opportunity'):
            raise StandardizedValidationError("You can only update financial summaries for opportunities assigned to you")
        
        # Only allow updating forecast_category and probability
        if set(serializer.validated_data.keys()) - {'forecast_category', 'probability'}:
            raise StandardizedValidationError("Only forecast_category and probability can be updated")
        
        summary = serializer.save()
        
        # Create history entry for probability change
        if 'probability' in serializer.validated_data:
            opportunity.create_history_entry(
                'CUSTOM',
                f"Probability updated to {summary.probability}%"
            )
        
        # Create history entry for forecast category change
        if 'forecast_category' in serializer.validated_data:
            opportunity.create_history_entry(
                'CUSTOM',
                f"Forecast category updated to {summary.get_forecast_category_display()}"
            )
        
        return summary
    
    @action(detail=False, methods=['get'])
    def forecast(self, request):
        """Get forecast summary by category"""
        # Get financial summaries for the current client
        queryset = self.get_queryset()
        
        # Group by forecast category
        forecast_data = {}
        for category_choice in OpportunityFinancialSummary.ForecastCategory.choices:
            category_code = category_choice[0]
            category_display = category_choice[1]
            
            # Get summaries for this category
            category_summaries = queryset.filter(forecast_category=category_code)
            
            # Calculate totals
            count = category_summaries.count()
            total_amount = category_summaries.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            expected_revenue = category_summaries.aggregate(Sum('expected_revenue'))['expected_revenue__sum'] or 0
            
            forecast_data[category_code] = {
                'display': category_display,
                'count': count,
                'total_amount': total_amount,
                'expected_revenue': expected_revenue
            }
        
        # Calculate grand totals
        grand_totals = {
            'count': queryset.count(),
            'total_amount': queryset.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'expected_revenue': queryset.aggregate(Sum('expected_revenue'))['expected_revenue__sum'] or 0
        }
        
        return Response({
            'forecast_categories': forecast_data,
            'totals': grand_totals,
            'currency': 'USD'  # Default, could be dynamic
        })