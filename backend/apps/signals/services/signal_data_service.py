# apps/signals/services/signal_data_service.py

from ..models.qualification_signal_model import QualificationSignal
from ..models.tech_stack_signal_model import TechStackSignal
from ..models.profile_signal_model import ProfileSignal


class SignalDataService:
    """
    Service for retrieving and formatting signal data from different signal types.
    Provides optimized queries and consistent data formatting for UI consumption.
    """
    
    @classmethod
    def get_account_profile_data(cls, account, include_signal_info=False):
        """
        Get profile signals for an account.
        
        Args:
            account: Account object
            include_signal_info: Whether to include detailed signal information
            
        Returns:
            dict: Profile data organized by field
        """
        # Get approved profile signals with optimized query
        profile_signals = ProfileSignal.objects.filter(
            account=account,
            status=ProfileSignal.Status.APPROVED
        ).select_related(
            'source_contact',
            'source_department'
        ).order_by('-confirmation_count', '-last_confirmed_at')
        
        # Organize by field_name, taking the most confirmed/recent value
        result = {}
        field_values = {}
        
        for signal in profile_signals:
            field = signal.field_name
            
            # For profile fields, we usually want the most confirmed value
            if field not in field_values or signal.confirmation_count > field_values[field]['confirmation_count']:
                field_values[field] = {
                    'signal': signal,
                    'confirmation_count': signal.confirmation_count,
                    'last_confirmed_at': signal.last_confirmed_at
                }
        
        # Convert to final format
        for field, data in field_values.items():
            result[field] = cls._format_signal(data['signal'], include_signal_info)
            
        return result
    
    @classmethod
    def get_account_qualification_data(cls, account, field_names=None, department=None, 
                                    source_contact=None, min_confirmations=None, 
                                    include_signal_info=False):
        """
        Get qualification signals for an account with filtering.
        
        Args:
            account: Account object
            field_names: Optional list of specific fields to retrieve
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum confirmation count
            include_signal_info: Whether to include detailed signal information
            
        Returns:
            dict: Qualification data organized by field

        """

        # Default field names if not provided
        if not field_names:
            field_names = [choice[0] for choice in QualificationSignal.Field.choices]
            
        # Start with base query
        query = QualificationSignal.objects.filter(
            account=account,
            status=QualificationSignal.Status.APPROVED
        ).select_related(
            'source_contact',
            'source_department'
        )
        
        # Apply filters
        if department:
            query = query.filter(source_department=department)
            
        if source_contact:
            query = query.filter(source_contact=source_contact)
            
        if min_confirmations:
            query = query.filter(confirmation_count__gte=min_confirmations)
            
        if field_names:
            if isinstance(field_names, list):
                query = query.filter(field_name__in=field_names)
            else:
                query = query.filter(field_name=field_names)
        
        # Group by field_name
        result = {}
        
        for signal in query:
            field = signal.field_name
            if field not in result:
                result[field] = []
                
            result[field].append(cls._format_signal(signal, include_signal_info))
            
        return result
    
    @classmethod
    def get_tech_stack_data(cls, account, tech_stack=None, field_names=None, department=None,
                        source_contact=None, min_confirmations=None, include_signal_info=False):
        """
        Get tech stack signals for an account or specific tech stack.
        
        Args:
            account: Account object
            tech_stack: Optional tech stack object
            field_names: Optional list of specific fields to retrieve
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum confirmation count
            include_signal_info: Whether to include detailed signal information
            
        Returns:
            dict: Tech stack data organized by tech stack and field
        """
        # Default field names if not provided
        if not field_names:
            field_names = [choice[0] for choice in TechStackSignal.Field.choices]
        
        # Start with base query
        query = TechStackSignal.objects.filter(
            account=account,
            status=TechStackSignal.Status.APPROVED
        ).select_related(
            'tech_stack',
            'source_contact',
            'source_department'
        )
        
        # Filter by tech stack if provided
        if tech_stack:
            query = query.filter(tech_stack=tech_stack)
            
        # Apply other filters
        if department:
            query = query.filter(source_department=department)
            
        if source_contact:
            query = query.filter(source_contact=source_contact)
            
        if min_confirmations:
            query = query.filter(confirmation_count__gte=min_confirmations)
            
        if field_names:
            if isinstance(field_names, list):
                query = query.filter(field_name__in=field_names)
            else:
                query = query.filter(field_name=field_names)
        
        # If specific tech stack requested, return fields directly
        if tech_stack:
            result = {}
            for signal in query:
                field = signal.field_name
                if field not in result:
                    result[field] = []
                    
                result[field].append(cls._format_signal(signal, include_signal_info))
                
            return result
            
        # Otherwise, group by tech stack
        result = {}
        for signal in query:
            tech_id = str(signal.tech_stack.id)
            if tech_id not in result:
                result[tech_id] = {
                    'tech_id': tech_id,
                    'tech_name': signal.tech_stack.tech_name,
                    'fields': {}
                }
                
            field = signal.field_name
            if field not in result[tech_id]['fields']:
                result[tech_id]['fields'][field] = []
                
            result[tech_id]['fields'][field].append(cls._format_signal(signal, include_signal_info))
            
        return result
    
    @classmethod
    def get_by_department(cls, account, signal_type, field_names=None, include_signal_info=False):
        """
        Get signals organized by department.
        
        Args:
            account: Account object
            signal_type: Signal type class (QualificationSignal, etc.)
            field_names: Optional list of field names to include
            include_signal_info: Whether to include detailed signal information
            
        Returns:
            dict: Signals organized by department
        """
        from apps.core_apps.models import StandardDepartment
        
        # Determine which method to call based on signal type
        if signal_type == QualificationSignal:
            data_method = cls.get_account_qualification_data
        elif signal_type == TechStackSignal:
            data_method = cls.get_tech_stack_data
        elif signal_type == ProfileSignal:
            data_method = cls.get_account_profile_data
        else:
            raise ValueError(f"Unsupported signal type: {signal_type}")
        
        result = {}
        
        # Get all departments
        departments = StandardDepartment.objects.all()
        
        for department in departments:
            # Get data filtered by this department
            department_data = data_method(
                account=account,
                field_names=field_names,
                department=department,
                include_signal_info=include_signal_info
            )
            
            if department_data:
                result[department.name] = {
                    'department_id': department.id,
                    'department_name': department.get_name_display(),
                    'data': department_data
                }
        
        return result
    
    @classmethod
    def _format_signal(cls, signal, include_signal_info=False):
        """
        Format a signal for API response.
        
        Args:
            signal: Signal object
            include_signal_info: Whether to include detailed signal information
            
        Returns:
            dict: Formatted signal data
        """
        # Basic data always included
        data = {
            'value': signal.value,
            'confirmation_count': signal.confirmation_count,
            'last_confirmed_at': signal.last_confirmed_at,
        }
        
        # Include additional info if requested
        if include_signal_info:
            data.update({
                'id': signal.id,
                'source': signal.source,
                'created_at': signal.created_at,
                'approved_at': signal.approved_at
            })
            
            # Include source contact if available
            if signal.source_contact:
                data['source_contact'] = {
                    'id': signal.source_contact.id,
                    'name': f"{getattr(signal.source_contact, 'first_name', '')} {getattr(signal.source_contact, 'last_name', '')}".strip()
                }
                
            # Include source department if available
            if signal.source_department:
                data['source_department'] = {
                    'id': signal.source_department.id,
                    'name': getattr(signal.source_department, 'name', '')
                }
                
        return data