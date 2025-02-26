from django.utils import timezone
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, F, Prefetch
from apps.sales_insight.models import QualificationChange
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from apps.accounts_app.contacts.models import Contact
from core.exceptions import StandardizedValidationError

class QualificationService:
    """
    Service class for handling qualification data processing and change management.
    Supports partial human modifications during approval and separate approval workflows
    for different entity types.
    """
    
    ENTITY_TYPES = {
        'account': Account,
        'org_unit': AccountOrganizationUnit,
        'contact': Contact
    }
    
    @classmethod
    @transaction.atomic
    def process_ai_data(cls, ai_data, account_id, user, source="ai_analysis"):
        """
        Process AI-generated data for an account and all related entities.
        
        Args:
            ai_data (dict): AI-generated data
            account_id (str): ID of the account
            user (User): User making the request
            source (str): Source of the data
            
        Returns:
            dict: Dictionary with pending changes for each entity type
        """
        result = {
            'account': {},
            'org_units': {},
            'contacts': {}
        }
        
        # Process account
        try:
            account = Account.objects.select_for_update().get(id=account_id, client_id=user.client_account)
            result['account'] = cls.process_account_data(account, ai_data, user, source)
        except Account.DoesNotExist:
            raise StandardizedValidationError(_("Account not found"))
        
        # Get all org units for the account
        org_units = AccountOrganizationUnit.objects.select_for_update().filter(account_id=account_id)
        for org_unit in org_units:
            result['org_units'][org_unit.organization_name] = cls.process_org_unit_data(org_unit, ai_data, user, source)
        
        # Process new org units from AI data
        cls._process_new_org_units(ai_data, account_id, user, source, result)
        
        # Get all contacts for the account
        contacts = Contact.objects.select_for_update().filter(account_id=account_id)
        for contact in contacts:
            result['contacts'][f"{contact.first_name} {contact.last_name}"] = cls.process_contact_data(contact, ai_data, user, source)
        
        # Process new contacts from AI data
        cls._process_new_contacts(ai_data, account_id, user, source, result)
        
        return result
    
    @classmethod
    def process_account_data(cls, account, ai_data, user, source):
        """
        Process qualification data from AI-generated insights for an account.
        
        Args:
            account (Account): Account model instance
            ai_data (dict): AI-generated data
            user (User): User making the request
            source (str): Source of the data
            
        Returns:
            dict: Dictionary with pending changes
        """
        # Get account insights data
        account_info = ai_data.get('accountInfo', {})
        account_insights = ai_data.get('insights', {}).get('accountInsights', {})
        pending_changes = {}
        
        # Process basic account fields
        basic_fields = [
            ('company_size', 'employeeCount'),
            ('annual_revenue', 'annualRevenue'),
            ('classification', 'classification'),
            ('type', 'accountType')
        ]
        
        for model_field, api_field in basic_fields:
            if api_field in account_info and account_info[api_field]:
                current_value = getattr(account, model_field)
                new_value = account_info[api_field]
                
                # Convert to appropriate format if needed
                if model_field in ['company_size', 'annual_revenue'] and isinstance(new_value, (int, float)):
                    new_value = str(new_value)
                
                # Create a change if the value is different or we don't have a value yet
                if (current_value is None or str(current_value) != str(new_value)):
                    change = cls.create_change_record(
                        'account', account.id, model_field, current_value, new_value, user, source
                    )
                    
                    pending_changes[model_field] = {
                        'change_id': change.id,
                        'old_value': current_value,
                        'new_value': new_value
                    }
        
        # Process qualification fields (from QualificationModel)
        qualification_field_mapping = {
            'objectives': 'objectives',
            'compelling_events': 'compellingEvents',
            'motivations': 'motivations',
            'key_kpis': 'keyKPIs',
            'criteria': 'criteria',
            'pain_points': 'painPoints',
            'implications': 'implications',
            'current_tech_stack': 'currentTechStack',
            'partners': 'partners',
            'budget': 'budget',
            'new_budget_start_date': 'newBudgetStartDate',
            'buying_process': 'buyingProcess',
            'projects': 'projects'
        }
        
        for model_field, api_field in qualification_field_mapping.items():
            if api_field in account_insights and account_insights[api_field]:
                current_value = getattr(account, model_field)
                new_value = account_insights[api_field]
                
                # Create a change if the value is different or we don't have a value yet
                if (current_value is None or current_value != new_value):
                    change = cls.create_change_record(
                        'account', account.id, model_field, current_value, new_value, user, source
                    )
                    
                    pending_changes[model_field] = {
                        'change_id': change.id,
                        'old_value': current_value,
                        'new_value': new_value
                    }
        
        return pending_changes
    
    @classmethod
    def process_org_unit_data(cls, org_unit, ai_data, user, source):
        """
        Process qualification data from AI-generated insights for an org unit.
        
        Args:
            org_unit (AccountOrganizationUnit): Org unit model instance
            ai_data (dict): AI-generated data
            user (User): User making the request
            source (str): Source of the data
            
        Returns:
            dict: Dictionary with pending changes
        """
        # Find this org unit in the AI data
        org_unit_data = None
        for ou in ai_data.get('insights', {}).get('orgUnitsInsights', []):
            if ou.get('organizationName') == org_unit.organization_name:
                org_unit_data = ou
                break
        
        if not org_unit_data:
            return {}  # No data for this org unit
        
        pending_changes = {}
        
        # Check unit type
        if 'unitType' in org_unit_data and org_unit_data['unitType']:
            unit_type = org_unit_data['unitType']
            if unit_type in [choice[0] for choice in org_unit.UnitType.choices] and unit_type != org_unit.unit_type:
                change = cls.create_change_record(
                    'org_unit', org_unit.id, 'unit_type', org_unit.unit_type, unit_type, user, source
                )
                pending_changes['unit_type'] = {
                    'change_id': change.id,
                    'old_value': org_unit.unit_type,
                    'new_value': unit_type
                }
        
        # Process qualification fields
        qualification_field_mapping = {
            'objectives': 'objectives',
            'compelling_events': 'compellingEvents',
            'motivations': 'motivations',
            'key_kpis': 'keyKPIs',
            'criteria': 'criteria',
            'pain_points': 'painPoints',
            'implications': 'implications',
            'current_tech_stack': 'currentTechStack',
            'partners': 'partners',
            'budget': 'budget',
            'new_budget_start_date': 'newBudgetStartDate',
            'buying_process': 'buyingProcess',
            'projects': 'projects'
        }
        
        for model_field, api_field in qualification_field_mapping.items():
            if api_field in org_unit_data and org_unit_data[api_field]:
                current_value = getattr(org_unit, model_field)
                new_value = org_unit_data[api_field]
                
                # Create a change if the value is different or we don't have a value yet
                if current_value is None or current_value != new_value:
                    change = cls.create_change_record(
                        'org_unit', org_unit.id, model_field, current_value, new_value, user, source
                    )
                    
                    pending_changes[model_field] = {
                        'change_id': change.id,
                        'old_value': current_value,
                        'new_value': new_value
                    }
        
        return pending_changes
    
    @classmethod
    def process_contact_data(cls, contact, ai_data, user, source):
        """
        Process qualification data from AI-generated insights for a contact.
        
        Args:
            contact (Contact): Contact model instance
            ai_data (dict): AI-generated data
            user (User): User making the request
            source (str): Source of the data
            
        Returns:
            dict: Dictionary with pending changes
        """
        # Find this contact in the AI data
        contact_data = None
        for c in ai_data.get('insights', {}).get('contactsInsights', []):
            if c.get('contactName') == f"{contact.first_name} {contact.last_name}":
                contact_data = c
                break
        
        if not contact_data:
            return {}  # No data for this contact
        
        pending_changes = {}
        
        # Basic contact info updates
        basic_field_mapping = {
            'job_title': 'role',
            'influence_level': 'influenceLevel'
        }
        
        for model_field, api_field in basic_field_mapping.items():
            if api_field in contact_data and contact_data[api_field]:
                current_value = getattr(contact, model_field)
                new_value = contact_data[api_field]
                
                if current_value is None or current_value != new_value:
                    change = cls.create_change_record(
                        'contact', contact.id, model_field, current_value, new_value, user, source
                    )
                    
                    pending_changes[model_field] = {
                        'change_id': change.id,
                        'old_value': current_value,
                        'new_value': new_value
                    }
        
        # Check for organization unit update
        if 'orgUnit' in contact_data and contact_data['orgUnit']:
            # This would require a lookup to find the actual org unit object
            # We'll handle this in a service layer
            pass
        
        # Process qualification fields
        qualification_field_mapping = {
            'objectives': 'objectives',
            'compelling_events': 'compellingEvents',
            'motivations': 'motivations',
            'key_kpis': 'keyKPIs',
            'criteria': 'criteria',
            'pain_points': 'painPoints',
            'implications': 'implications',
            'current_tech_stack': 'currentTechStack',
            'partners': 'partners',
            'projects': 'projectsInvolved'  # Note the different field name
        }
        
        for model_field, api_field in qualification_field_mapping.items():
            if api_field in contact_data and contact_data[api_field]:
                current_value = getattr(contact, model_field)
                new_value = contact_data[api_field]
                
                # For special cases like 'objectives' which may have a different structure
                if model_field == 'objectives' and isinstance(new_value, list) and all(isinstance(item, dict) for item in new_value):
                    # Extract just the goals from the objectives
                    new_value = [item.get('goal') for item in new_value if 'goal' in item]
                
                # Create a change if the value is different or we don't have a value yet
                if current_value is None or current_value != new_value:
                    change = cls.create_change_record(
                        'contact', contact.id, model_field, current_value, new_value, user, source
                    )
                    
                    pending_changes[model_field] = {
                        'change_id': change.id,
                        'old_value': current_value,
                        'new_value': new_value
                    }
        
        return pending_changes
    
    @classmethod
    def create_change_record(cls, entity_type, entity_id, field_name, old_value, new_value, user, source):
        """
        Create a qualification change record.
        
        Args:
            entity_type (str): Type of entity ('account', 'org_unit', 'contact')
            entity_id: ID of the entity
            field_name (str): Field name
            old_value: Current value
            new_value: New value
            user (User): User making the change
            source (str): Source of the change
            
        Returns:
            QualificationChange: The created change record
        """
        return QualificationChange.objects.create(
            client_id=user.client_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            status='pending',
            created_by=user,
            source=source
        )
    
    @staticmethod
    def _process_new_org_units(ai_data, account_id, user, source, result):
        """Process any new org units found in AI data"""
        for org_unit_data in ai_data.get('insights', {}).get('orgUnitsInsights', []):
            org_name = org_unit_data.get('organizationName')
            if not org_name or org_name in result['org_units']:
                continue
            
            # Create a new org unit
            unit_type = org_unit_data.get('unitType', 'DEPARTMENT')
            if unit_type not in [choice[0] for choice in AccountOrganizationUnit.UnitType.choices]:
                unit_type = 'DEPARTMENT'
            
            # Get standard department
            from apps.core_apps.models import StandardDepartment
            try:
                # Try to map based on name
                std_dept = None
                for dept_choice in StandardDepartment.DepartmentChoices.choices:
                    if dept_choice[1].lower() in org_name.lower():
                        std_dept = StandardDepartment.objects.get(name=dept_choice[0])
                        break
                
                # If no match, use General Management
                if not std_dept:
                    std_dept = StandardDepartment.objects.get(
                        name=StandardDepartment.DepartmentChoices.GENERAL_MANAGEMENT
                    )
            except StandardDepartment.DoesNotExist:
                # Fallback to first department
                std_dept = StandardDepartment.objects.first()
            
            # Create the new org unit
            new_org_unit = AccountOrganizationUnit.objects.create(
                client_id=user.client_account,
                account_id=account_id,
                organization_name=org_name,
                unit_type=unit_type,
                standard_department=std_dept,
                created_by=user
            )
            
            # Process qualification data for the new org unit
            result['org_units'][org_name] = QualificationService.process_org_unit_data(
                new_org_unit, ai_data, user, source
            )
    
    @staticmethod
    def _process_new_contacts(ai_data, account_id, user, source, result):
        """Process any new contacts found in AI data"""
        for contact_data in ai_data.get('insights', {}).get('contactsInsights', []):
            contact_name = contact_data.get('contactName')
            if not contact_name or contact_name in result['contacts']:
                continue
            
            # Split name into parts
            name_parts = contact_name.split(' ', 1)
            if len(name_parts) < 2:
                # Skip contacts without first and last name
                continue
            
            first_name, last_name = name_parts
            
            # See if we can find an org unit for this contact
            org_unit = None
            if contact_data.get('orgUnit'):
                try:
                    org_unit = AccountOrganizationUnit.objects.get(
                        account_id=account_id,
                        organization_name=contact_data.get('orgUnit')
                    )
                except AccountOrganizationUnit.DoesNotExist:
                    pass
            
            # Create the contact
            new_contact = Contact.objects.create(
                client_id=user.client_id,
                account_id=account_id,
                first_name=first_name,
                last_name=last_name,
                job_title=contact_data.get('role'),
                influence_level=contact_data.get('influenceLevel'),
                organization_unit=org_unit,
                created_by=user
            )
            
            # Process qualification data for the new contact
            result['contacts'][contact_name] = QualificationService.process_contact_data(
                new_contact, ai_data, user, source
            )
    
    @classmethod
    @transaction.atomic
    def approve_changes_with_modifications(cls, changes_data, user):
        """
        Approve multiple changes with human modifications.
        
        Args:
            changes_data (list): List of dictionaries with change data
                Each dict should have:
                - change_id: ID of the change
                - modified_value: Value after human modification (None/null to remove the field)
                - action: 'approve' or 'reject'
            user (User): User approving the changes
            
        Returns:
            dict: Dictionary with results for each change
        """
        results = {
            'approved': [],
            'rejected': [],
            'errors': []
        }
        
        if not changes_data:
            return results
        
        # Get all change IDs for efficient querying
        change_ids = [item.get('change_id') for item in changes_data if item.get('change_id')]
        
        # Fetch all changes in one query
        changes_map = {
            str(change.id): change for change in QualificationChange.objects.filter(
                id__in=change_ids,
                client_id=user.client_id,
                status='pending'
            )
        }
        
        # Group changes by entity for efficient processing
        entity_changes = {}
        for change_data in changes_data:
            change_id = str(change_data.get('change_id'))
            if change_id not in changes_map:
                results['errors'].append({
                    'change_id': change_id,
                    'error': 'Change not found or already processed'
                })
                continue
            
            change = changes_map[change_id]
            entity_key = f"{change.entity_type}:{change.entity_id}"
            
            if entity_key not in entity_changes:
                entity_changes[entity_key] = []
            
            entity_changes[entity_key].append({
                'change': change,
                'modified_value': change_data.get('modified_value'),
                'action': change_data.get('action', 'approve')
            })
        
        # Process changes by entity to reduce database operations
        for entity_key, changes_list in entity_changes.items():
            entity_type, entity_id = entity_key.split(':')
            
            if entity_type not in cls.ENTITY_TYPES:
                for change_data in changes_list:
                    results['errors'].append({
                        'change_id': change_data['change'].id,
                        'error': f"Unknown entity type: {entity_type}"
                    })
                continue
            
            try:
                # Get the entity once for all its changes
                entity = cls.ENTITY_TYPES[entity_type].objects.select_for_update().get(
                    id=entity_id, client_id=user.client_id
                )
                
                # Process each change for this entity
                for change_data in changes_list:
                    change = change_data['change']
                    modified_value = change_data['modified_value']
                    action = change_data['action']
                    
                    if action == 'reject':
                        # Reject the change
                        change.status = 'rejected'
                        change.approved_by = user
                        change.approved_at = timezone.now()
                        change.save(update_fields=['status', 'approved_by', 'approved_at'])
                        results['rejected'].append(change.id)
                    else:
                        # Approve with possibly modified value
                        change.status = 'approved'
                        change.approved_by = user
                        change.approved_at = timezone.now()
                        
                        # Update the new_value if it was modified
                        if modified_value != change.new_value:
                            change.new_value = modified_value
                        
                        change.save()
                        
                        # Update entity if value is not None (None means remove/don't apply)
                        if modified_value is not None:
                            entity.update_qualification_field(change.field_name, modified_value, user)
                        
                        results['approved'].append(change.id)
                
            except cls.ENTITY_TYPES[entity_type].DoesNotExist:
                # Entity not found, reject all its changes
                for change_data in changes_list:
                    change = change_data['change']
                    change.status = 'rejected'
                    change.approved_by = user
                    change.approved_at = timezone.now()
                    change.save(update_fields=['status', 'approved_by', 'approved_at'])
                    
                    results['errors'].append({
                        'change_id': change.id,
                        'error': f"Entity not found: {entity_type} {entity_id}"
                    })
        
        return results
    
    @classmethod
    @transaction.atomic
    def approve_entity_changes(cls, account_id, entity_type, changes_data, user):
        """
        Approve changes for a specific entity type within an account.
        This supports the separate approval flows for Account, OrgUnit, and Contact.
        
        Args:
            account_id (str): ID of the account
            entity_type (str): Type of entity ('account', 'org_unit', 'contact')
            changes_data (list): List of dictionaries with change data
            user (User): User approving the changes
            
        Returns:
            dict: Dictionary with results
        """
        if entity_type not in cls.ENTITY_TYPES:
            raise StandardizedValidationError(f"Invalid entity type: {entity_type}")
        
        # For account, we need to verify the account ID matches
        if entity_type == 'account':
            # Filter changes to make sure they're for this account
            filtered_changes = []
            for change_data in changes_data:
                change_id = change_data.get('change_id')
                if not change_id:
                    continue
                
                try:
                    change = QualificationChange.objects.get(
                        id=change_id, 
                        entity_type='account',
                        client_id=user.client_id,
                        status='pending'
                    )
                    
                    # Verify it's for this account
                    if str(change.entity_id) == str(account_id):
                        filtered_changes.append(change_data)
                except QualificationChange.DoesNotExist:
                    pass
            
            return cls.approve_changes_with_modifications(filtered_changes, user)
        
        # For org_unit and contact, we need to get all entities for this account
        elif entity_type == 'org_unit':
            # Get all org unit IDs for this account
            org_unit_ids = AccountOrganizationUnit.objects.filter(
                account_id=account_id
            ).values_list('id', flat=True)
            
            # Filter changes to make sure they're for org units in this account
            filtered_changes = []
            for change_data in changes_data:
                change_id = change_data.get('change_id')
                if not change_id:
                    continue
                
                try:
                    change = QualificationChange.objects.get(
                        id=change_id, 
                        entity_type='org_unit',
                        client_id=user.client_id,
                        status='pending'
                    )
                    
                    # Verify it's for an org unit in this account
                    if change.entity_id in org_unit_ids:
                        filtered_changes.append(change_data)
                except QualificationChange.DoesNotExist:
                    pass
            
            return cls.approve_changes_with_modifications(filtered_changes, user)
        
        elif entity_type == 'contact':
            # Get all contact IDs for this account
            contact_ids = Contact.objects.filter(
                account_id=account_id
            ).values_list('id', flat=True)
            
            # Filter changes to make sure they're for contacts in this account
            filtered_changes = []
            for change_data in changes_data:
                change_id = change_data.get('change_id')
                if not change_id:
                    continue
                
                try:
                    change = QualificationChange.objects.get(
                        id=change_id, 
                        entity_type='contact',
                        client_id=user.client_id,
                        status='pending'
                    )
                    
                    # Verify it's for a contact in this account
                    if change.entity_id in contact_ids:
                        filtered_changes.append(change_data)
                except QualificationChange.DoesNotExist:
                    pass
            
            return cls.approve_changes_with_modifications(filtered_changes, user)
    
    @classmethod
    def get_pending_changes_by_entity_type(cls, account_id, entity_type, user):
        """
        Get pending changes for a specific entity type within an account.
        
        Args:
            account_id (str): ID of the account
            entity_type (str): Type of entity ('account', 'org_unit', 'contact')
            user (User): User making the request
            
        Returns:
            dict: Dictionary of pending changes
        """
        # Verify account exists and belongs to user's client
        try:
            account = Account.objects.get(id=account_id, client_id=user.client_id)
        except Account.DoesNotExist:
            raise StandardizedValidationError(_("Account not found"))
        
        if entity_type == 'account':
            # Get changes for the account itself
            return {
                'account': QualificationChange.objects.filter(
                    entity_type='account',
                    entity_id=account_id,
                    status='pending',
                    client_id=user.client_id
                ).order_by('-created_at').select_related('created_by')
            }
        
        elif entity_type == 'org_unit':
            # Get all org units for this account
            org_units = AccountOrganizationUnit.objects.filter(account_id=account_id)
            org_unit_ids = [str(unit.id) for unit in org_units]
            
            # Get pending changes for these org units
            changes = QualificationChange.objects.filter(
                entity_type='org_unit',
                entity_id__in=org_unit_ids,
                status='pending',
                client_id=user.client_id
            ).order_by('-created_at').select_related('created_by')
            
            # Group changes by org unit
            result = {}
            org_unit_map = {str(unit.id): unit.organization_name for unit in org_units}
            
            for change in changes:
                org_name = org_unit_map.get(str(change.entity_id))
                if not org_name:
                    continue
                
                if org_name not in result:
                    result[org_name] = []
                
                result[org_name].append(change)
            
            return {'org_units': result}
        
        elif entity_type == 'contact':
            # Get all contacts for this account
            contacts = Contact.objects.filter(account_id=account_id)
            contact_ids = [str(contact.id) for contact in contacts]
            
            # Get pending changes for these contacts
            changes = QualificationChange.objects.filter(
                entity_type='contact',
                entity_id__in=contact_ids,
                status='pending',
                client_id=user.client_id
            ).order_by('-created_at').select_related('created_by')
            
            # Group changes by contact
            result = {}
            contact_map = {
                str(contact.id): f"{contact.first_name} {contact.last_name}" 
                for contact in contacts
            }
            
            for change in changes:
                contact_name = contact_map.get(str(change.entity_id))
                if not contact_name:
                    continue
                
                if contact_name not in result:
                    result[contact_name] = []
                
                result[contact_name].append(change)
            
            return {'contacts': result}
        
        else:
            raise StandardizedValidationError(f"Invalid entity type: {entity_type}")
    
    @classmethod
    def get_all_pending_changes(cls, account_id, user):
        """
        Get all pending changes for an account and its related entities.
        
        Args:
            account_id (str): ID of the account
            user (User): User making the request
            
        Returns:
            dict: Dictionary of pending changes grouped by entity
        """
        # Get changes for each entity type
        account_changes = cls.get_pending_changes_by_entity_type(account_id, 'account', user)
        org_unit_changes = cls.get_pending_changes_by_entity_type(account_id, 'org_unit', user)
        contact_changes = cls.get_pending_changes_by_entity_type(account_id, 'contact', user)
        
        # Combine the results
        return {
            'account': account_changes.get('account', []),
            'org_units': org_unit_changes.get('org_units', {}),
            'contacts': contact_changes.get('contacts', {})
        }
    
    @classmethod
    def get_change_history(cls, account_id, entity_type, entity_id, user):
        """
        Get the change history for a specific entity.
        
        Args:
            account_id (str): ID of the account
            entity_type (str): Type of entity ('account', 'org_unit', 'contact')
            entity_id (str): ID of the entity
            user (User): User making the request
            
        Returns:
            dict: Historical data for the entity
        """
        if entity_type not in cls.ENTITY_TYPES:
            raise StandardizedValidationError(f"Invalid entity type: {entity_type}")
        
        try:
            # For account, entity_id should match account_id
            if entity_type == 'account':
                if str(entity_id) != str(account_id):
                    raise StandardizedValidationError(_("Entity ID does not match account ID"))
                
                entity = Account.objects.get(id=account_id, client_id=user.client_id)
            
            # For org_unit, verify it belongs to the account
            elif entity_type == 'org_unit':
                entity = AccountOrganizationUnit.objects.get(
                    id=entity_id,
                    account_id=account_id,
                    client_id=user.client_id
                )
            
            # For contact, verify it belongs to the account
            elif entity_type == 'contact':
                entity = Contact.objects.get(
                    id=entity_id,
                    account_id=account_id,
                    client_id=user.client_id
                )
            
            # Return the historical data
            return entity.historical_data or {}
            
        except cls.ENTITY_TYPES[entity_type].DoesNotExist:
            raise StandardizedValidationError(_("Entity not found"))
            
    @classmethod
    def get_full_change_history(cls, account_id, user):
        """
        Get the complete change history for an account and all related entities.
        
        Args:
            account_id (str): ID of the account
            user (User): User making the request
            
        Returns:
            dict: Dictionary of historical data grouped by entity
        """
        # Verify account exists and belongs to user's client
        try:
            account = Account.objects.get(id=account_id, client_id=user.client_id)
        except Account.DoesNotExist:
            raise StandardizedValidationError(_("Account not found"))
        
        result = {
            'account': account.historical_data or {},
            'org_units': {},
            'contacts': {}
        }
        
        # Get all org units for the account
        org_units = AccountOrganizationUnit.objects.filter(account_id=account_id)
        for org_unit in org_units:
            if org_unit.historical_data:
                result['org_units'][org_unit.organization_name] = org_unit.historical_data
        
        # Get all contacts for the account
        contacts = Contact.objects.filter(account_id=account_id)
        for contact in contacts:
            if contact.historical_data:
                result['contacts'][f"{contact.first_name} {contact.last_name}"] = contact.historical_data
        
        return result