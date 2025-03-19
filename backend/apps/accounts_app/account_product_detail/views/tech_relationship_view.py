from rest_framework import status
from rest_framework.response import Response
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from ..models import AccountProductDetail
from ..services.tech_stack_relationship_service import TechStackRelationshipService

class TechRelationshipView(BaseAPIView):
    """
    API View for managing technology stack relationships with products.
    """
    
    def post(self, request, *args, **kwargs):
        """
        Create a relationship between a tech stack item and a product.
        
        POST /api/account-products/tech-relationships/
        
        Required fields:
            - apd_id: ID of the AccountProductDetail 
            - entity_type: Type of entity (ACCOUNT or ORG_UNIT)
            - entity_id: ID of the entity
            - tech_index: Index of the tech stack item
            - relationship_type: REPLACE or INTEGRATE
            
        Optional fields:
            - notes: Additional notes about the relationship
        """
        try:
            # Validate required fields
            required_fields = ['apd_id', 'entity_type', 'entity_id', 'tech_index', 'relationship_type']
            for field in required_fields:
                if field not in request.data:
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field=field)
                    )
            
            # Get input parameters
            apd_id = request.data['apd_id']
            entity_type = request.data['entity_type'].upper()
            entity_id = request.data['entity_id']
            tech_index = int(request.data['tech_index'])
            relationship_type = request.data['relationship_type'].upper()
            notes = request.data.get('notes')
            
            # Validate entity type
            if entity_type not in ['ACCOUNT', 'ORG_UNIT']:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="entity_type must be ACCOUNT or ORG_UNIT"
                    )
                )
            
            # Get APD
            try:
                apd = AccountProductDetail.objects.get(id=apd_id)
                self.validate_client_id(apd)
            except AccountProductDetail.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Get entity
            try:
                if entity_type == 'ACCOUNT':
                    entity = Account.objects.get(id=entity_id)
                else:  # ORG_UNIT
                    entity = AccountOrganizationUnit.objects.get(id=entity_id)
                    
                self.validate_client_id(entity)
            except (Account.DoesNotExist, AccountOrganizationUnit.DoesNotExist):
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Verify entity belongs to the APD's account
            if entity_type == 'ACCOUNT' and str(entity.id) != str(apd.account_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Entity must belong to the APD's account"
                    )
                )
            elif entity_type == 'ORG_UNIT' and str(entity.account_id) != str(apd.account_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Entity must belong to the APD's account"
                    )
                )
            
            # Call service to set the relationship
            TechStackRelationshipService.set_tech_stack_relationship(
                entity=entity,
                tech_index=tech_index,
                product_id=apd.product_id,
                relationship_type=relationship_type,
                notes=notes,
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': f'Technology relationship set to {relationship_type}'
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return self.handle_exception(e)
    
    def get(self, request, *args, **kwargs):
        """
        Get available tech stack items for an entity.
        
        GET /api/account-products/tech-relationships/?entity_type=ACCOUNT&entity_id=123
        """
        try:
            # Validate required parameters
            entity_type = request.query_params.get('entity_type', '').upper()
            entity_id = request.query_params.get('entity_id')
            
            if not entity_type or entity_type not in ['ACCOUNT', 'ORG_UNIT']:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field="entity_type (ACCOUNT or ORG_UNIT)"
                    )
                )
                
            if not entity_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="entity_id")
                )
            
            # Get entity
            try:
                if entity_type == 'ACCOUNT':
                    entity = Account.objects.get(id=entity_id)
                else:  # ORG_UNIT
                    entity = AccountOrganizationUnit.objects.get(id=entity_id)
                    
                self.validate_client_id(entity)
            except (Account.DoesNotExist, AccountOrganizationUnit.DoesNotExist):
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Check if entity has tech stack
            if not hasattr(entity, 'current_tech_stack') or not entity.current_tech_stack:
                return Response({
                    'tech_stack': [],
                    'message': 'No technology stack found for this entity'
                })
            
            # Format tech stack for response
            tech_stack = []
            for i, tech in enumerate(entity.current_tech_stack):
                tech_item = {
                    'index': i,
                    'tech_name': tech.get('techName', 'Unknown Technology'),
                    'business_goal': tech.get('businessGoal', ''),
                    'has_relationship': 'relationship' in tech,
                }
                
                if 'relationship' in tech:
                    tech_item['relationship'] = {
                        'product_id': tech['relationship'].get('product_id'),
                        'relationship_type': tech['relationship'].get('relationship_type'),
                        'notes': tech['relationship'].get('notes'),
                        'set_at': tech['relationship'].get('set_at')
                    }
                    
                tech_stack.append(tech_item)
            
            return Response({
                'entity_type': entity_type,
                'entity_id': str(entity_id),
                'entity_name': entity.company_name if entity_type == 'ACCOUNT' else entity.organization_name,
                'tech_stack': tech_stack
            })
                
        except Exception as e:
            return self.handle_exception(e)