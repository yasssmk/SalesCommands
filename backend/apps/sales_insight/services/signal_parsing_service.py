# apps/sales_insight/services/signal_parsing_service.py

from django.utils import timezone
from ..models import Signal
# from apps.accounts_app.org_units.models import AccountOrganizationUnit
# from apps.accounts_app.contacts.models import Contact
# from apps.accounts_app.account_product_detail.models import AccountProductDetail
from apps.accounts.models import Account, Contact, AccountProductRelationship
from apps.products.models import Product

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
        """Parse contact insights"""
        signals = []
        
        for contact_insight in contacts_insights:
            contact_name = contact_insight.get('contactName')
            role = contact_insight.get('role')
            org_unit_name = contact_insight.get('orgUnit')
            
            if not contact_name:
                continue
                
            # Try to find contact by name
            from apps.accounts.models import Contact
            
            # Split name into first and last (simple approach)
            name_parts = contact_name.split(' ', 1)
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            target_contact = None
            try:
                # Find contact by name (case-insensitive)
                target_contact = Contact.objects.filter(
                    account_id=account.id,
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    client_id=client_id
                ).first()
                
                # Create contact if it doesn't exist
                if not target_contact:
                    
                    # Create contact
                    target_contact = Contact.objects.create(
                        account=account,
                        first_name=first_name,
                        last_name=last_name,
                        job_title=role,
                        client_id=client_id,
                        created_by=user,
                        updated_by=user
                    )

            except Exception as e:
                # Log error and continue
                print(f"Error finding/creating contact: {str(e)}")
                continue
                
            if not target_contact:
                continue
                
            # Find org unit for the contact
            target_org_unit = target_contact.org_unit
            
            # Process contact-level insights
            # Objectives (handled specially because of nested structure)
            if 'objectives' in contact_insight and contact_insight['objectives']:
                for objective in contact_insight['objectives']:
                    # Create objective signal
                    signal = Signal.objects.create(
                        account=account,
                        contact=target_contact,
                        org_unit=target_org_unit,
                        category=Signal.Category.GOALS,
                        entity_type=Signal.EntityType.CONTACT,
                        field_name='objectives',
                        value=objective,
                        status=Signal.Status.PENDING,
                        source=source,
                        client_id=client_id,
                        created_by=user,
                        updated_by=user
                    )
                    signals.append(signal)
                    
                    # For high-value signals, find product alignment and APD
                    products = cls._detect_and_set_product_alignment(signal, objective)
                    
                    # Link to APDs
                    cls._link_to_account_product_details(signal, account, products, target_org_unit)
            
            # Process other qualification fields
            qualification_fields = [
                ('motivations', 'motivations'),
                ('keyKPIs', 'key_kpis'),
                ('criteria', 'criteria'),
                ('painPoints', 'pain_points'),
                ('implications', 'implications'),
                ('hasBudgetAuthority', 'budget_authority')
            ]
            
            for json_field, model_field in qualification_fields:
                if json_field in contact_insight and contact_insight[json_field]:
                    # Create qualification signal for contact
                    signal = Signal.objects.create(
                        account=account,
                        contact=target_contact,
                        org_unit=target_org_unit,
                        category=Signal.Category.QUALIFICATION,
                        entity_type=Signal.EntityType.CONTACT,
                        field_name=model_field,
                        value=contact_insight[json_field],
                        status=Signal.Status.PENDING,
                        source=source,
                        client_id=client_id,
                        created_by=user,
                        updated_by=user
                    )
                    signals.append(signal)
                    
                    # For high-value signals, find product alignment and APD
                    if model_field in ['pain_points', 'compelling_events', 'implications']:
                        products = cls._detect_and_set_product_alignment(signal, contact_insight[json_field])
                        
                        # Link to APDs
                        cls._link_to_account_product_details(signal, account, products, target_org_unit)
            
            # Process tech stack (special handling)
            if 'currentTechStack' in contact_insight and contact_insight['currentTechStack']:
                tech_stack_signals = cls._parse_tech_stack(
                    contact_insight['currentTechStack'],
                    account,
                    client_id,
                    source,
                    user,
                    Signal.EntityType.CONTACT,
                    target_org_unit,
                    target_contact
                )
                signals.extend(tech_stack_signals)
            
            # Process projects involved
            if 'projectsInvolved' in contact_insight and contact_insight['projectsInvolved']:
                for project in contact_insight['projectsInvolved']:
                    signal = Signal.objects.create(
                        account=account,
                        contact=target_contact,
                        org_unit=target_org_unit,
                        category=Signal.Category.PROJECT,
                        entity_type=Signal.EntityType.CONTACT,
                        field_name='project_involvement',
                        value=project,
                        status=Signal.Status.PENDING,
                        source=source,
                        client_id=client_id,
                        created_by=user,
                        updated_by=user
                    )
                    signals.append(signal)
                    
                    # For project signals, find product alignment and APD
                    products = cls._detect_and_set_product_alignment(signal, project)
                    
                    # Link to APDs
                    cls._link_to_account_product_details(signal, account, products, target_org_unit)
                
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
    
    
    
