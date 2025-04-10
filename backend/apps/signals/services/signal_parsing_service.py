# apps/signals/services/signal_parsing_service.py

from django.db import transaction
from ..models import Signal
from django.db.models import Q
from apps.core_apps.models import StandardDepartment
from .signal_creation_service import SignalCreationService

class SignalParsingService:
    """
    Service for parsing AI-generated insights into signals.
    Transforms LLM JSON output into structured signals categorized for sales effectiveness.
    Uses SignalCreationService for consistent validation and optimized performance.
    """
    
    @classmethod
    @transaction.atomic
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
        created_signals = []
        client_id = account.client_id
        
        # Process account info - PROFILE category
        if insights.get('accountInfo'):
            profile_data = cls._extract_profile_data(insights['accountInfo'])
            if profile_data:
                profile_signals = SignalCreationService.create_signals_from_dict(
                    instance=account,
                    data_dict=profile_data,
                    source=source,
                    user=user
                )
                created_signals.extend(profile_signals)
        
        # Process insights data
        if insights.get('insights'):
            insights_data = insights['insights']
            
            # Account-level insights
            if insights_data.get('accountInsights'):
                qualification_data = cls._extract_qualification_data(insights_data['accountInsights'])
                if qualification_data:
                    account_signals = SignalCreationService.create_signals_from_dict(
                        instance=account,
                        data_dict=qualification_data,
                        source=source,
                        user=user
                    )
                    created_signals.extend(account_signals)
            
            # Contact insights
            if insights_data.get('contactsInsights'):
                contact_signals = cls._process_contact_insights(
                    insights_data['contactsInsights'],
                    account,
                    source,
                    user
                )
                created_signals.extend(contact_signals)
        
            # Tech stack data
            if insights_data.get('techStack'):
                tech_stack_signals = cls._process_tech_stack_data(
                    insights_data['techStack'],
                    account,
                    source,
                    user
                )
                created_signals.extend(tech_stack_signals)

            # Buying process data
            if insights_data.get('buyingProcess'):
                buying_process_signals = cls._process_buying_process_data(
                    insights_data['buyingProcess'],
                    account,
                    source,
                    user
                )
                created_signals.extend(buying_process_signals)
                
        return created_signals
    
    @staticmethod
    def _safe_get(data, key):
        """Safely get value and filter out empty values"""
        value = data.get(key)
        if value is None:
            return None
        if isinstance(value, list) and len(value) == 0:
            return None
        return value
    
    @classmethod
    def _extract_profile_data(cls, account_info):
        """Extract profile data into a field_name -> value dictionary"""
        profile_data = {}
        
        # Map fields
        if 'employeeCount' in account_info and account_info['employeeCount'] != 0:
            profile_data[Signal.Field.COMPANY_SIZE] = account_info['employeeCount']
            
        if 'annualRevenue' in account_info and account_info['annualRevenue'] != 0:
            profile_data[Signal.Field.ANNUAL_REVENUE] = account_info['annualRevenue']
            
        return profile_data

    @classmethod
    def _extract_qualification_data(cls, account_insights):
        """Extract qualification data into a field_name -> value dictionary"""
        qualification_data = {}
        
        # Map fields
        field_mapping = {
            'objectives': Signal.Field.OBJECTIVES,
            'motivations': Signal.Field.MOTIVATIONS,
            'metrics': Signal.Field.METRICS,
            'painPoints': Signal.Field.PAIN_POINTS,
            'implications': Signal.Field.IMPLICATIONS
        }
        
        for json_field, signal_field in field_mapping.items():
            value = cls._safe_get(account_insights, json_field)
            if value is not None:
                qualification_data[signal_field] = value
                
        return qualification_data
    
    @classmethod
    def _process_contact_insights(cls, contacts_insights, account, source, user):
        """Process contact insights using efficient lookups for contacts and departments"""
        created_signals = []
        
        # Pre-fetch all contacts for this account
        from apps.accounts.models import Contact
        account_contacts = {}
        for contact in Contact.objects.filter(account=account):
            full_name = f"{contact.first_name.lower()} {contact.last_name.lower()}".strip()
            account_contacts[full_name] = contact
        
        # Pre-fetch departments
        department_cache = {}
        for dept in StandardDepartment.objects.all():
            department_cache[dept.name] = dept
        
        for contact_insight in contacts_insights:
            contact_name = contact_insight.get('contactName')
            if not contact_name:
                continue
                
            # Try to find contact by name
            name_parts = contact_name.split(' ', 1)
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            full_name = f"{first_name.lower()} {last_name.lower()}".strip()
            
            contact = account_contacts.get(full_name)
            department = None
            
            # Get department from contact or try to find it by name
            if contact:
                department = contact.standard_department
            
            if not department:
                department_name = contact_insight.get('department')
                if department_name:
                    for dept_choice in StandardDepartment.DepartmentChoices:
                        if dept_choice.label.lower() in department_name.lower() and dept_choice in department_cache:
                            department = department_cache[dept_choice]
                            break
            
            # Extract qualification data
            qualification_data = cls._extract_qualification_data(contact_insight)
            
            if qualification_data:
                # Create signals with this contact/department as source
                for field_name, value in qualification_data.items():
                    try:
                        signal = SignalCreationService.create_signal_for_field(
                            instance=account,
                            field_name=field_name,
                            value=value,
                            source=source,
                            user=user,
                            contact=contact,
                            department=department
                        )
                        
                        # Add contact metadata
                        if signal:
                            signal.metadata = {
                                'name': contact_name,
                                'job_title': contact_insight.get('jobTitle'),
                                'department': contact_insight.get('department'),
                                'contact_id': str(contact.id) if contact else None,
                                'department_id': str(department.id) if department else None
                            }
                            signal.save(update_fields=['metadata'])
                            created_signals.append(signal)
                    except Exception as e:
                        print(f"Error creating signal for contact {contact_name}, field {field_name}: {str(e)}")
        
        return created_signals
        
    @classmethod
    def _process_tech_stack_data(cls, tech_stack_data, account, source, user):
        """Process tech stack data using SignalCreationService for each tech product"""
        created_signals = []
        
        # Pre-fetch existing tech stacks
        from apps.accounts.models import TechStack
        existing_tech_stacks = {
            tech.tech_name.lower(): tech 
            for tech in TechStack.objects.filter(account=account)
        }
        
        for tech_item in tech_stack_data:
            tech_name = tech_item.get('techName')
            if not tech_name:
                continue
                
            # Get or create tech stack object
            tech_name_lower = tech_name.lower()
            if tech_name_lower in existing_tech_stacks:
                tech_stack = existing_tech_stacks[tech_name_lower]
            else:
                # Create new tech stack
                tech_stack = TechStack.objects.create(
                    account=account,
                    tech_name=tech_name,
                    client_id=account.client_id,
                    created_by=user,
                    updated_by=user
                )
                existing_tech_stacks[tech_name_lower] = tech_stack
            
            # Extract tech stack fields
            tech_data = {}
            
            # Handle primary and alternative field names
            if cls._safe_get(tech_item, 'purpose'):
                tech_data[Signal.Field.PURPOSE] = tech_item['purpose']
                
            if cls._safe_get(tech_item, 'pros'):
                tech_data[Signal.Field.PROS] = tech_item['pros']
                
            # Handle alternative field names for cons
            if cls._safe_get(tech_item, 'improvementPoints'):
                tech_data[Signal.Field.CONS] = tech_item['improvementPoints']
            elif cls._safe_get(tech_item, 'cons'):
                tech_data[Signal.Field.CONS] = tech_item['cons']
                
            # Handle alternative field names for costs
            if cls._safe_get(tech_item, 'annualCosts'):
                tech_data[Signal.Field.ANNUAL_COSTS] = tech_item['annualCosts']
            elif cls._safe_get(tech_item, 'costs'):
                tech_data[Signal.Field.ANNUAL_COSTS] = tech_item['costs']
                
            if cls._safe_get(tech_item, 'renewalDate'):
                tech_data[Signal.Field.RENEWAL_DATE] = tech_item['renewalDate']
                
            # Handle alternative field names for start year
            if cls._safe_get(tech_item, 'startYear'):
                tech_data[Signal.Field.START_YEAR_OF_USAGE] = tech_item['startYear']
            elif cls._safe_get(tech_item, 'yearsOfUsage'):
                tech_data[Signal.Field.START_YEAR_OF_USAGE] = tech_item['yearsOfUsage']
            
            # Create signals for this tech stack
            if tech_data:
                tech_signals = SignalCreationService.create_signals_from_dict(
                    instance=tech_stack,
                    data_dict=tech_data,
                    source=source,
                    user=user
                )
                created_signals.extend(tech_signals)
        
        return created_signals
    
    @classmethod
    def _process_buying_process_data(cls, buying_process_data, account, source, user):
        """Process buying process data into signals"""
        created_signals = []
        
        # Pre-fetch departments
        department_cache = {}
        for dept in StandardDepartment.objects.all():
            department_cache[dept.name] = dept
        
        for idx, step_data in enumerate(buying_process_data):
            # Find department if mentioned
            department = None
            department_name = step_data.get('department')
            
            if department_name:
                for dept_choice in StandardDepartment.DepartmentChoices:
                    if dept_choice.label.lower() in department_name.lower() and dept_choice in department_cache:
                        department = department_cache[dept_choice]
                        break
            
            # Format step data
            formatted_step = {
                'stakeholder': step_data.get('stakeholder', ''),
                'department_name': department_name,
                'step_description': step_data.get('stepDescription', ''),
                'step_goal': step_data.get('stepGoal', ''),
                'influenceScore': step_data.get('influenceScore', 0),
                'criterias': step_data.get('criterias', []),
                'metrics': step_data.get('metrics', []),
                'averageTimeInDays': step_data.get('averageTimeInDays', 0),
                'step_position': idx + 1  # Add position information
            }
            
            # Create signal with step data
            try:
                signal = SignalCreationService.create_signal_for_field(
                    instance=account,
                    field_name='buying_process_step',
                    value=formatted_step,
                    source=source,
                    user=user,
                    department=department
                )
                
                if signal:
                    # Add process metadata
                    signal.metadata = {
                        'needs_position_assignment': True,
                        'needs_process_assignment': True,
                        'step_data': formatted_step,
                        'step_position': idx + 1
                    }
                    signal.save(update_fields=['metadata'])
                    created_signals.append(signal)
            except Exception as e:
                print(f"Error creating buying process step signal: {str(e)}")
        
        return created_signals