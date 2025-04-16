# apps/signals/services/signal_parsing_service.py

from django.db import transaction
from django.utils import timezone
from ..models.qualification_signal_model import QualificationSignal
from ..models.tech_stack_signal_model import TechStackSignal
from ..models.profile_signal_model import ProfileSignal
from .signal_manager import SignalManager


class SignalParsingService:
    """
    Service for parsing AI-generated insights into typed signals.
    Transforms LLM JSON output into structured signals for sales intelligence.
    """
    
    @classmethod
    @transaction.atomic
    def parse_insights(cls, insights, account, source='ai_analysis', user=None, client_id=None):
        """
        Parse structured insights from LLM into appropriate Signal objects.
        
        Args:
            insights (dict): Structured insights from LLM
            account (Account): Account object
            source (str, optional): Source of insights
            user (User, optional): User who initiated the analysis
            client_id (str, optional): Client ID
            
        Returns:
            dict: Dictionary of created signals by type
        """
        created_signals = {
            'qualification': [],
            'profile': [],
            'tech_stack': []
        }
        
        # Use client_id from account if not provided
        if client_id is None:
            client_id = account.client_id
        
        # Process each type of insight
        # 1. Process account info (profile signals)
        if 'accountInfo' in insights:
            profile_signals = cls._process_profile_data(
                insights['accountInfo'],
                account,
                source,
                user,
                client_id
            )
            created_signals['profile'].extend(profile_signals)
        
        # 2. Process qualification insights
        if 'insights' in insights and 'accountInsights' in insights['insights']:
            qualification_signals = cls._process_qualification_data(
                insights['insights']['accountInsights'],
                account,
                source,
                user,
                client_id
            )
            created_signals['qualification'].extend(qualification_signals)
        
        # 3. Process tech stack data
        if 'insights' in insights and 'techStack' in insights['insights']:
            tech_stack_signals_by_tech = cls._process_tech_stack_data(
                insights['insights']['techStack'],
                account,
                source,
                user,
                client_id
            )
            
            # Flatten the dictionary of tech stack signals into a list for compatibility with view
            tech_stack_signals = []
            for tech_name, signals in tech_stack_signals_by_tech.items():
                tech_stack_signals.extend(signals)
                
            created_signals['tech_stack'] = tech_stack_signals
        
        return created_signals
    
    @classmethod
    def _process_profile_data(cls, account_info, account, source, user, client_id):
        """
        Process profile data into ProfileSignal objects.
        
        Args:
            account_info (dict): Profile information from LLM
            account (Account): Account object
            source (str): Source of insights
            user (User): User who initiated the analysis
            client_id: Client ID
            
        Returns:
            list: Created ProfileSignal objects
        """
        created_signals = []
        
        # Map LLM fields to our model fields
        field_mapping = {
            'employeeCount': ProfileSignal.Field.COMPANY_SIZE,
            'annualRevenue': ProfileSignal.Field.ANNUAL_REVENUE,
        }
        
        for json_field, signal_field in field_mapping.items():
            if json_field in account_info and account_info[json_field]:
                # Create profile signal
                try:
                    signal_data = {
                        'account': account,
                        'field_name': signal_field,
                        'value': account_info[json_field],
                        'source': source,
                        'status': 'PENDING',
                        'category': 'PROFILE',  # For SignalManager
                    }
                    
                    signal = SignalManager.create_signal(
                        data=signal_data,
                        user=user,
                        client_id=client_id
                    )
                    
                    if signal:
                        created_signals.append(signal)
                        
                except Exception as e:
                    print(f"Error creating profile signal for {json_field}: {str(e)}")
        
        return created_signals
    
    @classmethod
    def _process_qualification_data(cls, account_insights, account, source, user, client_id):
        """
        Process qualification data into QualificationSignal objects.
        
        Args:
            account_insights (dict): Qualification information from LLM
            account (Account): Account object
            source (str): Source of insights
            user (User): User who initiated the analysis
            client_id: Client ID
            
        Returns:
            list: Created QualificationSignal objects
        """
        created_signals = []
        
        # Map LLM fields to our model fields
        field_mapping = {
            'objectives': QualificationSignal.Field.OBJECTIVES,
            'motivations': QualificationSignal.Field.MOTIVATIONS,
            'metrics': QualificationSignal.Field.METRICS,
            'painPoints': QualificationSignal.Field.PAIN_POINTS,
            'implications': QualificationSignal.Field.IMPLICATIONS
        }
        
        for json_field, signal_field in field_mapping.items():
            if json_field in account_insights and account_insights[json_field]:
                values = account_insights[json_field]
                
                # Handle both list and single value formats
                if not isinstance(values, list):
                    values = [values]
                
                for value in values:
                    if value:  # Skip empty values
                        try:
                            signal_data = {
                                'account': account,
                                'field_name': signal_field,
                                'value': str(value),
                                'source': source,
                                'status': 'PENDING',
                                'category': 'QUALIFICATION',  # For SignalManager
                            }
                            
                            signal = SignalManager.create_signal(
                                data=signal_data,
                                user=user,
                                client_id=client_id
                            )
                            
                            if signal:
                                created_signals.append(signal)
                                
                        except Exception as e:
                            print(f"Error creating qualification signal for {json_field}: {str(e)}")
        
        return created_signals
    
    @classmethod
    def _process_tech_stack_data(cls, tech_stack_data, account, source, user, client_id):
        """
        Process tech stack data into TechStackSignal objects.
        
        Args:
            tech_stack_data (list): Tech stack information from LLM
            account (Account): Account object
            source (str): Source of insights
            user (User): User who initiated the analysis
            client_id: Client ID
            
        Returns:
            dict: Created TechStackSignal objects grouped by tech name
        """
        created_signals_by_tech = {}  # Changed to dictionary to group by tech name
        
        # Pre-fetch existing tech stacks to avoid duplicates
        from apps.accounts.models import TechStack
        existing_tech_stacks = {
            tech.tech_name.lower(): tech 
            for tech in TechStack.objects.filter(account=account)
        }
        
        # Process each tech stack item
        for tech_item in tech_stack_data:
            tech_name = tech_item.get('techName')
            if not tech_name:
                continue
            
            # Initialize empty list for this tech if not already in dictionary
            if tech_name not in created_signals_by_tech:
                created_signals_by_tech[tech_name] = []
            
            # Check if tech stack exists in our database
            tech_name_lower = tech_name.lower()
            tech_stack = existing_tech_stacks.get(tech_name_lower)
            
            # Field mapping with alternative field names
            field_mapping = {
                'purpose': TechStackSignal.Field.PURPOSE,
                'pros': TechStackSignal.Field.PROS,
                'cons': TechStackSignal.Field.CONS,
                'improvementPoints': TechStackSignal.Field.CONS,  # Alternative name
                'costs': TechStackSignal.Field.COSTS,
                'annualCosts': TechStackSignal.Field.COSTS,  # Alternative name
                'renewalDate': TechStackSignal.Field.RENEWAL_DATE,
                'startYear': TechStackSignal.Field.START_YEAR_OF_USAGE,
                'yearsOfUsage': TechStackSignal.Field.START_YEAR_OF_USAGE  # Alternative name
            }
            
            # Process each tech stack field
            for json_field, signal_field in field_mapping.items():
                if json_field in tech_item and tech_item[json_field]:
                    values = tech_item[json_field]
                    
                    if not isinstance(values, list):
                        values = [values]
                    
                    for value in values:
                        if value:  # Skip empty values
                            try:
                                # Prepare signal data
                                signal_data = {
                                    'account': account,
                                    'field_name': signal_field,
                                    'value': value,
                                    'source': source,
                                    'status': 'PENDING',
                                    'category': 'TECH_STACK',
                                }
                                
                                # If tech_stack exists, add it directly
                                if tech_stack:
                                    signal_data['tech_stack'] = tech_stack
                                else:
                                    # Otherwise, add tech_name to be stored in metadata
                                    signal_data['tech_name'] = tech_name
                                # Create the signal
                                signal = SignalManager.create_signal(
                                    data=signal_data,
                                    user=user,
                                    client_id=client_id
                                )
                                
                                if signal:
                                    # Add to the appropriate tech name key in the dictionary
                                    created_signals_by_tech[tech_name].append(signal)
                                
                            except Exception as e:
                                print(f"Error creating tech stack signal for {json_field}: {str(e)}")
        
        return created_signals_by_tech