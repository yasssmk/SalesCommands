# apps/campaign/services/campaign_target_service.py
from typing import Dict, List, Set, Optional
from django.db.models import Q
from apps.accounts.models import Account, Contact

class CampaignTargetService:
    """
    Service for handling campaign target selection and preparation
    """
    
    @classmethod
    def prepare_campaign_targets(cls, 
                               target_account_ids: List[int] = None,
                               target_contact_ids: List[int] = None) -> Dict:
        """
        Prepare campaign targets based on user selection of accounts and/or contacts
        
        Args:
            target_account_ids: List of account IDs to target (all contacts within)
            target_contact_ids: List of specific contact IDs to target
            
        Returns:
            Dict with:
            - target_accounts: List of account IDs for campaign
            - target_contacts: List of contact IDs for specific targeting
            - stats: Statistics about the selection
        """
        # Initialize result with empty lists
        result = {
            "target_accounts": [],
            "target_contacts": [],
            "stats": {
                "total_accounts": 0,
                "total_contacts": 0,
                "estimated_activities": 0,
                "invalid_ids": {
                    "accounts": [],
                    "contacts": []
                }
            }
        }
        
        # Handle case where no targets are specified
        if not target_account_ids and not target_contact_ids:
            return result
        
        # Normalize inputs to empty lists if None
        target_account_ids = target_account_ids or []
        target_contact_ids = target_contact_ids or []
        
        # Process account IDs
        if target_account_ids:
            # Validate account IDs
            valid_account_ids = set(Account.objects.filter(
                id__in=target_account_ids
            ).values_list('id', flat=True))
            
            # Identify invalid account IDs
            invalid_account_ids = set(target_account_ids) - valid_account_ids
            if invalid_account_ids:
                result["stats"]["invalid_ids"]["accounts"] = list(invalid_account_ids)
            
            # Add valid account IDs to target
            result["target_accounts"] = list(valid_account_ids)
            result["stats"]["total_accounts"] = len(valid_account_ids)
        
        # Process contact IDs
        contact_account_ids = set()
        
        if target_contact_ids:
            # Get valid contacts and their account IDs
            contacts_data = Contact.objects.filter(
                id__in=target_contact_ids
            ).values('id', 'account_id')
            
            valid_contact_ids = set()
            for contact in contacts_data:
                valid_contact_ids.add(contact['id'])
                contact_account_ids.add(contact['account_id'])
            
            # Identify invalid contact IDs
            invalid_contact_ids = set(target_contact_ids) - valid_contact_ids
            if invalid_contact_ids:
                result["stats"]["invalid_ids"]["contacts"] = list(invalid_contact_ids)
            
            # Add valid contact IDs to target
            result["target_contacts"] = list(valid_contact_ids)
            
            # Add account IDs from contacts (that aren't already included)
            additional_accounts = contact_account_ids - set(result["target_accounts"])
            result["target_accounts"].extend(additional_accounts)
            
            # Update account stats
            result["stats"]["total_accounts"] = len(set(result["target_accounts"]))
        
        # Calculate total contacts (for accounts, we get all contacts; for specific contacts, we use those)
        total_contacts = 0
        
        # Count contacts from accounts
        if result["target_accounts"]:
            # Exclude contacts that are specifically targeted to avoid double counting
            account_contacts_query = Contact.objects.filter(
                account_id__in=result["target_accounts"]
            )
            
            if result["target_contacts"]:
                account_contacts_query = account_contacts_query.exclude(
                    id__in=result["target_contacts"]
                )
            
            account_contacts_count = account_contacts_query.count()
            total_contacts += account_contacts_count
        
        # Add specifically targeted contacts
        total_contacts += len(result["target_contacts"])
        result["stats"]["total_contacts"] = total_contacts
        
        # Calculate estimated activities (assume average of 4 activities per contact)
        result["stats"]["estimated_activities"] = total_contacts * 4
        
        return result