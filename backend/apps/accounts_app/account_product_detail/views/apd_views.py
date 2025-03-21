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
from ..models import AccountProductDetail
from ..serializers import AccountProductDetailSerializer
from apps.accounts_app.accounts.models import Account
from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from decimal import Decimal
from django.shortcuts import redirect
from django.urls import reverse

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
        
        # Filter by analysis-related fields
            has_analysis = self.request.query_params.get('has_analysis')
            if has_analysis in ('true', 'True', '1'):
                queryset = queryset.exclude(
                    objectives_alignment=None, 
                    pain_points_coverage=None,
                    economic_impact=None
                )
                
            min_coverage = self.request.query_params.get('min_coverage')
            if min_coverage and min_coverage.isdigit():
                min_coverage_val = int(min_coverage)
                queryset = queryset.filter(
                    coverage_stats__overall_coverage_percent__gte=min_coverage_val
                )
                
            min_relevance = self.request.query_params.get('min_relevance')
            if min_relevance and min_relevance.replace('.', '', 1).isdigit():
                min_relevance_val = float(min_relevance)
                queryset = queryset.filter(
                    ai_relevance_score__gte=min_relevance_val
                )
            
        return self.filter_queryset_by_client(queryset)

    def get(self, request, *args, **kwargs):
        """Handle GET requests for list, detail, summary and whitespace."""
        if 'summary' in request.path:
            return self.get_summary(request)
        elif 'whitespace' in request.path:
            return self.get_whitespace(request)
        elif 'analysis_summary' in request.path:
            return self.get_analysis_summary(request)
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
        summary['products_with_analysis'] = products_with_analysis
        
        # Calculate average coverage if there are products with analysis
        if products_with_analysis > 0:
            products_with_coverage = queryset.exclude(coverage_stats=None).values_list('coverage_stats', flat=True)
            total_coverage = 0
            valid_coverage_count = 0
            
            for coverage in products_with_coverage:
                if coverage and 'overall_coverage_percent' in coverage:
                    total_coverage += coverage['overall_coverage_percent']
                    valid_coverage_count += 1
            
            if valid_coverage_count > 0:
                summary['avg_coverage_percent'] = round(total_coverage / valid_coverage_count)
        
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
    
    def get_analysis_summary(self, request):
        """Get a summary of analysis data across products for an account."""
        account_id = request.query_params.get('account')
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Account ID")
            )
            
        queryset = self.get_queryset().filter(account_id=account_id)
        
        # Count products by coverage level
        coverage_summary = {
            'high_coverage': 0,    # >75%
            'medium_coverage': 0,  # 50-75%
            'low_coverage': 0,     # 25-50%
            'minimal_coverage': 0, # <25%
            'no_analysis': 0,      # No analysis data
            'top_products': []     # Top 5 products by coverage
        }
        
        # Analyze each APD
        for apd in queryset:
            if not apd.coverage_stats or 'overall_coverage_percent' not in apd.coverage_stats:
                coverage_summary['no_analysis'] += 1
                continue
                
            coverage = apd.coverage_stats['overall_coverage_percent']
            
            if coverage > 75:
                coverage_summary['high_coverage'] += 1
            elif coverage > 50:
                coverage_summary['medium_coverage'] += 1
            elif coverage > 25:
                coverage_summary['low_coverage'] += 1
            else:
                coverage_summary['minimal_coverage'] += 1
        
        # Get top products by coverage
        top_products = queryset.exclude(coverage_stats=None).order_by('-ai_relevance_score')[:5]
        coverage_summary['top_products'] = [
            {
                'id': str(apd.id),
                'product_name': apd.product.product_name,
                'coverage_percent': apd.coverage_stats.get('overall_coverage_percent', 0) if apd.coverage_stats else 0,
                'ai_relevance_score': apd.ai_relevance_score or 0,
                'last_analysis_date': apd.last_analysis_date.isoformat() if apd.last_analysis_date else None
            }
            for apd in top_products
        ]
        
        return Response(coverage_summary)
        
    @action(detail=True, methods=['get'])
    def analysis_details(self, request, pk=None):
        """Get detailed analysis information for a specific APD."""
        apd = self.get_objects([pk]).first()
        if not apd:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
        # Check if analysis data exists
        if not (apd.objectives_alignment or apd.pain_points_coverage or apd.economic_impact):
            return Response({
                'message': 'No analysis data available for this product',
                'has_analysis': False
            })
            
        # Construct analysis details response
        analysis_details = {
            'has_analysis': True,
            'last_analysis_date': apd.last_analysis_date.isoformat() if apd.last_analysis_date else None,
            'coverage_stats': apd.coverage_stats or {},
            'objectives_alignment': apd.objectives_alignment or {},
            'pain_points_coverage': apd.pain_points_coverage or {},
            'economic_impact': apd.economic_impact or {},
            'ai_relevance_score': apd.ai_relevance_score or 0
        }
        
        return Response(analysis_details)

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
            
    @action(detail=True, methods=['post'])
    def update_analysis(self, request, pk=None):
        """
        Update the analysis data for an existing APD.
        This provides a targeted endpoint for updating just the analysis fields.
        """
        apd = self.get_objects([pk]).first()
        if not apd:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
        # Validate data has at least one analysis field
        valid_analysis_fields = ['objectives_alignment', 'pain_points_coverage', 
                                'economic_impact', 'coverage_stats', 'ai_relevance_score']
        
        if not any(field in request.data for field in valid_analysis_fields):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="At least one analysis field must be provided"
                )
            )
        
        # Update only analysis fields
        update_data = {}
        for field in valid_analysis_fields:
            if field in request.data:
                update_data[field] = request.data[field]
                
        # Set last_analysis_date
        update_data['last_analysis_date'] = timezone.now()
        
        # Use serializer for validation but only update specific fields
        serializer = self.serializer_class(
            apd, 
            data=update_data,
            partial=True,
            context={'request': request, 'client_id': self.get_client_id()}
        )
        
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def analyze(self, request, pk=None):
        """
        Trigger analysis for an APD and redirect to the analysis view.
        
        GET /api/account-product-details/{id}/analyze/
        """
        apd = self.get_objects([pk]).first()
        if not apd:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        # Redirect to analysis view with correct parameters
        analysis_url = reverse('analyze_apd')
        redirect_url = f"{analysis_url}?account_id={apd.account_id}&product_id={apd.product_id}"
        
        return redirect(redirect_url)
    
    @action(detail=True, methods=['post'])
    def refresh_analysis(self, request, pk=None):
        """
        Refresh the analysis data for this APD.
        This triggers a new analysis and updates the APD with the results.
        
        POST /api/account-product-details/{id}/refresh-analysis/
        """
        from backend.apps.sales_insight.services.apr_analysis_service import APDAnalysisService
        from backend.apps.sales_insight.services.apr_update_service import APDUpdateService
        
        apd = self.get_objects([pk]).first()
        if not apd:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        try:
            # Run analysis
            analysis_results = APDAnalysisService.analyze_product_alignment(
                account_id=apd.account_id,
                product_id=apd.product_id
            )
            
            # Update APD with results
            updated_apd, _ = APDUpdateService.apply_analysis_to_apd(
                analysis_results=analysis_results,
                account_id=apd.account_id,
                product_id=apd.product_id,
                user=request.user
            )
            
            # Return updated APD
            serializer = self.serializer_class(updated_apd)
            return Response({
                'success': True,
                'message': 'Analysis refreshed successfully',
                'data': serializer.data
            })
        
        except Exception as e:
            return self.handle_exception(e)
        
    # Add this method to your existing AccountProductDetailView class

    @action(detail=True, methods=['get'])
    def tech_relationships(self, request, pk=None):
        """
        Get tech relationships for this APD.
        
        GET /api/account-products/{id}/tech-relationships/
        """
        apd = self.get_objects([pk]).first()
        if not apd:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
        # Check for tech relationships
        relationships = apd.tech_relationships or []
        
        # Get entities with tech stack
        account = apd.account
        org_units = account.accountorganizationunit_set.all()
        
        # Find entities with tech stack
        entities_with_tech = []
        
        # Check account
        if account.current_tech_stack:
            entities_with_tech.append({
                'entity_type': 'ACCOUNT',
                'entity_id': str(account.id),
                'entity_name': account.company_name,
                'tech_count': len(account.current_tech_stack) if isinstance(account.current_tech_stack, list) else 1
            })
        
        # Check org units
        for org_unit in org_units:
            if org_unit.current_tech_stack:
                entities_with_tech.append({
                    'entity_type': 'ORG_UNIT',
                    'entity_id': str(org_unit.id),
                    'entity_name': org_unit.organization_name,
                    'tech_count': len(org_unit.current_tech_stack) if isinstance(org_unit.current_tech_stack, list) else 1
                })
        
        return Response({
            'tech_relationships': relationships,
            'entities_with_tech': entities_with_tech,
            'product_id': str(apd.product_id),
            'product_name': apd.product.product_name
        })