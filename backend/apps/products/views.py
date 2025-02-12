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
        filters = {}
        for field in ['target_category_id']:
            value = self.request.query_params.get(field)
            if value:
                filters[field] = value

        if filters:
            queryset = queryset.filter(**filters)

        # Text search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(product_name__icontains=search) |
                Q(description__icontains=search)
            )

        # Optimize queries
        return queryset.prefetch_related(
            Prefetch(
                'pricing_models',
                queryset=Pricing.objects.filter(
                    client_id=self.get_client_id()
                )
            )
        ).select_related('target_category')

    def post(self, request, *args, **kwargs):
        """Handle POST requests with proper transaction handling"""
        client_id = self.get_client_id()
        data = request.data if isinstance(request.data, list) else [request.data]
        
        created_objects = []
        try:
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
                        return Response(
                            serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST
                        )
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
        return super()._update(request, partial)  # Validation handled in serializer

class PricingAPIView(BaseAPIView):
    queryset = Pricing.objects.all()
    serializer_class = PricingSerializer
    summary_serializer_class = PricingSummarySerializer
    entity_name = 'pricing'
    mass_update_allowed_fields = {
        'base_price', 'unit_price', 'currency', 
        'units_per', 'billing_term'
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
        billing_term = self.request.query_params.get('billing_term')
        if billing_term:
            filters['billing_term'] = billing_term

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

    @action(detail=True, methods=['get'])
    def calculate_price(self, request, pk=None):
        """
        Calculate final price based on pricing model and parameters
        """
        instance = self.get_object()
        
        try:
            # Get quantity parameter
            quantity = request.query_params.get('quantity', 1)
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="quantity must be a number")
                )

            # Calculate total units
            total_units = quantity * instance.units_per

            # Calculate price
            total_price = instance.base_price + (total_units * instance.unit_price)

            return Response({
                'base_price': instance.base_price,
                'unit_price': instance.unit_price,
                'quantity': quantity,
                'units_per': instance.units_per,
                'total_units': total_units,
                'total_price': total_price,
                'currency': instance.currency,
                'billing_term': instance.billing_term
            })

        except Exception as exc:
            return self.handle_exception(exc)

    def post(self, request, *args, **kwargs):
        """Create pricing with validation"""
        try:
            with transaction.atomic():
                return super().post(request, *args, **kwargs)
        except Exception as exc:
            return self.handle_exception(exc)

    def _update(self, request, partial):
        """Update pricing with validation"""
        try:
            with transaction.atomic():
                return super()._update(request, partial)
        except Exception as exc:
            return self.handle_exception(exc)
