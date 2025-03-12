from rest_framework.decorators import action
from core.apps_shared_methods import BaseAPIView
from ..models import  Pricing
from ..serializers import (PricingSerializer, PricingSummarySerializer)



class PricingAPIView(BaseAPIView):
    queryset = Pricing.objects.all()
    serializer_class = PricingSerializer
    summary_serializer_class = PricingSummarySerializer
    entity_name = 'pricing'
    mass_update_allowed_fields = {
        'base_price', 'unit_price', 'currency', 
        'units_per', 'pricing_term', 'contract_payment_term' 
    }

    def get_queryset(self):
        """Get filtered queryset"""
        queryset = super().get_queryset()
        
        # Apply filters
        filters = {}
        
        # Product filter
        product_id = self.request.query_params.get('product_id')
        if product_id:
            filters['product_id'] = product_id

        # Pricing type filter
        pricing_type = self.request.query_params.get('pricing_type')
        if pricing_type:
            filters['pricing_type'] = pricing_type

        # Billing term filter
        pricing_term = self.request.query_params.get('pricing_term')
        if pricing_term:
            filters['pricing_term'] = pricing_term

        # Unit of measure filter
        unit_of_measure = self.request.query_params.get('unit_of_measure')
        if unit_of_measure:
            filters['unit_of_measure'] = unit_of_measure

        queryset = queryset.filter(**filters)

        # Price range filters
        min_price = self.request.query_params.get('min_price')
        if min_price:
            queryset = queryset.filter(base_price__gte=min_price)

        max_price = self.request.query_params.get('max_price')
        if max_price:
            queryset = queryset.filter(base_price__lte=max_price)

        return queryset.select_related('product')

    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.request.query_params.get('summary'):
            return self.summary_serializer_class
        return self.serializer_class
    
