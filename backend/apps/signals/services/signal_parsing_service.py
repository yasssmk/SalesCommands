# apps/signals/services/signal_parsing_service.py

from django.db import transaction
from ..models import Signal
from django.utils import timezone
from apps.core_apps.models import StandardDepartment

class SignalParsingService:
    """
    Service for parsing AI-generated insights into signals.
    Transforms LLM JSON output into structured signals for sales intelligence.
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
        
        # Process account info (profile category)
        if 'accountInfo' in insights:
            profile_signals = cls._process_profile_data(
                insights['accountInfo'], 
                account, 
                source, 
                user
            )
            created_signals.extend(profile_signals)
        
        # Process qualification insights
        if 'insights' in insights and 'accountInsights' in insights['insights']:
            qualification_signals = cls._process_qualification_data(
                insights['insights']['accountInsights'], 
                account, 
                source, 
                user
            )
            created_signals.extend(qualification_signals)
          
        # Process tech stack data
        if 'insights' in insights and 'techStack' in insights['insights']:
            tech_stack_signals = cls._process_tech_stack_data(
                insights['insights']['techStack'],
                account,
                source,
                user
            )
            created_signals.extend(tech_stack_signals)
        
        return created_signals
    
    @classmethod
    def _create_signal(cls, instance, field_name, value, category=None, source=None, user=None, **kwargs):
        """
        Create a single signal with proper validation and defaults.
        """
        # Determine category from field_name if not provided
        if category is None and field_name in Signal.FIELD_CATEGORIES:
            category = Signal.FIELD_CATEGORIES[field_name]
        
        # Skip if we can't determine category
        if not category:
            return None
            
        # Skip empty values
        if value is None or (isinstance(value, (list, dict)) and not value):
            return None
        
        # Create signal with proper defaults
        try:
            # Determine entity type
            from apps.accounts.models import Account, TechStack
            if isinstance(instance, Account):
                entity_type = Signal.EntityType.ACCOUNT
            elif isinstance(instance, TechStack):
                entity_type = Signal.EntityType.TECH_STACK
            else:
                return None
                
            signal = Signal(
                account=kwargs.get('account', instance if entity_type == Signal.EntityType.ACCOUNT else instance.account),
                category=category,
                entity_type=entity_type,
                field_name=field_name,
                value=value,
                source=source or 'ai_analysis',
                status=Signal.Status.PENDING,
                source_contact=kwargs.get('contact'),
                source_department=kwargs.get('department'),
                tech_stack=instance if entity_type == Signal.EntityType.TECH_STACK else None,
                client_id=instance.client_id,
                created_by=user,
                updated_by=user,
                confirmation_count=1,
                last_confirmed_at=timezone.now()
            )
            
            # Add additional metadata if provided
            if kwargs.get('metadata'):
                signal.metadata = kwargs.get('metadata')
                
            signal.save()
            return signal
            
        except Exception as e:
            print(f"Error creating signal for {field_name}: {str(e)}")
            return None
    
    @classmethod
    def _process_profile_data(cls, account_info, account, source, user):
        """Process profile data into signals"""
        created_signals = []
        
        # Map fields directly
        field_mapping = {
            'employeeCount': Signal.Field.COMPANY_SIZE,
            'annualRevenue': Signal.Field.ANNUAL_REVENUE,
        }
        
        for json_field, signal_field in field_mapping.items():
            if json_field in account_info and account_info[json_field]:
                signal = cls._create_signal(
                    instance=account,
                    field_name=signal_field,
                    value=account_info[json_field],
                    category=Signal.Category.PROFILE,
                    source=source,
                    user=user
                )
                if signal:
                    created_signals.append(signal)
        
        return created_signals

    @classmethod
    def _process_qualification_data(cls, account_insights, account, source, user):
        """Process qualification data into signals"""
        created_signals = []
        
        # Field mapping from JSON to signal fields
        field_mapping = {
            'objectives': Signal.Field.OBJECTIVES,
            'motivations': Signal.Field.MOTIVATIONS,
            'metrics': Signal.Field.METRICS,
            'painPoints': Signal.Field.PAIN_POINTS,
            'implications': Signal.Field.IMPLICATIONS
        }
        
        for json_field, signal_field in field_mapping.items():
            if json_field in account_insights and account_insights[json_field]:
                # For array fields, create separate signals for each item
                values = account_insights[json_field]
                if isinstance(values, list):
                    for value in values:
                        if value:  # Skip empty values
                            signal = cls._create_signal(
                                instance=account,
                                field_name=signal_field,
                                value=value,
                                category=Signal.Category.QUALIFICATION,
                                source=source,
                                user=user
                            )
                            if signal:
                                created_signals.append(signal)
                else:
                    # Handle single values
                    signal = cls._create_signal(
                        instance=account,
                        field_name=signal_field,
                        value=values,
                        category=Signal.Category.QUALIFICATION,
                        source=source,
                        user=user
                    )
                    if signal:
                        created_signals.append(signal)
        
        return created_signals
    
    @classmethod
    def _process_tech_stack_data(cls, tech_stack_data, account, source, user):
        """Process tech stack data into signals"""
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
            
            # Field mapping with alternative field names
            field_mapping = {
                'purpose': Signal.Field.PURPOSE,
                'pros': Signal.Field.PROS,
                'cons': Signal.Field.CONS,
                'improvementPoints': Signal.Field.CONS,  # Alternative name
                'annualCosts': Signal.Field.ANNUAL_COSTS,
                'costs': Signal.Field.ANNUAL_COSTS,  # Alternative name
                'renewalDate': Signal.Field.RENEWAL_DATE,
                'startYear': Signal.Field.START_YEAR_OF_USAGE,
                'yearsOfUsage': Signal.Field.START_YEAR_OF_USAGE  # Alternative name
            }
            
            # Process each tech stack field
            for json_field, signal_field in field_mapping.items():
                if json_field in tech_item and tech_item[json_field]:
                    values = tech_item[json_field]
                    
                    # Create separate signals for list items
                    if isinstance(values, list):
                        for value in values:
                            if value:  # Skip empty values
                                signal = cls._create_signal(
                                    instance=tech_stack,
                                    field_name=signal_field,
                                    value=value,
                                    category=Signal.Category.TECH_STACK,
                                    source=source,
                                    user=user,
                                    account=account
                                )
                                if signal:
                                    created_signals.append(signal)
                    else:
                        # Handle single values
                        signal = cls._create_signal(
                            instance=tech_stack,
                            field_name=signal_field,
                            value=values,
                            category=Signal.Category.TECH_STACK,
                            source=source,
                            user=user,
                            account=account
                        )
                        if signal:
                            created_signals.append(signal)
        
        return created_signals