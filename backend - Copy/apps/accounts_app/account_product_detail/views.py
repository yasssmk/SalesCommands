from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.accounts_app.accounts.models import Account
from django.db import transaction
from .models import AccountProductDetail
from .serializers import AccountProductDetailSerializer
from apps.accounts_app.accounts.models import Account
from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from decimal import Decimal

class AccountProductDetailView(BaseAPIView):
    """
    API View for managing AccountProductDetail instances with proper client scoping.
    Supports CRUD operations and additional analysis endpoints.
    """
    queryset = AccountProductDetail.objects.select_related(
        'account',
        'product',
        'selected_pricing'
    ).prefetch_related('target_org_units')
    
    serializer_class = AccountProductDetailSerializer
    entity_name = 'account_product_detail'
    
    def get_queryset(self):
        """Get base queryset filtered by client and optional filters."""
        queryset = super().get_queryset()
        
        # Apply additional filters if provided
        if self.request.method == 'GET':
            account_id = self.request.query_params.get('account')
            if account_id:
                queryset = queryset.filter(account_id=account_id)
                
            product_id = self.request.query_params.get('product_id')
            if product_id:
                queryset = queryset.filter(product_id=product_id)
                
            revenue_type = self.request.query_params.get('revenue_type')
            if revenue_type:
                queryset = queryset.filter(revenue_type=revenue_type)
            
        return self.filter_queryset_by_client(queryset)

    def get(self, request, *args, **kwargs):
        """Handle GET requests for list, detail, summary and whitespace."""
        if 'summary' in request.path:
            return self.get_summary(request)
        elif 'whitespace' in request.path:
            return self.get_whitespace(request)
        return super().get(request, *args, **kwargs)

    def get_summary(self, request):
        """Get revenue summary grouped by type."""
        queryset = self.get_queryset()
        
        # Verify account filter is provided for summary
        account_id = request.query_params.get('account')
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Account ID")
            )
        
        summary = {
            'MRR': Decimal('0.00'),
            'QRR': Decimal('0.00'),
            'ARR': Decimal('0.00'),
            'ONE_TIME': Decimal('0.00'),
            'total_products': 0
        }
        
        # Aggregate revenue by type
        revenue_summary = queryset.values('revenue_type').annotate(
            total=Coalesce(Sum('potential_revenue'), Value(0, output_field=DecimalField()))
        )
        
        for item in revenue_summary:
            summary[item['revenue_type']] = item['total']
        
        summary['total_products'] = queryset.count()
        
        # Add currency information if available
        first_record = queryset.first()
        if first_record and first_record.selected_pricing:
            summary['currency'] = first_record.selected_pricing.currency
            
        return Response(summary)

    def get_whitespace(self, request):
        """Get products not yet analyzed for the account."""
        account_id = request.query_params.get('account')
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Account ID")
            )
            
        # Get analyzed products for the account
        analyzed_products = self.get_queryset().filter(
            account_id=account_id
        ).values_list('product_id', flat=True)
        
        # Get available products not yet analyzed
        whitespace_products = Product.objects.filter(
            client_id=self.get_client_id()
        ).exclude(
            id__in=analyzed_products
        )
        
        return Response(ProductSerializer(whitespace_products, many=True).data)

    def perform_create(self, serializer):
        """Create instance with automatic client_id."""
        try:
            with transaction.atomic():
                instance = serializer.save(
                    client_id=self.get_client_id(),
                    user=self.request.user
                )
                self.validate_client_id(instance)
                return instance
                
        except Exception as e:
            raise StandardizedValidationError(str(e))