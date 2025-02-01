from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Prefetch, Q
from core.apps_shared_methods import BaseAPIView
from core.error_messages import CoreErrorMessages
from .models import Product, Pricing, BillingCycle
from .serializers import (
    ProductSerializer, PricingSerializer, BillingCycleSerializer
)
from django.core.exceptions import ValidationError
from core.exceptions import StandardizedValidationError


class ProductAPIView(BaseAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    entity_name = 'product'
    mass_update_allowed_fields = {'product_type', 'description', 'value_proposition', 
                                'potential_cons', 'competitors', 'target_category_id'}

    def get_queryset(self):
        """Get filtered and optimized queryset"""
        queryset = super().get_queryset()
        
        # Apply filters from query parameters
        filters = {}
        for field in ['product_type', 'target_category_id']:
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
                ).prefetch_related('available_cycles')
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
    entity_name = 'pricing'
    mass_update_allowed_fields = {'base_price', 'currency'}

    def get_queryset(self):
        """Get filtered queryset"""
        queryset = super().get_queryset()
        
        # Apply filters
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        pricing_type = self.request.query_params.get('pricing_type')
        if pricing_type:
            queryset = queryset.filter(pricing_type=pricing_type)

        return queryset.prefetch_related('available_cycles').select_related('product')

class BillingCycleAPIView(BaseAPIView):
    queryset = BillingCycle.objects.all()
    serializer_class = BillingCycleSerializer
    entity_name = 'billing_cycle'
    mass_update_allowed_fields = {'multiplier'}

    def get_queryset(self):
        """Get filtered queryset"""
        queryset = super().get_queryset()
        
        cycle_type = self.request.query_params.get('cycle_type')
        if cycle_type:
            queryset = queryset.filter(cycle_type=cycle_type)

        return queryset

    def delete(self, request, *args, **kwargs):
        """Handle deletion with dependency check"""
        try:
            with transaction.atomic():
                objects = self.get_objects()
                if not objects:
                    raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

                # Check for dependencies
                for obj in objects:
                    if obj.pricing_models.exists():
                        raise StandardizedValidationError(CoreErrorMessages.OBJECT_IN_USE.format(fields={obj.name}))

                return super().delete(request, *args, **kwargs)
        except Exception as exc:
            return self.handle_exception(exc)
