# apps/sales_insight/services/tech_stack_relationship_service.py

from django.utils import timezone
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from apps.products.models import Product
from apps.accounts_app.account_product_detail.models import AccountProductDetail
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

class TechStackRelationshipService:
    """
    Service for managing relationships between customer's tech stack
    and products (replace or integrate).
    """
    
    RELATIONSHIP_TYPES = ['REPLACE', 'INTEGRATE']
    
    @classmethod
    def set_tech_stack_relationship(cls, entity, tech_index, product_id, relationship_type, notes=None, user=None):
        """
        Set a relationship between a tech stack item and a product.
        
        Args:
            entity: Account or AccountOrganizationUnit object
            tech_index: Index of the tech stack item in the current_tech_stack list
            product_id: ID of the product to relate to
            relationship_type: 'REPLACE' or 'INTEGRATE'
            notes: Optional notes about the relationship
            user: User performing the action
            
        Returns:
            bool: Success status
            
        Raises:
            StandardizedValidationError: If parameters are invalid
        """
        # Validate inputs
        if relationship_type not in cls.RELATIONSHIP_TYPES:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field=f"Relationship type must be one of: {', '.join(cls.RELATIONSHIP_TYPES)}"
                )
            )
            
        # Verify entity has current_tech_stack
        if not hasattr(entity, 'current_tech_stack') or not entity.current_tech_stack:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="Entity has no tech stack defined"
                )
            )
            
        # Convert to list if it's not already
        if not isinstance(entity.current_tech_stack, list):
            entity.current_tech_stack = [entity.current_tech_stack]
            
        # Check tech_index is valid
        if tech_index < 0 or tech_index >= len(entity.current_tech_stack):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field=f"Tech stack index {tech_index} is out of range"
                )
            )
            
        # Verify product exists
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
        # Get the tech stack item
        tech_item = entity.current_tech_stack[tech_index]
        
        # Create or update relationship info
        relationship_info = {
            "product_id": str(product_id),
            "relationship_type": relationship_type,
            "notes": notes,
            "set_by": str(user.id) if user else None,
            "set_at": timezone.now().isoformat()
        }
        
        # Update the tech stack item
        tech_item['relationship'] = relationship_info
        entity.current_tech_stack[tech_index] = tech_item
        
        # Save the entity
        if hasattr(entity, 'update_qualification_field'):
            entity.update_qualification_field('current_tech_stack', entity.current_tech_stack, user)
        else:
            entity.save()
            
        # Also update any relevant APDs
        cls._update_apd_for_tech_relationship(entity, product_id, tech_item, user)
        
        return True
        
    @classmethod
    def _update_apd_for_tech_relationship(cls, entity, product_id, tech_item, user):
        """
        Update APD with tech stack relationship info.
        """
        # Determine if entity is Account or OrgUnit
        account_id = entity.id if isinstance(entity, Account) else entity.account_id
        
        # Find or create APD
        try:
            apd = AccountProductDetail.objects.get(
                account_id=account_id,
                product_id=product_id
            )
        except AccountProductDetail.DoesNotExist:
            # No APD exists, nothing to update
            return
            
        # Get existing tech relationships or initialize
        if not hasattr(apd, 'tech_relationships') or not apd.tech_relationships:
            apd.tech_relationships = []
            
        # Create tech relationship data for APD
        tech_relationship = {
            "tech_name": tech_item.get('techName', 'Unknown Technology'),
            "relationship_type": tech_item['relationship']['relationship_type'],
            "notes": tech_item['relationship'].get('notes'),
            "source_entity_type": "ACCOUNT" if isinstance(entity, Account) else "ORG_UNIT",
            "source_entity_id": str(entity.id),
            "updated_at": timezone.now().isoformat()
        }
        
        # Check if this tech is already in relationships
        found = False
        for i, rel in enumerate(apd.tech_relationships):
            if rel.get('tech_name') == tech_relationship['tech_name']:
                # Update existing
                apd.tech_relationships[i] = tech_relationship
                found = True
                break
                
        if not found:
            # Add new
            apd.tech_relationships.append(tech_relationship)
            
        # Save APD
        apd.save(user=user)