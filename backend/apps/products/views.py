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

    def get_queryset(self):
        """Get filtered and optimized queryset"""
        queryset = super().get_queryset()
        
        # Apply filters from query parameters
        # Filter by target category
        target_category_id = self.request.query_params.get('target_category_id')
        if target_category_id:
            queryset = queryset.filter(target_categories__id=target_category_id)

        # Text search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(product_name__icontains=search) |
                Q(description__icontains=search)
            )

        # Optimize queries
        return queryset.prefetch_related(
            'target_categories',
            Prefetch(
                'pricing_models',
                queryset=Pricing.objects.filter(
                    client_id=self.get_client_id()
                )
            )
        ).select_related(
            'created_by',
            'updated_by'
        ).distinct()

    def post(self, request, *args, **kwargs):
        """Handle POST requests with proper transaction handling"""
        try:
            client_id = self.get_client_id()
            data = request.data if isinstance(request.data, list) else [request.data]
            
            created_objects = []
            with transaction.atomic():
                for item in data:
                    serializer = self.serializer_class(
                        data=item,
                        context={
                            'request': request,
                            'client_id': client_id
                        }
                    )
                    if not serializer.is_valid():
                        raise StandardizedValidationError(serializer.errors)
                        
                    instance = serializer.save(client_id=client_id)
                    created_objects.append(instance)

            # Return paginated response for batch creations if needed
            if len(created_objects) > 1 and self.paginator is not None:
                page = self.paginate_queryset(created_objects)
                if page is not None:
                    serializer = self.serializer_class(page, many=True)
                    return self.get_paginated_response(serializer.data)

            serializer = self.serializer_class(created_objects, many=True)
            return Response(
                serializer.data if len(created_objects) > 1 else serializer.data[0],
                status=status.HTTP_201_CREATED
            )
        
        except Exception as exc:
            return self.handle_exception(exc)
        

    def _update(self, request, partial):
        """Update product(s)"""
        try:
            return super()._update(request, partial)
        except Exception as exc:
            return self.handle_exception(exc)

class PricingAPIView(BaseAPIView):
    queryset = Pricing.objects.all()
    serializer_class = PricingSerializer
    summary_serializer_class = PricingSummarySerializer
    entity_name = 'pricing'
    mass_update_allowed_fields = {
        'base_price', 'unit_price', 'currency', 
        'units_per', 'billing_term', 'contract_payment_term'
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

    def post(self, request, *args, **kwargs):
        """Create pricing with validation"""
        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                if not serializer.is_valid():
                    raise StandardizedValidationError(serializer.errors)
                    
                instance = serializer.save(client_id=self.get_client_id())
                return Response(
                    self.get_serializer(instance).data,
                    status=status.HTTP_201_CREATED
                )
        except Exception as exc:
            return self.handle_exception(exc)

    def _update(self, request, partial):
        """Update pricing with validation"""
        try:
            with transaction.atomic():
                instance = self.get_object()
                serializer = self.get_serializer(
                    instance,
                    data=request.data,
                    partial=partial
                )
                if not serializer.is_valid():
                    raise StandardizedValidationError(serializer.errors)
                    
                updated_instance = serializer.save()
                return Response(self.get_serializer(updated_instance).data)
        except Exception as exc:
            return self.handle_exception(exc)
