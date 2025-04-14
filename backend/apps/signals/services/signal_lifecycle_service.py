# # apps/sales_insight/services/signal_lifecycle_service.py

# from django.utils import timezone
# from django.db import transaction
# from ..models import Signal
# import logging

# logger = logging.getLogger(__name__)

# class SignalLifecycleService:
#     """
#     Service for managing signal lifecycle with confirmation tracking.
#     Works alongside existing SignalStatusService and SignalApplicationService.
#     """

            
#     TIME_TO_EXPIRED_PROFILE = 365
#     TIME_TO_EXPIRED_PROCESS = 730
    
#     @classmethod
#     def confirm_signal(cls, signal, user=None, source=None):
#         """
#         Confirm a signal, incrementing confirmation count and updating last_confirmed_at.
        
#         Args:
#             signal: The signal to confirm
#             user: User performing the confirmation
#             source: Source of the confirmation (e.g., 'manual', 'transcript')
            
#         Returns:
#             Signal: The updated signal
#         """
#         with transaction.atomic():
#             # Increment confirmation count
#             signal.confirmation_count += 1
#             signal.last_confirmed_at = timezone.now()
            
#             # Initialize metadata if needed
#             if not signal.metadata:
#                 signal.metadata = {}
                
#             # Track confirmation history
#             if 'confirmations' not in signal.metadata:
#                 signal.metadata['confirmations'] = []
                
#             # Add confirmation record
#             confirmation_data = {
#                 'confirmed_by': str(user.id) if user else 'system',
#                 'confirmed_at': timezone.now().isoformat(),
#                 'current_count': signal.confirmation_count,
#                 'source': source or 'direct_confirmation'
#             }
            
#             signal.metadata['confirmations'].append(confirmation_data)
            
#             signal.save()
#             return signal
    
#     @classmethod
#     def merge_signals(cls, target_signal, source_signal, user=None):
#         """
#         Merge source signal into target signal for confirmation tracking.
#         This links the signals and increments confirmation count, but
#         doesn't modify the actual signal value.
        
#         Args:
#             target_signal: Signal to merge into (the one that will remain active)
#             source_signal: Signal to merge from (will be marked as merged)
#             user: User performing the merge
            
#         Returns:
#             Signal: The updated target signal
#         """
#         with transaction.atomic():
#             # Increment confirmation count
#             target_signal.confirmation_count += 1
#             target_signal.last_confirmed_at = timezone.now()

#             if target_signal.category != source_signal.category or target_signal.field_name != source_signal.field_name:
#                 from core.exceptions import StandardizedValidationError
#                 from core.error_messages import CoreErrorMessages
#                 raise StandardizedValidationError(
#                     CoreErrorMessages.INVALID_OPERATION.format(
#                         operation="Signals must have the same category and field name to be merged"
#                     )
#                 )
            
#             # Initialize metadata if needed
#             if not target_signal.metadata:
#                 target_signal.metadata = {}
                
#             # Track confirmation history
#             if 'confirmations' not in target_signal.metadata:
#                 target_signal.metadata['confirmations'] = []
                
#             # Add confirmation record
#             target_signal.metadata['confirmations'].append({
#                 'confirmed_by': str(user.id) if user else 'system',
#                 'confirmed_at': timezone.now().isoformat(),
#                 'current_count': target_signal.confirmation_count,
#                 'source': 'merge',
#                 'merged_signal_id': str(source_signal.id),
#                 'merged_signal_source': source_signal.source
#             })
            
#             # Mark source signal as merged
#             source_signal.status = Signal.Status.MERGED
#             source_signal.merged_into = target_signal
            
#             if not source_signal.metadata:
#                 source_signal.metadata = {}
                
#             source_signal.metadata['merged_at'] = timezone.now().isoformat()
#             source_signal.metadata['merged_by'] = str(user.id) if user else 'system'
            
#             # Save both signals
#             target_signal.save()
#             source_signal.save()
            
#             return target_signal
    
#     @classmethod
#     def bulk_merge(cls, target_signal, signals, user=None):
#         """
#         Merge multiple signals into a target signal.
        
#         Args:
#             target_signal: Signal to merge into
#             signals: List or QuerySet of signals to merge from
#             user: User performing the merge
            
#         Returns:
#             dict: Summary of results with counts
#         """
#         results = {
#             'total': len(signals),
#             'merged_count': 0,
#             'failed_count': 0,
#             'failed_ids': []
#         }
        
#         for signal in signals:
#             try:
#                 # Skip the target signal if it's in the list
#                 if signal.id == target_signal.id:
#                     continue
                    
#                 # Skip signals that are already merged
#                 if signal.status == Signal.Status.MERGED:
#                     results['failed_count'] += 1
#                     results['failed_ids'].append({
#                         'id': str(signal.id),
#                         'reason': 'Signal is already merged into another signal'
#                     })
#                     continue
                    
#                 # Validate signals are compatible for merging
#                 if signal.category != target_signal.category or signal.field_name != target_signal.field_name:
#                     results['failed_count'] += 1
#                     results['failed_ids'].append({
#                         'id': str(signal.id),
#                         'reason': 'Signal category or field_name does not match target signal'
#                     })
#                     continue
                
#                 # Perform the merge
#                 cls.merge_signals(
#                     target_signal=target_signal,
#                     source_signal=signal,
#                     user=user
#                 )
                
#                 results['merged_count'] += 1
                
#             except Exception as e:
#                 results['failed_count'] += 1
#                 results['failed_ids'].append({
#                     'id': str(signal.id),
#                     'reason': str(e)
#                 })
        
#         return results
    
#     @classmethod
#     def get_effective_status(cls, signal):
#         """
#         Calculate the effective status of a signal based on its age and category.
#         This is a just-in-time calculation that doesn't update the database.
        
#         Args:
#             signal: The signal to check
            
#         Returns:
#             str: The effective status
#         """
#         # Skip for certain statuses
#         if signal.status in [Signal.Status.PENDING, Signal.Status.REJECTED, Signal.Status.MERGED]:
#             return signal.status
            
#         # Project data doesn't expire
#         if signal.category == Signal.Category.PROJECT:
#             return signal.status
        
#         # Calculate age in days
#         age_days = (timezone.now() - signal.last_confirmed_at).days
        
#         # Check expiration based on category
#         if signal.category in [Signal.Category.PROFILE, Signal.Category.QUALIFICATION]:
#             if age_days > cls.TIME_TO_EXPIRED_PROFILE:
#                 return "EXPIRED"
#         elif signal.category == Signal.Category.PROCESS:
#             if age_days > cls.TIME_TO_EXPIRED_PROCESS:
#                 return "EXPIRED"
                
#         return signal.status
    
#     @classmethod
#     def get_signals_by_confirmation_count(cls, account=None, min_count=2, field_name=None, entity_type=None):
#         """
#         Get signals with at least the specified confirmation count.
#         Useful for finding highly confirmed signals.
        
#         Args:
#             account: Optional account to filter by
#             min_count: Minimum confirmation count
#             field_name: Optional field name to filter by
#             entity_type: Optional entity type to filter by
            
#         Returns:
#             QuerySet: Filtered signals
#         """
#         query = Signal.objects.filter(
#             confirmation_count__gte=min_count
#         )
        
#         if account:
#             query = query.filter(account=account)
            
#         if field_name:
#             query = query.filter(field_name=field_name)
            
#         if entity_type:
#             query = query.filter(entity_type=entity_type)
            
#         return query
    
#     @classmethod
#     def get_signals_for_field(cls, account, field_name, entity_type=None):
#         """
#         Get all signals that contributed to a field value, including those that were 
#         merged. Useful for showing where information came from.
        
#         Args:
#             account: Account to get signals for
#             field_name: Field name to get signals for
#             entity_type: Optional entity type to filter by
            
#         Returns:
#             dict: Dictionary with applied and merged signals
#         """
#         # Base query for this account and field
#         query = Signal.objects.filter(
#             account=account,
#             field_name=field_name,
#         )
        
#         if entity_type:
#             query = query.filter(entity_type=entity_type)
        
#         # Get applied/approved signals
#         active_signals = query.filter(
#             status__in=[Signal.Status.APPROVED, Signal.Status.APPLIED]
#         )
        
#         # Get merged signals
#         merged_signals = query.filter(
#             status=Signal.Status.MERGED,
#             merged_into__in=active_signals
#         )
        
#         return {
#             'active': active_signals,
#             'merged': merged_signals
#         }

#     @classmethod
#     def find_matching_signals(cls, signal):
#         """
#         Find existing signals that match this one's field and entity.
#         Used for automatic merging and confirmation.
        
#         Args:
#             signal: Signal to find matches for
            
#         Returns:
#             QuerySet: Matching signals
#         """
#         # Find signals with the same account, field, and category
#         matches = Signal.objects.filter(
#             account=signal.account,
#             field_name=signal.field_name,
#             category=signal.category,
#             entity_type=signal.entity_type,
#             status__in=[Signal.Status.APPROVED, Signal.Status.APPLIED]
#         ).exclude(id=signal.id)
        
#         # Add contact-specific matching if relevant
#         if signal.source_contact:
#             matches = matches.filter(source_contact=signal.source_contact)
        
#         # Add department-specific matching if relevant
#         if signal.source_department:
#             matches = matches.filter(source_department=signal.source_department)
        
#         return matches

#     @classmethod
#     def find_conflicting_signals(cls, signal):
#         """
#         Find existing signals that conflict with this one.
#         Used for highlighting potential conflicts during approval.
        
#         Args:
#             signal: Signal to find conflicts for
            
#         Returns:
#             QuerySet: Conflicting signals
#         """
#         # Find signals with the same account, field but different value
#         from django.db.models import Q
#         import json
        
#         # Get a JSON string of the value for comparison
#         try:
#             value_json = json.dumps(signal.value)
#         except (TypeError, ValueError):
#             value_json = json.dumps(str(signal.value))
        
#         # Find active signals for the same field
#         active_signals = Signal.objects.filter(
#             account=signal.account,
#             field_name=signal.field_name,
#             category=signal.category,
#             entity_type=signal.entity_type,
#             status__in=[Signal.Status.APPROVED, Signal.Status.APPLIED]
#         ).exclude(id=signal.id)
        
#         # Now filter for those with different values
#         conflicts = []
#         for existing in active_signals:
#             try:
#                 existing_json = json.dumps(existing.value)
#             except (TypeError, ValueError):
#                 existing_json = json.dumps(str(existing.value))
            
#             if existing_json != value_json:
#                 conflicts.append(existing.id)
        
#         if conflicts:
#             return Signal.objects.filter(id__in=conflicts)
        
#         return Signal.objects.none()

#     @classmethod
#     def auto_merge_or_confirm(cls, signal, user=None):
#         """
#         Automatically merge or confirm a signal with matching existing signals.
        
#         Args:
#             signal: Newly approved signal
#             user: User performing the action
            
#         Returns:
#             dict: Result of the operation
#         """
#         # Find matching signals
#         matches = cls.find_matching_signals(signal)
        
#         if not matches.exists():
#             return {
#                 'action': 'none',
#                 'message': 'No matching signals found'
#             }
        
#         # If we have matching signals, find the most confirmed one
#         most_confirmed = matches.order_by('-confirmation_count').first()
        
#         # If the new signal exactly matches the value of an existing one,
#         # merge it or confirm the existing one
#         import json
#         try:
#             signal_json = json.dumps(signal.value)
#             most_confirmed_json = json.dumps(most_confirmed.value)
            
#             if signal_json == most_confirmed_json:
#                 # Values match, confirm the most confirmed signal
#                 updated = cls.confirm_signal(most_confirmed, user, f"Auto-confirmed from signal {signal.id}")
                
#                 # Mark the new signal as merged
#                 signal.status = Signal.Status.MERGED
#                 signal.merged_into = most_confirmed
#                 signal.save(update_fields=['status', 'merged_into'])
                
#                 return {
#                     'action': 'merged',
#                     'merged_into': most_confirmed.id,
#                     'confirmation_count': updated.confirmation_count
#                 }
#         except (TypeError, ValueError):
#             # If JSON serialization fails, just skip auto-merging
#             pass
        
#         return {
#             'action': 'none',
#             'message': 'No exact matches for auto-merging'
#         }