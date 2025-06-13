# apps/campaign/utils/contact_helpers.py
from typing import Optional, Dict, Any
from apps.accounts.models import Contact, Account


class ContactSafetyHelper:
    """
    Helper class for safely accessing contact properties that might not exist
    Prevents crashes when contact.account is None or missing
    """
    
    @staticmethod
    def get_account_name(contact: Contact, fallback: str = "Unknown Account") -> str:
        """
        Safely get account name from contact
        
        Args:
            contact: Contact instance
            fallback: Default value if account is missing
            
        Returns:
            str: Account name or fallback value
        """
        try:
            if contact and contact.account and hasattr(contact.account, 'company_name'):
                return contact.account.company_name or fallback
            return fallback
        except (AttributeError, TypeError):
            return fallback
    
    @staticmethod
    def get_account_id(contact: Contact) -> Optional[int]:
        """
        Safely get account ID from contact
        
        Args:
            contact: Contact instance
            
        Returns:
            Optional[int]: Account ID or None if not available
        """
        try:
            if contact and contact.account:
                return contact.account.id
            return None
        except (AttributeError, TypeError):
            return None
    
    @staticmethod
    def get_account(contact: Contact) -> Optional[Account]:
        """
        Safely get account from contact
        
        Args:
            contact: Contact instance
            
        Returns:
            Optional[Account]: Account instance or None if not available
        """
        try:
            if contact and hasattr(contact, 'account'):
                return contact.account
            return None
        except (AttributeError, TypeError):
            return None
    
    @staticmethod
    def validate_contact_has_account(contact: Contact) -> bool:
        """
        Check if contact has a valid account
        
        Args:
            contact: Contact instance
            
        Returns:
            bool: True if contact has valid account, False otherwise
        """
        try:
            return (contact and 
                    hasattr(contact, 'account') and 
                    contact.account is not None and
                    hasattr(contact.account, 'id'))
        except (AttributeError, TypeError):
            return False
    
    @staticmethod
    def get_contact_display_info(contact: Contact) -> Dict[str, Any]:
        """
        Get safe display information for a contact
        
        Args:
            contact: Contact instance
            
        Returns:
            Dict with safe contact information
        """
        try:
            return {
                'contact_id': contact.id if contact else None,
                'contact_name': f"{contact.first_name} {contact.last_name}".strip() if contact else "Unknown Contact",
                'account_id': ContactSafetyHelper.get_account_id(contact),
                'account_name': ContactSafetyHelper.get_account_name(contact),
                'has_account': ContactSafetyHelper.validate_contact_has_account(contact),
                'email': getattr(contact, 'email', None) if contact else None,
                'phone': getattr(contact, 'phone', None) if contact else None
            }
        except (AttributeError, TypeError):
            return {
                'contact_id': None,
                'contact_name': "Unknown Contact",
                'account_id': None,
                'account_name': "Unknown Account", 
                'has_account': False,
                'email': None,
                'phone': None
            }