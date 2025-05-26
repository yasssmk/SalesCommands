# apps/account/services/contact_service.py
from django.db import transaction
from apps.accounts.models import Contact

class ContactService:
    """
    Service for handling contact-related operations
    """
    
    @classmethod
    @transaction.atomic
    def toggle_email_validity(cls, contact: Contact, user=None) -> dict:
        """
        Toggle the email_is_valid field for a contact
        
        Args:
            contact: The contact to update
            user: Optional user for tracking changes
            
        Returns:
            Dictionary with the result information
        """
        # Store original value for tracking
        original_value = contact.email_is_valid
        
        # Toggle the value
        contact.email_is_valid = not original_value
        contact.save(update_fields=['email_is_valid'])
        
        # Track the field change if tracking is implemented
        if hasattr(contact, 'track_field_change') and user:
            contact.track_field_change('email_is_valid', original_value, contact.email_is_valid, user)
        
        return {
            'success': True,
            'email_is_valid': contact.email_is_valid,
            'message': 'Email marked as valid' if contact.email_is_valid else 'Email marked as invalid'
        }
    
    @classmethod
    @transaction.atomic
    def toggle_phone_validity(cls, contact: Contact, user=None) -> dict:
        """
        Toggle the phone_is_valid field for a contact
        
        Args:
            contact: The contact to update
            user: Optional user for tracking changes
            
        Returns:
            Dictionary with the result information
        """
        # Store original value for tracking
        original_value = contact.phone_is_valid
        
        # Toggle the value
        contact.phone_is_valid = not original_value
        contact.save(update_fields=['phone_is_valid'])
        
        # Track the field change if tracking is implemented
        if hasattr(contact, 'track_field_change') and user:
            contact.track_field_change('phone_is_valid', original_value, contact.phone_is_valid, user)
        
        return {
            'success': True,
            'phone_is_valid': contact.phone_is_valid,
            'message': 'Phone marked as valid' if contact.phone_is_valid else 'Phone marked as invalid'
        }