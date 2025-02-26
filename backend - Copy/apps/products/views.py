from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Prefetch, Q
from core.apps_shared_methods import BaseAPIView
from core.error_messages import CoreErrorMessages
from .models import Product, Pricing
from .serializers import (
    ProductSerializer, PricingSerializer, PricingSummarySerializer
)
from core.exceptions import StandardizedValidationError


class ProductAPIView(BaseAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    entity_name = 'product'
    mass_update_allowed_fields = {'description', 'value_proposition', 
                                'potential_cons', 'competitors', 'target_category_id'}

    def clean_data(self, data):
        """Clean and prepare data before serializer validation"""
        cleaned_data = data.copy()

        # Handle target_category_id
        if 'target_category_id' in cleaned_data:
            category_id = cleaned_data.pop('target_category_id', None)
            # Convert empty string or None to empty list
            if not category_id or str(category_id).strip() == '':
                cleaned_data['target_category_ids'] = []
            else:
                cleaned_data['target_category_ids'] = [category_id]

        return cleaned_data

    def get_queryset(self):
        """Get filtered and optimized queryset"""
        queryset = super().get_queryset()
        
        filters = {}
        
        # Filter by target category
        target_category_id = self.request.query_params.get('target_category_id')
        if target_category_id:
            filters['target_categories__id'] = target_category_id

        # Text search
        search = self.request.query_params.get('search')
        if search:
            filters['Q'] = Q(product_name__icontains=search) | Q(description__icontains=search)

        # Apply filters
        if filters:
            if 'Q' in filters:
                q_filter = filters.pop('Q')
                queryset = queryset.filter(q_filter)
            queryset = queryset.filter(**filters)

        # Optimize queries
        return queryset.prefetch_related(
            'target_categories',
            Prefetch(
                'pricing_models',
                queryset=Pricing.objects.filter(client_id=self.get_client_id())
            )
        ).select_related(
            'created_by',
            'updated_by'
        ).distinct()


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
    
