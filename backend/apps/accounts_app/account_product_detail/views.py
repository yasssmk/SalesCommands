from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.accounts_app.accounts.models import Account
from .models import AccountProductDetail
from .serializers import AccountProductDetailSerializer
from apps.accounts_app.accounts.models import Account
from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from decimal import Decimal

class AccountProductDetailView(BaseAPIView):
    """
    API View for managing AccountProductDetail instances.
    """
    queryset = AccountProductDetail.objects.all()
    serializer_class = AccountProductDetailSerializer
    entity_name = 'account_product_detail'

    def get_account(self):
        """Get and validate account from URL."""
        account_id = self.kwargs.get('account_id')
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Account ID")
            )
            
        account_queryset = Account.objects.filter(id=account_id)
        account = self.filter_queryset_by_client(account_queryset).first()
        
        if not account:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
        return account

    def get_serializer_context(self):
        """Add account to serializer context."""
        context = super().get_serializer_context()
        context['account'] = self.get_account()
        return context

    def get_queryset(self):
        """Get base queryset filtered by account and client."""
        return super().get_queryset().filter(account=self.get_account())

    def get(self, request, *args, **kwargs):
        if 'summary' in request.path:
            return self.get_summary(request)
        if 'whitespace' in request.path:
            return self.get_whitespace(request)
        return super().get(request, *args, **kwargs)

    def get_summary(self, request):
        """Get revenue summary grouped by type."""
        queryset = self.get_queryset()
        
        summary = {
            'MRR': Decimal('0.00'),
            'QRR': Decimal('0.00'),
            'ARR': Decimal('0.00'),
            'ONE_TIME': Decimal('0.00'),
            'total_products': 0
        }
        
        revenue_summary = queryset.values('revenue_type').annotate(
            total=Coalesce(Sum('potential_revenue'), Value(0, output_field=DecimalField()))
        )
        
        for item in revenue_summary:
            summary[item['revenue_type']] = item['total']
        
        summary['total_products'] = queryset.count()
        return Response(summary)

    def get_whitespace(self, request):
        """Get products not yet analyzed for the account."""
        analyzed_products = self.get_queryset().values_list('product_id', flat=True)
        
        whitespace_products = Product.objects.filter(
            client_id=self.get_client_id()
        ).exclude(
            id__in=analyzed_products
        )
        
        return Response(ProductSerializer(whitespace_products, many=True).data)