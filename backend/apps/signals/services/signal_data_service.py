# apps/signals/services/signal_data_service.py

from django.db.models import Q
from apps.signals.models import Signal
from django.utils import timezone

class SignalDataService:
    """
    Service for retrieving and aggregating data from signals.
    Provides methods to access qualification data and other signal-based information.
    """
    
    @classmethod
    def get_account_qualification_data(cls, account, field_names=None, department=None, 
                                      source_contact=None, min_confirmations=None, 
                                      include_signal_info=False, status=None):
        """
        Get all qualification data for an account from signals.
        
        Args:
            account: Account object to get data for
            field_names: Optional list of specific fields to retrieve
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum number of confirmations required
            include_signal_info: Whether to include signal metadata
            status: Optional signal status to filter by (defaults to APPROVED, APPLIED)
            
        Returns:
            dict: Qualification data from signals
        """
        if not field_names:
            # Default to all qualification fields
            field_names = [
                Signal.Field.OBJECTIVES,
                Signal.Field.MOTIVATIONS,
                Signal.Field.METRICS,
                Signal.Field.PAIN_POINTS,
                Signal.Field.IMPLICATIONS
            ]
        
        if not status:
            status = [Signal.Status.APPROVED, Signal.Status.APPLIED]
        
        result = {}
        
        for field_name in field_names:
            field_data = cls.get_field_data(
                account=account,
                field_name=field_name,
                department=department,
                source_contact=source_contact,
                min_confirmations=min_confirmations,
                include_signal_info=include_signal_info,
                status=status
            )
            
            if field_data:
                result[field_name] = field_data.get('value', [])
                
                if include_signal_info and 'signals' in field_data:
                    result[f"{field_name}_signals"] = field_data['signals']
        
        return result
    
    @classmethod
    def get_tech_stack_data(cls, account, tech_stack=None, field_names=None, department=None,
                           source_contact=None, min_confirmations=None, 
                           include_signal_info=False, status=None):
        """
        Get tech stack data for an account from signals.
        
        Args:
            account: Account object to get data for
            tech_stack: Optional TechStack object to filter by
            field_names: Optional list of specific fields to retrieve
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum number of confirmations required
            include_signal_info: Whether to include signal metadata
            status: Optional signal status to filter by (defaults to APPROVED, APPLIED)
            
        Returns:
            dict: Tech stack data from signals
        """
        if not field_names:
            # Default to all tech stack fields
            field_names = [
                Signal.Field.PROS,
                Signal.Field.CONS,
                Signal.Field.PURPOSE,
                Signal.Field.ANNUAL_COSTS,
                Signal.Field.RENEWAL_DATE,
                Signal.Field.START_YEAR_OF_USAGE
            ]
        
        if not status:
            status = [Signal.Status.APPROVED, Signal.Status.APPLIED]
        
        result = {}
        
        # Get tech stack specific metadata 
        if tech_stack:
            # Tech stack specific metadata (which signals apply to which tech stack)
            tech_metadata_filter = {
                'tech_stack_id': str(tech_stack.id)
            }
        else:
            tech_metadata_filter = None
        
        for field_name in field_names:
            field_data = cls.get_field_data(
                account=account,
                field_name=field_name,
                department=department,
                source_contact=source_contact,
                min_confirmations=min_confirmations,
                include_signal_info=include_signal_info,
                status=status,
                metadata_filter=tech_metadata_filter
            )
            
            if field_data:
                result[field_name] = field_data.get('value', [])
                
                if include_signal_info and 'signals' in field_data:
                    result[f"{field_name}_signals"] = field_data['signals']
        
        return result
    
    @classmethod
    def get_field_data(cls, account, field_name, department=None, source_contact=None,
                      min_confirmations=None, include_signal_info=False, status=None,
                      metadata_filter=None):
        """
        Get data for a specific field from signals.
        
        Args:
            account: Account object to get data for
            field_name: Field name to get data for
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum number of confirmations required
            include_signal_info: Whether to include signal metadata
            status: Optional signal status to filter by (defaults to APPROVED, APPLIED)
            metadata_filter: Optional filter for signal metadata
            
        Returns:
            dict: Field data from signals
        """
        # Base query to get signals for this field
        query = Signal.objects.filter(
            account=account,
            field_name=field_name
        )
        
        # Add status filter
        if status:
            if isinstance(status, list):
                query = query.filter(status__in=status)
            else:
                query = query.filter(status=status)
        else:
            # Default to approved/applied signals
            query = query.filter(status__in=[Signal.Status.APPROVED, Signal.Status.APPLIED])
        
        # Add department filter if provided
        if department:
            query = query.filter(source_department=department)
        
        # Add source contact filter if provided
        if source_contact:
            query = query.filter(source_contact=source_contact)
        
        # Add confirmation count filter if provided
        if min_confirmations:
            query = query.filter(confirmation_count__gte=min_confirmations)
        
        # Add metadata filter if provided
        if metadata_filter:
            for key, value in metadata_filter.items():
                # Filter signals that have this metadata key/value
                query = query.filter(Q(metadata__contains={key: value}))
        
        # Check if we have any signals
        if not query.exists():
            return None
        
        # Combine values from all signals
        combined_values = []
        signals_info = []
        
        for signal in query:
            if isinstance(signal.value, list):
                combined_values.extend(signal.value)
            else:
                combined_values.append(signal.value)
                
            if include_signal_info:
                signals_info.append({
                    'id': signal.id,
                    'status': signal.status,
                    'source': signal.source,
                    'value': signal.value,
                    'source_contact_id': signal.source_contact_id,
                    'source_department_id': signal.source_department_id,
                    'confirmation_count': signal.confirmation_count,
                    'created_at': signal.created_at,
                    'last_confirmed_at': signal.last_confirmed_at,
                    'metadata': signal.metadata
                })
        
        # Return combined data
        result = {
            'value': combined_values
        }
        
        if include_signal_info:
            result['signals'] = signals_info
            
        return result
    
    @classmethod
    def get_profile_by_department(cls, account):
        """
        Get qualification data aggregated by department.
        
        Args:
            account: Account object to get data for
            
        Returns:
            dict: Qualification data organized by department
        """
        from apps.core_apps.models import StandardDepartment
        
        result = {}
        
        # Get all departments
        departments = StandardDepartment.objects.all()
        
        for department in departments:
            department_data = cls.get_account_qualification_data(
                account=account,
                department=department,
                include_signal_info=False
            )
            
            if department_data:
                result[department.name] = {
                    'department_id': department.id,
                    'department_name': department.get_name_display(),
                    'data': department_data
                }
        
        return result
    
    @classmethod
    def get_tech_stack_by_department(cls, account):
        """
        Get tech stack data aggregated by department.
        
        Args:
            account: Account object to get data for
            
        Returns:
            dict: Tech stack data organized by department
        """
        from apps.core_apps.models import StandardDepartment
        
        result = {}
        
        # Get all departments
        departments = StandardDepartment.objects.all()
        
        for department in departments:
            department_data = cls.get_tech_stack_data(
                account=account,
                department=department,
                include_signal_info=False
            )
            
            if department_data:
                result[department.name] = {
                    'department_id': department.id,
                    'department_name': department.get_name_display(),
                    'data': department_data
                }
        
        return result
    
    @classmethod
    def get_field_signals(cls, account, field_name, entity_type=None, department=None, 
                         source_contact=None, min_confirmations=None, 
                         status=None, include_expired=False):
        """
        Get signals for a specific field with filtering options.
        
        Args:
            account: Account to get signals for
            field_name: Field name to get signals for
            entity_type: Optional entity type to filter by
            department: Optional department to filter by
            source_contact: Optional source contact to filter by
            min_confirmations: Minimum number of confirmations required
            status: Specific status to filter by (default: APPROVED, APPLIED)
            include_expired: Whether to include expired signals
            
        Returns:
            QuerySet: Filtered signals
        """
        # Base query for this field
        query = Signal.objects.filter(
            account=account,
            field_name=field_name
        )
        
        # Add entity type filter if provided
        if entity_type:
            query = query.filter(entity_type=entity_type)
        
        # Add status filter
        if status:
            if isinstance(status, list):
                query = query.filter(status__in=status)
            else:
                query = query.filter(status=status)
        else:
            # Default to approved/applied signals
            query = query.filter(status__in=[Signal.Status.APPROVED, Signal.Status.APPLIED])
        
        # Add department filter if provided
        if department:
            query = query.filter(source_department=department)
        
        # Add source contact filter if provided
        if source_contact:
            query = query.filter(source_contact=source_contact)
        
        # Add confirmation count filter if provided
        if min_confirmations:
            query = query.filter(confirmation_count__gte=min_confirmations)
        
        # Add expiration filter
        if not include_expired:
            from apps.signals.services.signal_lifecycle_service import SignalLifecycleService
            
            # Calculate expiration cutoffs
            profile_expiry = timezone.now() - timezone.timedelta(days=SignalLifecycleService.TIME_TO_EXPIRED_PROFILE)
            process_expiry = timezone.now() - timezone.timedelta(days=SignalLifecycleService.TIME_TO_EXPIRED_PROCESS)
            
            # Exclude signals that have effectively expired
            query = query.exclude(
                Q(status__in=['APPROVED', 'APPLIED']) &
                (
                    Q(category__in=['PROFILE', 'QUALIFICATION'], last_confirmed_at__lte=profile_expiry) |
                    Q(category='PROCESS', last_confirmed_at__lte=process_expiry)
                )
            )
        
        return query
    
    @classmethod
    def check_for_updates(cls, account, last_synced_at):
        """
        Check if there are any signal updates since the last sync.
        
        Args:
            account: Account to check for
            last_synced_at: Datetime of last sync
            
        Returns:
            dict: Count of updates by category
        """
        if not last_synced_at:
            # If no sync time provided, just return everything
            return {
                'has_updates': True,
                'total_count': Signal.objects.filter(account=account).count()
            }
        
        # Check for signals that were created, updated, confirmed or applied since the last sync
        updates = Signal.objects.filter(
            account=account
        ).filter(
            Q(created_at__gt=last_synced_at) |
            Q(updated_at__gt=last_synced_at) |
            Q(approved_at__gt=last_synced_at) |
            Q(applied_date__gt=last_synced_at) |
            Q(last_confirmed_at__gt=last_synced_at)
        )
        
        if not updates.exists():
            return {
                'has_updates': False,
                'total_count': 0
            }
        
        # Count updates by category
        update_counts = {}
        for category in Signal.Category.values:
            count = updates.filter(category=category).count()
            if count > 0:
                update_counts[category] = count
        
        return {
            'has_updates': True,
            'total_count': updates.count(),
            'updates_by_category': update_counts
        }
    
    @classmethod
    def verify_field_value(cls, account, field_name, value, 
                          department=None, min_confirmations=None):
        """
        Verify if a specific value exists in signals for a field.
        Useful for checking if information is already known.
        
        Args:
            account: Account to check
            field_name: Field name to check
            value: Value to look for
            department: Optional department to filter by
            min_confirmations: Minimum confirmation count
            
        Returns:
            dict: Match information including confirmation count and last update
        """
        # Get signals for this field
        signals = cls.get_field_signals(
            account=account,
            field_name=field_name,
            department=department,
            min_confirmations=min_confirmations
        )
        
        # Look for value match
        matched_signals = []
        
        for signal in signals:
            signal_value = signal.value
            
            # Handle list values
            if isinstance(signal_value, list) and not isinstance(value, list):
                # If signal value is a list but search value is not,
                # check if value is in the list
                if any(item == value for item in signal_value):
                    matched_signals.append(signal)
            elif isinstance(signal_value, list) and isinstance(value, list):
                # If both are lists, check for overlap
                if any(item in value for item in signal_value):
                    matched_signals.append(signal)
            else:
                # Direct comparison
                if signal_value == value:
                    matched_signals.append(signal)
        
        if not matched_signals:
            return {
                'found': False,
                'confirmation_count': 0,
                'matched_signals': []
            }
        
        # Get the highest confirmation count
        max_confirmations = max(signal.confirmation_count for signal in matched_signals)
        latest_signal = max(matched_signals, key=lambda s: s.last_confirmed_at)
        
        return {
            'found': True,
            'confirmation_count': max_confirmations,
            'last_confirmed_at': latest_signal.last_confirmed_at,
            'matched_signals': [{'id': s.id, 'status': s.status} for s in matched_signals]
        }