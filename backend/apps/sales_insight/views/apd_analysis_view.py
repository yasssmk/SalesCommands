# apps/sales_insight/views/account_product_alignment_view.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from apps.products.models import Product
from apps.LLM_calls.services import LLMProviderService
from ..services.apd_prompts_service import call_second_llm_for_alignment
import json

class AccountProductAlignmentView(BaseAPIView):
    """
    API View for analyzing account or org unit signals against product information
    to generate comprehensive alignment insights for the Account Product Detail.
    """
    
    def post(self, request, *args, **kwargs):
        """
        Custom post method that analyzes objectives, pain points, and economic factors
        from either an account or organization unit against product benefits.
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
            
            # Get the account
            account_id = request.data['account_id']
            try:
                account = Account.objects.get(id=account_id)
                self.validate_client_id(account)
            except Account.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND.format(entity="Account")
                )
            
            # Get the product
            product_id = request.data['product_id']
            try:
                product = Product.objects.get(id=product_id)
                self.validate_client_id(product)
            except Product.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND.format(entity="Product")
                )
            
            # Determine if we're analyzing an org unit or the main account
            org_unit = None
            org_unit_id = request.data.get('org_unit_id')
            if org_unit_id:
                try:
                    org_unit = AccountOrganizationUnit.objects.get(id=org_unit_id)
                    self.validate_client_id(org_unit)
                    
                    # Verify org unit belongs to the account
                    if str(org_unit.account_id) != str(account.id):
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_FIELD.format(
                                field="Organization unit must belong to the specified account"
                            )
                        )
                except AccountOrganizationUnit.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND.format(entity="Organization Unit")
                    )
            
            # Get objectives and pain points - either from org unit if specified, or from account
            if org_unit:
                objectives = org_unit.objectives or []
                pain_points = org_unit.pain_points or []
                entity_name = f"{org_unit.organization_name} (Org Unit)"
                entity_id = str(org_unit.id)
                entity_type = "org_unit"
            else:
                objectives = account.objectives or []
                pain_points = account.pain_points or []
                entity_name = account.company_name
                entity_id = str(account.id)
                entity_type = "account"
                
            # Check if we have enough data for meaningful analysis
            has_objectives = len(objectives) > 0
            has_pain_points = len(pain_points) > 0
            
            if not has_objectives and not has_pain_points:
                return Response({
                    'success': False,
                    'message': f'No objectives or pain points found for {entity_type} {entity_name}',
                    'account_id': str(account.id),
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'product_id': str(product.id),
                    'results': None
                }, status=status.HTTP_200_OK)
                
            # Get product benefits and features
            product_benefits = product.key_benefits or []
            product_features = product.key_features or []
            
            combined_product_info = product_benefits + product_features
            
            if not combined_product_info:
                return Response({
                    'success': False,
                    'message': 'No benefits or features defined for this product',
                    'account_id': str(account.id),
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'product_id': str(product.id),
                    'results': None
                }, status=status.HTTP_200_OK)
            
            # Call LLM service for comprehensive alignment
            llm_service = LLMProviderService()
            alignment_json = call_second_llm_for_alignment(
                objectives,
                pain_points,
                combined_product_info
            )
            
            # Parse the response
            try:
                if isinstance(alignment_json, str):
                    # Try to extract JSON if it's wrapped in markdown or other text
                    import re
                    json_match = re.search(r'```json\s*(.*?)\s*```', alignment_json, re.DOTALL)
                    if json_match:
                        try:
                            alignment_results = json.loads(json_match.group(1))
                        except json.JSONDecodeError:
                            # If that didn't work, try loading the whole string
                            try:
                                alignment_results = json.loads(alignment_json)
                            except json.JSONDecodeError:
                                alignment_results = {"error": "Failed to parse LLM response"}
                    else:
                        # If no JSON code block, try loading the whole string
                        try:
                            alignment_results = json.loads(alignment_json)
                        except json.JSONDecodeError:
                            alignment_results = {"error": "Failed to parse LLM response"}
                else:
                    alignment_results = alignment_json
            except Exception as e:
                alignment_results = {"error": f"Failed to process LLM response: {str(e)}"}
            
            # Calculate coverage percentage
            coverage_stats = self._calculate_coverage_stats(alignment_results, objectives, pain_points)
            
            response_data = {
                'success': True,
                'account_id': str(account.id),
                'entity_type': entity_type,
                'entity_id': entity_id,
                'product_id': str(product.id),
                'entity_name': entity_name,
                'product_name': product.product_name,
                'coverage_stats': coverage_stats,
                'results': alignment_results
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            return self.handle_exception(e)
    
    def _calculate_coverage_stats(self, alignment_results, objectives, pain_points):
        """
        Calculate coverage statistics based on analysis results
        """
        stats = {
            'objectives_coverage_percent': 0,
            'pain_points_coverage_percent': 0,
            'overall_coverage_percent': 0
        }
        
        # Check if results have the expected structure
        if not alignment_results or "error" in alignment_results:
            return stats
        
        # Calculate objective coverage
        objectives_count = len(objectives)
        covered_objectives = 0
        
        if objectives_count > 0 and 'objectives' in alignment_results:
            for obj in alignment_results['objectives']:
                if obj.get('matchingProductBenefit') and len(obj.get('matchingProductBenefit', [])) > 0:
                    covered_objectives += 1
            
            stats['objectives_coverage_percent'] = round((covered_objectives / objectives_count) * 100)
        
        # Calculate pain points coverage
        pain_points_count = len(pain_points)
        covered_pain_points = 0
        
        if pain_points_count > 0 and 'painPointsAnalysis' in alignment_results:
            pains_coverage = alignment_results['painPointsAnalysis'].get('painsCoverage', [])
            for pain in pains_coverage:
                if (pain.get('matchingProductFeatures') and len(pain.get('matchingProductFeatures', [])) > 0) or \
                   (pain.get('matchingProductBenefits') and len(pain.get('matchingProductBenefits', [])) > 0):
                    covered_pain_points += 1
            
            stats['pain_points_coverage_percent'] = round((covered_pain_points / pain_points_count) * 100)
        
        # Calculate overall coverage
        total_items = objectives_count + pain_points_count
        if total_items > 0:
            covered_items = covered_objectives + covered_pain_points
            stats['overall_coverage_percent'] = round((covered_items / total_items) * 100)
        
        return stats