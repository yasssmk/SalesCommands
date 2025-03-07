# apps/sales_insight/services/signal_parsing_service.py

from django.utils import timezone
from ..models import Signal
from apps.core_apps.models import StandardDepartment
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from apps.accounts_app.contacts.models import Contact
from apps.accounts_app.account_product_detail.models import AccountProductDetail
from apps.products.models import Product

class SignalParsingService:
    """
    Service for parsing AI-generated insights into signals.
    Transforms LLM JSON output into structured signals categorized for sales effectiveness.
    """
    
    @classmethod
    def parse_insights(cls, insights, account, org_unit=None, source='ai_analysis', user=None):
        """
        Parse structured insights from LLM into Signal objects.
        
        Args:
            insights (dict): Structured insights from LLM
            account (Account): Account object
            org_unit (AccountOrganizationUnit, optional): Organization unit
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
            
            # Org Unit insights
            if 'orgUnitsInsights' in insights_data:
                org_unit_signals = cls._parse_org_unit_insights(
                    insights_data['orgUnitsInsights'], 
                    account, 
                    org_unit, 
                    client_id, 
                    source, 
                    user
                )
                signals.extend(org_unit_signals)
                
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
            'accountType': 'type',
            'classification': 'classification',
            'employeeCount': 'company_size',
            'annualRevenue': 'annual_revenue',
            'buyingDecisionsLocation': 'metadata'  # Store in metadata JSON field
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
                
        # Handle parent company if present
        if 'parentCompany' in account_info and account_info['parentCompany'].get('companyName'):
            signal = Signal.objects.create(
                account=account,
                category=Signal.Category.PROFILE,
                entity_type=Signal.EntityType.ACCOUNT,
                field_name='parent_company',
                value=account_info['parentCompany'],
                status=Signal.Status.PENDING,
                source=source,
                client_id=client_id,
                created_by=user,
                updated_by=user
            )
            signals.append(signal)
            
        return signals
    @classmethod
    def _find_matching_org_unit(cls, account, org_name, client_id):
        """
        Find existing org unit or matching standard department.
        Returns:
        - exact_match: Exact org unit match if found
        - similar_units: List of similar org units
        - std_department: Matching standard department (for creation)
        """
        results = {
            'exact_match': None,
            'similar_units': [],
            'std_department': None
        }
        
        # Step 1: Try to find exact match by name
        exact_match = AccountOrganizationUnit.objects.filter(
            account_id=account.id,
            organization_name__iexact=org_name,
            client_id=client_id
        ).first()
        
        if exact_match:
            results['exact_match'] = exact_match
            return results
        
        # Step 2: Try to match keywords to find a standard department
        from apps.core_apps.models import StandardDepartment
        std_dept = None
        
        dept_keywords = org_name.lower().split()
        if dept_keywords:
            for keyword in dept_keywords:
                if len(keyword) >= 3:  # Only consider meaningful keywords
                    possible_depts = StandardDepartment.objects.filter(
                        name__icontains=keyword
                    )
                    if possible_depts.exists():
                        std_dept = possible_depts.first()
                        break
        
        # If we found a standard department, look for other org units with it
        if std_dept:
            results['std_department'] = std_dept
            similar_units = AccountOrganizationUnit.objects.filter(
                account_id=account.id,
                standard_department=std_dept,
                client_id=client_id
            )
            
            if similar_units.exists():
                results['similar_units'] = list(similar_units)
        
        return results

    @classmethod
    def _parse_account_insights(cls, account_insights, account, client_id, source, user):
        """Parse account-level insights"""
        signals = []
        
        # Process qualification fields
        qualification_fields = [
            ('objectives', 'objectives'),
            ('compellingEvents', 'compelling_events'),
            ('motivations', 'motivations'),
            ('keyKPIs', 'key_kpis'),
            ('criteria', 'criteria'),
            ('painPoints', 'pain_points'),
            ('implications', 'implications'),
            ('partners', 'partners'),
            ('budget', 'budget'),
            ('newBudgetStartDate', 'new_budget_start_date')
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
                
                # For high-priority fields, try to find product alignment
                if model_field in ['pain_points', 'compelling_events', 'implications']:
                    cls._detect_and_set_product_alignment(signal, account_insights[json_field])
    
        # Process tech stack (special handling)
        if 'currentTechStack' in account_insights and account_insights['currentTechStack']:
            tech_stack_signals = cls._parse_tech_stack(
                account_insights['currentTechStack'],
                account,
                client_id,
                source,
                user,
                Signal.EntityType.ACCOUNT
            )
            signals.extend(tech_stack_signals)
        
        # Process buying process
        if 'buyingProcess' in account_insights and account_insights['buyingProcess']:
            signal = Signal.objects.create(
                account=account,
                category=Signal.Category.PROCESS,
                entity_type=Signal.EntityType.ACCOUNT,
                field_name='buying_process',
                value=account_insights['buyingProcess'],
                status=Signal.Status.PENDING,
                source=source,
                client_id=client_id,
                created_by=user,
                updated_by=user
            )
            signals.append(signal)
        
        # Process projects (highest value signals)
        if 'projects' in account_insights and account_insights['projects']:
            project_signals = cls._parse_projects(
                account_insights['projects'],
                account,
                client_id,
                source,
                user,
                Signal.EntityType.ACCOUNT
            )
            signals.extend(project_signals)
            
        return signals
    
    @classmethod
    def _parse_org_unit_insights(cls, org_units_insights, account, provided_org_unit, client_id, source, user):
        """Parse organization unit insights"""
        signals = []
        
        for org_insight in org_units_insights:
            org_name = org_insight.get('organizationName')
            unit_type = org_insight.get('unitType')
            
            if not org_name:
                continue
                
            # Try to find or match org unit
            org_unit_results = cls._find_matching_org_unit(account, org_name, client_id)
            target_org_unit = org_unit_results['exact_match']
            
            # Create signals with metadata about org unit validation needs
            org_unit_metadata = {
                'needs_validation': True,
                'proposed_name': org_name,
                'proposed_unit_type': unit_type,
                'matching_std_department_id': org_unit_results['std_department'].id if org_unit_results['std_department'] else None,
                'similar_unit_ids': [unit.id for unit in org_unit_results['similar_units']]
            }
                
            # Process qualification fields
            qualification_fields = [
                ('objectives', 'objectives'),
                ('compellingEvents', 'compelling_events'),
                ('motivations', 'motivations'),
                ('keyKPIs', 'key_kpis'),
                ('criteria', 'criteria'),
                ('painPoints', 'pain_points'),  
                ('implications', 'implications'),
                ('partners', 'partners'),
                ('budget', 'budget'),
                ('newBudgetStartDate', 'new_budget_start_date')
            ]
            
            for json_field, model_field in qualification_fields:
                if json_field in org_insight and org_insight[json_field]:
                    # Create signal with org unit validation metadata
                    signal = Signal.objects.create(
                        account=account,
                        org_unit=target_org_unit,  # May be None
                        category=Signal.Category.QUALIFICATION,
                        entity_type=Signal.EntityType.ORG_UNIT,
                        field_name=model_field,
                        value=org_insight[json_field],
                        status=Signal.Status.PENDING,
                        source=source,
                        metadata=org_unit_metadata,
                        client_id=client_id,
                        created_by=user,
                        updated_by=user
                    )
                    signals.append(signal)
                    
            # For high-value signals, find product alignment and APD
            # if value_score >= 60:
            #     products = cls._detect_and_set_product_alignment(signal, org_insight[json_field])
                        
            # # Link to APDs
            # cls._link_to_account_product_details(signal, account, products, target_org_unit)
            
            # Process tech stack (special handling)
            if 'currentTechStack' in org_insight and org_insight['currentTechStack']:
                tech_stack_signals = cls._parse_tech_stack(
                    org_insight['currentTechStack'],
                    account,
                    client_id,
                    source,
                    user,
                    Signal.EntityType.ORG_UNIT,
                    target_org_unit
                )
                signals.extend(tech_stack_signals)
            
            # Process projects (highest value signals)
            if 'projects' in org_insight and org_insight['projects']:
                project_signals = cls._parse_projects(
                    org_insight['projects'],
                    account,
                    client_id,
                    source,
                    user,
                    Signal.EntityType.ORG_UNIT,
                    target_org_unit
                )
                signals.extend(project_signals)
                
        return signals
    
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
            from apps.accounts_app.contacts.models import Contact
            
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
                    # Try to find org unit
                    org_unit = None
                    if org_unit_name:
                        org_unit = AccountOrganizationUnit.objects.filter(
                            account_id=account.id,
                            organization_name__iexact=org_unit_name,
                            client_id=client_id
                        ).first()
                    
                    # Create contact
                    target_contact = Contact.objects.create(
                        account=account,
                        first_name=first_name,
                        last_name=last_name,
                        job_title=role,
                        org_unit=org_unit,
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
                org_unit=org_unit,
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
                org_unit=org_unit,
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
            cls._link_to_account_product_details(signal, account, products, org_unit, 
                                                estimated_units=project.get('estimatedUnitsNeeded'),
                                                budget=project.get('budgetAllocation'))
            
        return signals
    
    @classmethod
    def _detect_and_set_product_alignment(cls, signal, data, is_competitor=False):
        """
        Detect product alignment from text and set on signal.
        Returns list of detected products.
        """
        try:
            # Get all products for simple keyword matching
            # In a real system, this would use NLP/ML for better matching
            all_products = Product.objects.all()
            matched_products = []
            
            # Convert data to string for text search
            if isinstance(data, dict):
                search_text = str(data)
            elif isinstance(data, list):
                search_text = " ".join([str(item) for item in data])
            else:
                search_text = str(data)
                
            search_text = search_text.lower()
            
            # Simple keyword matching
            for product in all_products:
                # Check if product name appears in text
                if product.product_name.lower() in search_text:
                    matched_products.append(product)
                    
                # Check custom keywords if available
                if hasattr(product, 'keywords') and product.keywords:
                    keywords = product.keywords.lower().split(',')
                    for keyword in keywords:
                        if keyword.strip() in search_text:
                            if product not in matched_products:
                                matched_products.append(product)
            
            # Add products to signal
            if matched_products:
                signal.product_alignment.add(*matched_products)
                
            return matched_products
            
        except Exception as e:
            # Log error but don't block signal creation
            print(f"Error in product alignment detection: {str(e)}")
            return []
    
    @classmethod
    def _link_to_account_product_details(cls, signal, account, products, org_unit=None, 
                                       is_competitor=False, estimated_units=None, budget=None):
        """Link signal to appropriate AccountProductDetail objects"""
        try:
            if not products:
                return
                
            for product in products:
                # Try to find existing APD
                apd = AccountProductDetail.objects.filter(
                    account=account,
                    product=product
                ).first()
                
                # If no APD exists, consider creating one
                if not apd :  
                    # Create APD with minimal info
                    try:
                        # Get default pricing if available
                        default_pricing = product.pricing_models.first()
                        
                        # Estimate units based on signal or default to 1
                        units = estimated_units or 1
                        
                        apd = AccountProductDetail.objects.create(
                            account=account,
                            product=product,
                            estimated_units=units,
                            selected_pricing=default_pricing,
                            client_id=account.client_id,

                        )
                        
                        # Add org unit to target units if provided
                        if org_unit:
                            apd.target_org_units.add(org_unit)
                            
                    except Exception as e:
                        print(f"Error creating APD: {str(e)}")
                        continue
                
                # Link signal to APD if we found or created one
                if apd:
                    signal.account_product_detail = apd
                    signal.save(update_fields=['account_product_detail'])
                    
                        
        except Exception as e:
            # Log error but don't block signal processing
            print(f"Error linking to APD: {str(e)}")
    
    @classmethod
    def _map_unit_type(cls, unit_type_str):
        """Map text unit type to model choice"""
        from apps.accounts_app.org_units.models import AccountOrganizationUnit
        
        unit_type_str = (unit_type_str or '').upper()
        
        if 'DEPARTMENT' in unit_type_str:
            return AccountOrganizationUnit.UnitType.DEPARTMENT
        elif 'DIVISION' in unit_type_str:
            return AccountOrganizationUnit.UnitType.DIVISION
        elif 'TEAM' in unit_type_str:
            return AccountOrganizationUnit.UnitType.TEAM
        else:
            # Default to department
            return AccountOrganizationUnit.UnitType.DEPARTMENT