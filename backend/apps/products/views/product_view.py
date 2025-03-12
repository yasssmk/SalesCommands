from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Prefetch, Q
from core.apps_shared_methods import BaseAPIView
from ..models import Product, Pricing
from ..serializers import ProductSerializer, CompetitorSummarySerializer


class ProductAPIView(BaseAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    entity_name = 'product'
    mass_update_allowed_fields = {
        'description', 'key_features', 'key_benefits', 
        'typical_implementation_time', 'target_category_ids'
    }

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

        # Filter by implementation time
        max_impl_time = self.request.query_params.get('max_implementation_time')
        if max_impl_time:
            filters['typical_implementation_time__lte'] = max_impl_time

        # Apply filters
        if filters:
            if 'Q' in filters:
                q_filter = filters.pop('Q')
                queryset = queryset.filter(q_filter)
            queryset = queryset.filter(**filters)

        # Optimize queries
        return queryset.prefetch_related(
            'target_categories',
            'competitor_list',
            Prefetch(
                'pricing_models',
                queryset=Pricing.objects.filter(client_id=self.get_client_id())
            )
        ).select_related(
            'created_by',
            'updated_by'
        ).distinct()
        
    @action(detail=True, methods=['get'])
    def competitors(self, request, pk=None):
        """Get competitors for a specific product"""
        product = self.get_object()
        competitors = product.competitor_list.all()
        serializer = CompetitorSummarySerializer(competitors, many=True)
        return Response(serializer.data)