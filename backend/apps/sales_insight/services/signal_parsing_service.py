# apps/sales_insight/services/signal_parsing_service.py

from django.utils import timezone
from ..models import Signal
# from apps.accounts_app.org_units.models import AccountOrganizationUnit
# from apps.accounts_app.contacts.models import Contact
# from apps.accounts_app.account_product_detail.models import AccountProductDetail
from apps.accounts.models import Account, Contact, AccountProductRelationship
from apps.products.models import Product
from django.db.models import  Q

class SignalParsingService:
    """
    Service for parsing AI-generated insights into signals.
    Transforms LLM JSON output into structured signals categorized for sales effectiveness.
    """
    
    @classmethod
    def parse_insights(cls, insights, account, source='ai_analysis', user=None):
        """
        Parse structured insights from LLM into Signal objects.
        
        Args:
            insights (dict): Structured insights from LLM
            account (Account): Account object
            source (str, optional): Source of insights
            user (User, optional): User who initiated the analysis
            
        Returns:
            list: Created Signal objects
        """
        signals = []
        client_id = account.client_id
        
        # Process account info - PROFILE category
        if 'accountInfo' in insights:
            profile_signals = cls._parse_profile_data(
                insights['accountInfo'], 
                account, 
                client_id, 
                source, 
                user
            )
            signals.extend(profile_signals)
        
        # Process insights data
        if 'insights' in insights:
            insights_data = insights['insights']
            
            # Account-level insights
            if 'accountInsights' in insights_data:
                account_signals = cls._parse_account_insights(
                    insights_data['accountInsights'], 
                    account, 
                    client_id, 
                    source, 
                    user
                )
                signals.extend(account_signals)
            
                
            # Contact insights
            if 'contactsInsights' in insights_data:
                contact_signals = cls._parse_contact_insights(
                    insights_data['contactsInsights'], 
                    account, 
                    client_id, 
                    source, 
                    user
                )
                signals.extend(contact_signals)
                
        return signals
    
    @classmethod
    def _parse_profile_data(cls, account_info, account, client_id, source, user):
        """Parse profile data from accountInfo section"""
        signals = []
        
        # Basic profile fields mapping (JSON field → model field)
        profile_fields = {
            'employeeCount': 'company_size',
            'annualRevenue': 'annual_revenue',
            'buyingDecisions': 'has_buying_decision'
        }
        
        for json_field, model_field in profile_fields.items():
            if json_field in account_info and account_info[json_field]:
                # Profile data usually has low-medium urgency but is foundational
                signal = Signal.objects.create(
                    account=account,
                    category=Signal.Category.PROFILE,
                    entity_type=Signal.EntityType.ACCOUNT,
                    field_name=model_field,
                    value=account_info[json_field],
                    status=Signal.Status.PENDING,
                    source=source,
                    client_id=client_id,
                    created_by=user,
                    updated_by=user
                )
                signals.append(signal)
                      
        return signals

    @classmethod
    def _parse_account_insights(cls, account_insights, account, client_id, source, user):
        """Parse account-level insights"""
        signals = []
        
        # Process qualification fields
        qualification_fields = [
            ('objectives', 'objectives'),
            ('motivations', 'motivations'),
            ('metrics', 'metrics'),
            ('painPoints', 'pain_points'),
            ('implications', 'implications'),
            ('partners', 'partners')
        ]
        
        for json_field, model_field in qualification_fields:
            if json_field in account_insights and account_insights[json_field]:
                # Create qualification signal
                signal = Signal.objects.create(
                    account=account,
                    category=Signal.Category.QUALIFICATION,
                    entity_type=Signal.EntityType.ACCOUNT,
                    field_name=model_field,
                    value=account_insights[json_field],
                    status=Signal.Status.PENDING,
                    source=source,
                    client_id=client_id,
                    created_by=user,
                    updated_by=user
                )
                signals.append(signal)
    
    @classmethod
    def _parse_contact_insights(cls, contacts_insights, account, client_id, source, user):
        """
        Parse contact insights without automatically creating contacts.
        Creates signals with contact information that users can assign later.
        """
        signals = []
        
        for contact_insight in contacts_insights:
            contact_name = contact_insight.get('contactName')
            job_title = contact_insight.get('jobTitle')
            department = contact_insight.get('department')
            has_budget_authority = contact_insight.get('hasBudgetAuthority', False)
            
            if not contact_name:
                continue
            
            # Store contact details in the signal metadata for later assignment
            contact_details = {
                'name': contact_name,
                'job_title': job_title,
                'department': department,
                'has_budget_authority': has_budget_authority
            }
            
            # Try to find potential matches to suggest
            potential_matches = []
            name_parts = contact_name.split(' ', 1)
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            try:
                # Find contacts by name (case-insensitive)
                from apps.accounts.models import Contact
                
                matching_contacts = Contact.objects.filter(
                    account_id=account.id,
                    client_id=client_id
                ).filter(
                    Q(first_name__iexact=first_name, last_name__iexact=last_name) |
                    Q(email__icontains=first_name.lower())
                )[:5]  # Limit to 5 suggestions
                
                # Add potential matches (just IDs and names for now)
                for contact in matching_contacts:
                    potential_matches.append({
                        'id': str(contact.id),
                        'name': f"{contact.first_name} {contact.last_name}",
                        'job_title': contact.job_title,
                        'email': contact.email
                    })
                    
            except Exception as e:
                # Log error but continue
                print(f"Error finding potential contact matches: {str(e)}")
            
            # Process qualification fields
            qualification_fields = [
                ('objectives', 'objectives'),
                ('motivations', 'motivations'),
                ('metrics', 'metrics'),
                ('painPoints', 'pain_points'),
                ('implications', 'implications')
            ]
            
            # Create signals for each qualification field
            for json_field, model_field in qualification_fields:
                if json_field in contact_insight and contact_insight[json_field]:
                    # Initialize metadata
                    metadata = {
                        'contact_details': contact_details,
                        'potential_matches': potential_matches,
                        'needs_assignment': True
                    }
                    
                    # Create the signal without assigning to a contact yet
                    signal = Signal.objects.create(
                        account=account,
                        # No contact assigned yet
                        category=Signal.Category.QUALIFICATION,
                        entity_type=Signal.EntityType.CONTACT,
                        field_name=model_field,
                        value=contact_insight[json_field],
                        status=Signal.Status.PENDING,
                        source=source,
                        client_id=client_id,
                        created_by=user,
                        updated_by=user,
                        metadata=metadata
                    )
                    signals.append(signal)
            
            # Add signals for profile fields (department, has_budget_authority)
            profile_fields = [
                ('department', 'department'),
                ('hasBudgetAuthority', 'has_buying_authority')
            ]
            
            for json_field, model_field in profile_fields:
                if json_field in contact_insight and contact_insight[json_field]:
                    # Create profile signal with same metadata
                    metadata = {
                        'contact_details': contact_details,
                        'potential_matches': potential_matches,
                        'needs_assignment': True
                    }
                    
                    signal = Signal.objects.create(
                        account=account,
                        # No contact assigned yet
                        category=Signal.Category.PROFILE,
                        entity_type=Signal.EntityType.CONTACT,
                        field_name=model_field,
                        value=contact_insight[json_field],
                        status=Signal.Status.PENDING,
                        source=source,
                        client_id=client_id,
                        created_by=user,
                        updated_by=user,
                        metadata=metadata
                    )
                    signals.append(signal)
            
        return signals
        
    @classmethod
    def _parse_tech_stack(cls, tech_stack, account, client_id, source, user, entity_type, org_unit=None, contact=None):
        """Parse tech stack into signals with competitor analysis"""
        signals = []
        
        for tech_item in tech_stack:
            # Tech stack is very valuable for competitor analysis and product alignment
            signal = Signal.objects.create(
                account=account,
                contact=contact,
                category=Signal.Category.QUALIFICATION,
                entity_type=entity_type,
                field_name='current_tech_stack',
                value=tech_item,
                status=Signal.Status.PENDING,
                source=source,
                client_id=client_id,
                created_by=user,
                updated_by=user
            )
            signals.append(signal)
            
            # Find competitor products and set product alignment
            tech_name = tech_item.get('techName', '')
            products = cls._detect_and_set_product_alignment(signal, tech_name, is_competitor=True)
            
            # Link to APDs based on competitor analysis
            cls._link_to_account_product_details(signal, account, products, org_unit, is_competitor=True)
            
        return signals
    
    @classmethod
    def _parse_projects(cls, projects, account, client_id, source, user, entity_type, org_unit=None, contact=None):
        """Parse projects into signals - highest value insights"""
        signals = []
        
        for project in projects:
            # Projects represent concrete opportunities for selling
            signal = Signal.objects.create(
                account=account,
                contact=contact,
                category=Signal.Category.PROJECT,
                entity_type=entity_type,
                field_name='projects',
                value=project,
                status=Signal.Status.PENDING,
                source=source,
                client_id=client_id,
                created_by=user,
                updated_by=user
            )
            signals.append(signal)
            
            # Set product alignment based on project description
            project_name = project.get('projectName', '')
            products = cls._detect_and_set_product_alignment(signal, project)
            
            # Create or find APDs for project and link them
            cls._link_to_account_product_details(signal, account, products, 
                                                estimated_units=project.get('estimatedUnitsNeeded'),
                                                budget=project.get('budgetAllocation'))
            
        return signals
    
    
    
