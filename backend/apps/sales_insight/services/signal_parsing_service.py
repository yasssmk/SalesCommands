# # apps/sales_insight/services/signal_parsing_service.py

# from ..models import Signal
# from django.db.models import Q

# class SignalParsingService:
#     """
#     Service for parsing AI-generated insights into signals.
#     Transforms LLM JSON output into structured signals categorized for sales effectiveness.
#     """
    
#     @classmethod
#     def parse_insights(cls, insights, account, source='ai_analysis', user=None):
#         """
#         Parse structured insights from LLM into Signal objects.
        
#         Args:
#             insights (dict): Structured insights from LLM
#             account (Account): Account object
#             source (str, optional): Source of insights
#             user (User, optional): User who initiated the analysis
            
#         Returns:
#             list: Created Signal objects
#         """
#         signals = []
#         client_id = account.client_id
        
#         # Process account info - PROFILE category
#         if insights.get('accountInfo'):
#             profile_signals = cls._parse_profile_data(
#                 insights['accountInfo'], 
#                 account, 
#                 client_id, 
#                 source, 
#                 user
#             )
#             if profile_signals:
#                 signals.extend(profile_signals)
        
#         # Process insights data
#         if insights.get('insights'):
#             insights_data = insights['insights']
            
#             # Account-level insights
#             if insights_data.get('accountInsights') and insights_data['accountInsights']:
#                 account_signals = cls._parse_account_insights(
#                     insights_data['accountInsights'], 
#                     account, 
#                     client_id, 
#                     source, 
#                     user
#                 )
#                 if account_signals:
#                     signals.extend(account_signals)
            
#             # Contact insights
#             if insights_data.get('contactsInsights') and insights_data['contactsInsights']:
#                 contact_signals = cls._parse_contact_insights(
#                     insights_data['contactsInsights'], 
#                     account, 
#                     client_id, 
#                     source, 
#                     user
#                 )
#                 if contact_signals:
#                     signals.extend(contact_signals)
        
#             # Tech stack data
#             if insights_data.get('techStack') and insights_data['techStack']:
#                 tech_stack_signals = cls._parse_tech_stack_data(
#                     insights_data['techStack'],
#                     account,
#                     client_id,
#                     source,
#                     user
#                 )
#                 if tech_stack_signals:
#                     signals.extend(tech_stack_signals)

#             # Buying process data
#             if insights_data.get('buyingProcess') and insights_data['buyingProcess']:
#                 buying_process_signals = cls._parse_buying_process_data(
#                     insights_data['buyingProcess'],
#                     account,
#                     client_id,
#                     source,
#                     user
#                 )
#                 if buying_process_signals:
#                     signals.extend(buying_process_signals)
                    
#             return signals
    
#     @classmethod
#     def _parse_profile_data(cls, account_info, account, client_id, source, user):
#         """Parse profile data from accountInfo section"""
#         signals = []
        
#         # Basic profile fields mapping (JSON field → model field)
#         profile_fields = {
#             'employeeCount': 'company_size',
#             'annualRevenue': 'annual_revenue',
#             'buyingDecisions': 'has_buying_decision'
#         }
        
#         for json_field, model_field in profile_fields.items():
#             if json_field in account_info and account_info[json_field] is not None:

#                 if json_field == 'employeeCount' and account_info[json_field] == 0:
#                     # Do not create signal if employee count is 0
#                     continue

#                 if json_field == 'annualRevenue' and account_info[json_field] == 0:
#                     # Do not create signal if annual revenue is 0
#                     continue
                
#                 # Profile data usually has low-medium urgency but is foundational
#                 signal = Signal.objects.create(
#                     account=account,
#                     category=Signal.Category.PROFILE,
#                     entity_type=Signal.EntityType.ACCOUNT,
#                     field_name=model_field,
#                     value=account_info[json_field],
#                     status=Signal.Status.PENDING,
#                     source=source,
#                     client_id=client_id,
#                     created_by=user,
#                     updated_by=user
#                 )
#                 signals.append(signal)
                      
#         return signals

#     @classmethod
#     def _parse_account_insights(cls, account_insights, account, client_id, source, user):
#         """Parse account-level insights"""
#         signals = []
        
#         # Process qualification fields
#         qualification_fields = [
#             ('objectives', 'objectives'),
#             ('motivations', 'motivations'),
#             ('metrics', 'metrics'),
#             ('painPoints', 'pain_points'),
#             ('implications', 'implications'),
#             ('partners', 'partners')
#         ]
        
#         for json_field, model_field in qualification_fields:
#             if json_field in account_insights and account_insights[json_field]:
#                 # Create qualification signal
#                 signal = Signal.objects.create(
#                     account=account,
#                     category=Signal.Category.QUALIFICATION,
#                     entity_type=Signal.EntityType.ACCOUNT,
#                     field_name=model_field,
#                     value=account_insights[json_field],
#                     status=Signal.Status.PENDING,
#                     source=source,
#                     client_id=client_id,
#                     created_by=user,
#                     updated_by=user
#                 )
#                 signals.append(signal)
        
#         return signals
    
#     @classmethod
#     def _parse_contact_insights(cls, contacts_insights, account, client_id, source, user):
#         """
#         Parse contact insights without automatically creating contacts.
#         Creates signals with contact information that users can assign later.
#         """
#         signals = []
        
#         for contact_insight in contacts_insights:
#             contact_name = contact_insight.get('contactName')
#             job_title = contact_insight.get('jobTitle')
#             department = contact_insight.get('department')
#             has_budget_authority = contact_insight.get('hasBudgetAuthority', False)
            
#             if not contact_name:
#                 continue
            
#             # Store contact details in the signal metadata for later assignment
#             contact_details = {
#                 'name': contact_name,
#                 'job_title': job_title,
#                 'department': department,
#                 'has_budget_authority': has_budget_authority
#             }
            
#             # Try to find potential matches to suggest
#             potential_matches = []
#             name_parts = contact_name.split(' ', 1)
#             first_name = name_parts[0] if len(name_parts) > 0 else ''
#             last_name = name_parts[1] if len(name_parts) > 1 else ''
            
#             try:
#                 # Find contacts by name (case-insensitive)
#                 from apps.accounts.models import Contact
                
#                 matching_contacts = Contact.objects.filter(
#                     account_id=account.id,
#                     client_id=client_id
#                 ).filter(
#                     Q(first_name__iexact=first_name, last_name__iexact=last_name) |
#                     Q(email__icontains=first_name.lower())
#                 )[:5]  # Limit to 5 suggestions
                
#                 # Add potential matches (just IDs and names for now)
#                 for contact in matching_contacts:
#                     potential_matches.append({
#                         'id': str(contact.id),
#                         'name': f"{contact.first_name} {contact.last_name}",
#                         'job_title': contact.job_title,
#                         'email': contact.email
#                     })
                    
#             except Exception as e:
#                 # Log error but continue
#                 print(f"Error finding potential contact matches: {str(e)}")
            
#             # Process qualification fields
#             qualification_fields = [
#                 ('objectives', 'objectives'),
#                 ('motivations', 'motivations'),
#                 ('metrics', 'metrics'),
#                 ('painPoints', 'pain_points'),
#                 ('implications', 'implications')
#             ]
            
#             # Create signals for each qualification field
#             for json_field, model_field in qualification_fields:
#                 if json_field in contact_insight and contact_insight[json_field]:
#                     # Initialize metadata
#                     metadata = {
#                         'contact_details': contact_details,
#                         'potential_matches': potential_matches,
#                         'needs_assignment': True
#                     }
                    
#                     # Create the signal without assigning to a contact yet
#                     signal = Signal.objects.create(
#                         account=account,
#                         # No contact assigned yet
#                         category=Signal.Category.QUALIFICATION,
#                         entity_type=Signal.EntityType.CONTACT,
#                         field_name=model_field,
#                         value=contact_insight[json_field],
#                         status=Signal.Status.PENDING,
#                         source=source,
#                         client_id=client_id,
#                         created_by=user,
#                         updated_by=user,
#                         metadata=metadata
#                     )
#                     signals.append(signal)
            
#             # Add signals for profile fields (department, has_budget_authority)
#             profile_fields = [
#                 ('department', 'department'),
#                 ('hasBudgetAuthority', 'has_buying_authority')
#             ]
            
#             for json_field, model_field in profile_fields:
#                 if json_field in contact_insight and contact_insight[json_field]:
#                     # Create profile signal with same metadata
#                     metadata = {
#                         'contact_details': contact_details,
#                         'potential_matches': potential_matches,
#                         'needs_assignment': True
#                     }
                    
#                     signal = Signal.objects.create(
#                         account=account,
#                         # No contact assigned yet
#                         category=Signal.Category.PROFILE,
#                         entity_type=Signal.EntityType.CONTACT,
#                         field_name=model_field,
#                         value=contact_insight[json_field],
#                         status=Signal.Status.PENDING,
#                         source=source,
#                         client_id=client_id,
#                         created_by=user,
#                         updated_by=user,
#                         metadata=metadata
#                     )
#                     signals.append(signal)
            
#         return signals
        
#     @classmethod
#     def _parse_tech_stack_data(cls, tech_stack, account, client_id, source, user):
#         """
#         Parse tech stack data from transcript analysis.
#         Creates signals for tech stack information.
        
#         Args:
#             tech_stack: List of tech stack items from the transcript
#             account: Account object
#             client_id: Client ID
#             source: Source of the insights
#             user: User who initiated the analysis
            
#         Returns:
#             list: Created Signal objects for tech stack
#         """
#         signals = []
#         print(f"Tech Stack Data: {tech_stack}")
#         for tech_item in tech_stack:
#             tech_name = tech_item.get('techName')
#             purpose = tech_item.get('purpose', [])
#             pros = tech_item.get('pros', [])
#             improvement_points = tech_item.get('improvementPoints', []) 
#             years_of_usage = tech_item.get('yearsOfUsage')
#             costs = tech_item.get('costs', [])
#             renewal_date = tech_item.get('renewalDate')
            
#             if not tech_name:
#                 continue
            
#             # Create metadata with all tech stack information
#             metadata = {
#                 'tech_name': tech_name,
#                 'purpose': purpose,
#                 'pros': pros,
#                 'improvement_points': improvement_points,
#                 'years_of_usage': years_of_usage,
#                 'costs': costs,
#                 'renewal_date': renewal_date,
#                 'needs_assignment': True  # Indicates this needs user review
#             }
            
#             # Create a signal for the tech stack item
#             signal = Signal.objects.create(
#                 account=account,
#                 category=Signal.Category.TECH_STACK,
#                 entity_type=Signal.EntityType.ACCOUNT,
#                 field_name='tech_stack',
#                 value={
#                     'tech_name': tech_name,
#                     'purpose': purpose,
#                     'pros': pros,
#                     'cons': improvement_points,  
#                     'years_of_usage': years_of_usage,
#                     'costs': costs,
#                     'renewal_date': renewal_date
#                 },
#                 status=Signal.Status.PENDING,
#                 source=source,
#                 client_id=client_id,
#                 created_by=user,
#                 updated_by=user,
#                 metadata=metadata
#             )
#             signals.append(signal)
        
#         return signals
    
#     @classmethod
#     def _parse_buying_process_data(cls, buying_process_data, account, client_id, source, user):
#         """
#         Parse buying process data from transcript analysis.
#         Creates a signal for each identified buying process step.
        
#         Args:
#             buying_process_data: List of buying process steps from the transcript
#             account: Account object
#             client_id: Client ID
#             source: Source of the insights
#             user: User who initiated the analysis
            
#         Returns:
#             list: Created Signal objects for buying process steps
#         """
#         signals = []
#         print(f"Buying Process Data: {buying_process_data}")
#         for step_data in buying_process_data:
#             # Standardize the step data format
#             formatted_step = {
#                 'stakeholder': step_data.get('stakeholder', ''),
#                 'department_name': step_data.get('department', ''),
#                 'step_description': step_data.get('stepDescription', ''),
#                 'step_goal': step_data.get('stepGoal', ''),
#                 'influence_score': step_data.get('influenceScore', 0),
#                 'criterias': step_data.get('criterias', []),
#                 'metrics': step_data.get('metrics', []),
#                 'average_time_in_days': step_data.get('averageTimeInDays', 0)
#             }
            
#             # Create a signal for this step
#             signal = Signal.objects.create(
#                 account=account,
#                 category=Signal.Category.PROCESS,
#                 entity_type=Signal.EntityType.ACCOUNT,
#                 field_name='buying_process_step',
#                 value=formatted_step,
#                 status=Signal.Status.PENDING,
#                 source=source,
#                 client_id=client_id,
#                 created_by=user,
#                 updated_by=user,
#                 metadata={
#                     'needs_position_assignment': True,  # Flag that position needs to be assigned
#                     'needs_process_assignment': True,   # Flag that process needs to be assigned
#                     'step_data': formatted_step
#                 }
#             )
#             print(f"Created Buying Process Signal: {signal.id} with data: {formatted_step}")
#             signals.append(signal)
    
#         return signals