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
from ..services.apd_prompts_service import call_second_llm_for_objectives
from ..serializers.apd_analyze_serializer import APDAnalysisSerializer, ObjectiveAlignmentResponseSerializer
import json

class AccountProductAlignmentView(BaseAPIView):
    """
    API View for analyzing account or org unit signals against product information
    to generate alignment insights for the Account Product Detail.
    """
    
    def post(self, request, *args, **kwargs):
        """
        Custom post method that analyzes objectives from either an account or
        organization unit against product benefits.
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
            
            # Get objectives - either from org unit if specified, or from account
            if org_unit:
                objectives = org_unit.objectives or []
                entity_name = f"{org_unit.organization_name} (Org Unit)"
                entity_id = str(org_unit.id)
                entity_type = "org_unit"
            else:
                objectives = account.objectives or []
                entity_name = account.company_name
                entity_id = str(account.id)
                entity_type = "account"
                
            if not objectives:
                return Response({
                    'success': False,
                    'message': f'No objectives found for {entity_type} {entity_name}',
                    'account_id': str(account.id),
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'product_id': str(product.id),
                    'results': None
                }, status=status.HTTP_200_OK)
                
            # Get product benefits
            product_benefits = product.key_benefits or []
            if not product_benefits:
                return Response({
                    'success': False,
                    'message': 'No key benefits defined for this product',
                    'account_id': str(account.id),
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'product_id': str(product.id),
                    'results': None
                }, status=status.HTTP_200_OK)
            
            # Call LLM service to align objectives with benefits
            llm_service = LLMProviderService()
            alignment_json = call_second_llm_for_objectives(
                objectives, 
                product_benefits,
                llm_service
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
            
            response_data = {
                'success': True,
                'account_id': str(account.id),
                'entity_type': entity_type,
                'entity_id': entity_id,
                'product_id': str(product.id),
                'entity_name': entity_name,
                'product_name': product.product_name,
                'results': alignment_results
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            return self.handle_exception(e)