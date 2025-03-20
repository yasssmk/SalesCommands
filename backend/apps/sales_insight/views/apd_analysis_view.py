# # apps/sales_insight/views/apd_analysis_view.py

# from rest_framework import status
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from core.error_messages import CoreErrorMessages
# from core.exceptions import StandardizedValidationError
# from core.apps_shared_methods import BaseAPIView
# from apps.accounts_app.accounts.models import Account
# from apps.accounts_app.org_units.models import AccountOrganizationUnit
# from apps.products.models import Product
# from apps.accounts_app.account_product_detail.models import AccountProductDetail
# from backend.apps.sales_insight.services.apr_analysis_service import APDAnalysisService
# from backend.apps.sales_insight.services.apr_update_service import APDUpdateService
# import json

# class APDAnalysisView(BaseAPIView):
#     """
#     API View for analyzing account/org unit signals against products
#     and automatically updating Account Product Detail records with insights.
#     """
    
#     def post(self, request, *args, **kwargs):
#         """
#         Analyze account/org unit against product and automatically update APD.
        
#         POST /api/insights/analyze-apd/
        
#         Required fields:
#             - account_id: ID of the account to analyze
#             - product_id: ID of the product to compare against
            
#         Optional fields:
#             - org_unit_id: ID of a specific org unit to analyze
#             - contact_id: ID of a specific contact to include in analysis
#         """
#         try:
#             # Validate required fields
#             if 'account_id' not in request.data:
#                 raise StandardizedValidationError(
#                     CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
#                 )
                
#             if 'product_id' not in request.data:
#                 raise StandardizedValidationError(
#                     CoreErrorMessages.REQUIRED_FIELD.format(field="product_id")
#                 )
            
#             # Get input parameters
#             account_id = request.data['account_id']
#             product_id = request.data['product_id']
#             org_unit_id = request.data.get('org_unit_id')
#             contact_id = request.data.get('contact_id')
            
#             # Validate entities exist and user has access
#             try:
#                 account = Account.objects.get(id=account_id)
#                 self.validate_client_id(account)
#             except Account.DoesNotExist:
#                 raise StandardizedValidationError(
#                     CoreErrorMessages.OBJECT_NOT_FOUND
#                 )
                
#             try:
#                 product = Product.objects.get(id=product_id)
#                 self.validate_client_id(product)
#             except Product.DoesNotExist:
#                 raise StandardizedValidationError(
#                     CoreErrorMessages.OBJECT_NOT_FOUND
#                 )
            
#             # Verify org_unit if specified
#             if org_unit_id:
#                 try:
#                     org_unit = AccountOrganizationUnit.objects.get(id=org_unit_id)
#                     self.validate_client_id(org_unit)
                    
#                     # Verify org unit belongs to the account
#                     if str(org_unit.account_id) != str(account.id):
#                         raise StandardizedValidationError(
#                             CoreErrorMessages.INVALID_FIELD.format(
#                                 field="Organization unit must belong to the specified account"
#                             )
#                         )
#                 except AccountOrganizationUnit.DoesNotExist:
#                     raise StandardizedValidationError(
#                         CoreErrorMessages.OBJECT_NOT_FOUND
#                     )
#             # Call the analysis service
#             try:
#                 analysis_results = APDAnalysisService.analyze_product_alignment(
#                     account_id=account_id,
#                     product_id=product_id,
#                     org_unit_id=org_unit_id,
#                     contact_id=contact_id
#                 )
#             except Exception as analysis_error:
#                 raise StandardizedValidationError(
#                     CoreErrorMessages.SERVICE_ERROR
#                 )
                
#             # Check if we have valid analysis results
#             if "message" in analysis_results and "analysis_results" not in analysis_results:
#                 # Handle case where there's not enough data for analysis
#                 return Response({
#                     'success': False,
#                     'message': analysis_results["message"],
#                     'account_id': str(account_id),
#                     'product_id': str(product_id)
#                 }, status=status.HTTP_200_OK)
            
#             # Automatically update the APD with analysis results
#             apd, created = APDUpdateService.apply_analysis_to_apd(
#                 analysis_results=analysis_results,
#                 account_id=account_id,
#                 product_id=product_id,
#                 user=request.user
#             )
            
#             # Prepare response data
#             response_data = {
#                 'success': True,
#                 'account_id': str(account_id),
#                 'entity_type': analysis_results.get('entity_type'),
#                 'entity_id': analysis_results.get('entity_id'),
#                 'product_id': str(product_id),
#                 'entity_name': analysis_results.get('entity_name'),
#                 'product_name': analysis_results.get('product_name'),
#                 'coverage_stats': analysis_results.get('coverage_stats'),
#                 'apd_updated': True,
#                 'apd_id': str(apd.id),
#                 'apd_created': created,
#                 'apd_relevance_score': apd.ai_relevance_score
#             }
            
#             # Include signal quality metadata for UI highlighting
#             if "signal_quality" in analysis_results:
#                 response_data['signal_quality'] = analysis_results['signal_quality']
            
#             # Include analysis results
#             response_data['analysis_results'] = analysis_results.get('analysis_results', {})
            
#             return Response(response_data, status=status.HTTP_200_OK)
                
#         except Exception as e:
#             return self.handle_exception(e)
    