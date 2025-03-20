# apps/sales_insight/views/apd_analysis_view.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.accounts.models import Account, AccountProductRelationship
from apps.products.models import Product
from ..services.apr_analysis_service import APRAnalysisService
from apps.sales_insight.services.apr_update_service import APRUpdateService
import json

class APRAnalysisView(BaseAPIView):
    """
    API View for analyzing account/org unit signals against products
    and automatically updating Account Product Detail records with insights.
    """
    
    def post(self, request, *args, **kwargs):
        """
        Analyze account/org unit against product and automatically update APD.
        
        POST /api/insights/analyze-apd/
        
        Required fields:
            - account_id: ID of the account to analyze
            - product_id: ID of the product to compare against
            
        Optional fields:
            - org_unit_id: ID of a specific org unit to analyze
            - contact_id: ID of a specific contact to include in analysis
        """
        try:
            # Validate required fields
            if 'account_id' not in request.data:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
                )
                
            if 'product_id' not in request.data:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="product_id")
                )
            
            # Get input parameters
            account_id = request.data['account_id']
            product_id = request.data['product_id']
            contact_id = request.data.get('contact_id')
            
            # Validate entities exist and user has access
            try:
                account = Account.objects.get(id=account_id)
                self.validate_client_id(account)
            except Account.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
                
            try:
                product = Product.objects.get(id=product_id)
                self.validate_client_id(product)
            except Product.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
            

            # Call the analysis service
            try:
                analysis_results = APRAnalysisService.analyze_product_alignment(
                    account_id=account_id,
                    product_id=product_id,
                    contact_id=contact_id
                )
            except Exception as analysis_error:
                raise StandardizedValidationError(
                    CoreErrorMessages.SERVICE_ERROR
                )
                
            # Check if we have valid analysis results
            if "message" in analysis_results and "analysis_results" not in analysis_results:
                # Handle case where there's not enough data for analysis
                return Response({
                    'success': False,
                    'message': analysis_results["message"],
                    'account_id': str(account_id),
                    'product_id': str(product_id)
                }, status=status.HTTP_200_OK)
            
            # Automatically update the APD with analysis results
            apd, created = APRUpdateService.apply_analysis_to_apd(
                analysis_results=analysis_results,
                account_id=account_id,
                product_id=product_id,
                user=request.user
            )
            
            # Prepare response data
            response_data = {
                'success': True,
                'account_id': str(account_id),
                'entity_type': analysis_results.get('entity_type'),
                'entity_id': analysis_results.get('entity_id'),
                'product_id': str(product_id),
                'entity_name': analysis_results.get('entity_name'),
                'product_name': analysis_results.get('product_name'),
                'coverage_stats': analysis_results.get('coverage_stats'),
                'apr_updated': True,
                'apr_id': str(apd.id),
                'apr_created': created,
                'apr_relevance_score': apd.ai_relevance_score
            }
            
            # Include signal quality metadata for UI highlighting
            if "signal_quality" in analysis_results:
                response_data['signal_quality'] = analysis_results['signal_quality']
            
            # Include analysis results
            response_data['analysis_results'] = analysis_results.get('analysis_results', {})
            
            return Response(response_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            return self.handle_exception(e)
    