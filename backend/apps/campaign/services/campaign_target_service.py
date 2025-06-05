# apps/campaign/services/campaign_target_service.py
from typing import Dict, List, Set, Optional
from django.db.models import Q
from apps.accounts.models import Account, Contact
from apps.leads.models import Lead
from apps.opportunities.models import Opportunity

class CampaignTargetService:
    """
    Service for handling campaign target selection and preparation
    """
    
    @classmethod
    def prepare_campaign_targets(cls, 
                               target_account_ids: List[int] = None,
                               target_contact_ids: List[int] = None,
                               target_lead_ids: List[int] = None,
                               target_opportunity_ids: List[int] = None) -> Dict:
        """
        Prepare campaign targets based on user selection of accounts, contacts, leads, and/or opportunities
        
        Args:
            target_account_ids: List of account IDs to target (all contacts within)
            target_contact_ids: List of specific contact IDs to target
            target_lead_ids: List of specific lead IDs to target
            target_opportunity_ids: List of specific opportunity IDs to target
            
        Returns:
            Dict with:
            - target_accounts: List of account IDs for campaign
            - target_contacts: List of contact IDs for specific targeting
            - target_leads: List of lead IDs for specific targeting
            - target_opportunities: List of opportunity IDs for specific targeting
            - stats: Statistics about the selection
        """
        # Initialize result with empty lists
        result = {
            "target_accounts": [],
            "target_contacts": [],
            "target_leads": [],
            "target_opportunities": [],
            "stats": {
                "total_accounts": 0,
                "total_contacts": 0,
                "total_leads": 0,
                "total_opportunities": 0,
                "estimated_activities": 0,
                "invalid_ids": {
                    "accounts": [],
                    "contacts": [],
                    "leads": [],
                    "opportunities": []
                }
            }
        }
        
        # Handle case where no targets are specified
        if not any([target_account_ids, target_contact_ids, target_lead_ids, target_opportunity_ids]):
            return result
        
        # Normalize inputs to empty lists if None
        target_account_ids = target_account_ids or []
        target_contact_ids = target_contact_ids or []
        target_lead_ids = target_lead_ids or []
        target_opportunity_ids = target_opportunity_ids or []
        
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
            result["stats"]["total_contacts"] = len(valid_contact_ids)
        
        # Process lead IDs
        lead_account_ids = set()
        
        if target_lead_ids:
            # Get valid leads and their account IDs
            leads_data = Lead.objects.filter(
                id__in=target_lead_ids
            ).values('id', 'account_id')
            
            valid_lead_ids = set()
            for lead in leads_data:
                valid_lead_ids.add(lead['id'])
                if lead['account_id']:  # Some leads might not have an account yet
                    lead_account_ids.add(lead['account_id'])
            
            # Identify invalid lead IDs
            invalid_lead_ids = set(target_lead_ids) - valid_lead_ids
            if invalid_lead_ids:
                result["stats"]["invalid_ids"]["leads"] = list(invalid_lead_ids)
            
            # Add valid lead IDs to target
            result["target_leads"] = list(valid_lead_ids)
            result["stats"]["total_leads"] = len(valid_lead_ids)
        
        # Process opportunity IDs
        opportunity_account_ids = set()
        
        if target_opportunity_ids:
            # Get valid opportunities and their account IDs
            opportunities_data = Opportunity.objects.filter(
                id__in=target_opportunity_ids
            ).values('id', 'account_id')
            
            valid_opportunity_ids = set()
            for opportunity in opportunities_data:
                valid_opportunity_ids.add(opportunity['id'])
                opportunity_account_ids.add(opportunity['account_id'])
            
            # Identify invalid opportunity IDs
            invalid_opportunity_ids = set(target_opportunity_ids) - valid_opportunity_ids
            if invalid_opportunity_ids:
                result["stats"]["invalid_ids"]["opportunities"] = list(invalid_opportunity_ids)
            
            # Add valid opportunity IDs to target
            result["target_opportunities"] = list(valid_opportunity_ids)
            result["stats"]["total_opportunities"] = len(valid_opportunity_ids)
        
        # Add account IDs from contacts, leads, and opportunities (if not already included)
        additional_accounts = (contact_account_ids | lead_account_ids | opportunity_account_ids) - set(result["target_accounts"])
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
        
        # Calculate estimated activities
        # Assume average of 4 activities per contact/lead/opportunity
        estimated_activities = (total_contacts + len(result["target_leads"]) + len(result["target_opportunities"])) * 4
        result["stats"]["estimated_activities"] = estimated_activities
        
        return result