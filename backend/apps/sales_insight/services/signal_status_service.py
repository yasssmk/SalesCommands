# apps/sales_insight/services/signal_status_service.py

from django.utils import timezone
from django.db import transaction
from ..models import Signal
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

class SignalStatusService:
    """
    Service for managing signal status transitions.
    Handles approval, rejection, and other status changes.
    """
    
    @classmethod
    def approve_signal(cls, signal, user=None):
        """
        Approve a signal, making it eligible for application.
        
        Args:
            signal: The Signal to approve
            user: User performing the approval
            
        Returns:
            Signal: The updated signal
        """
        # Allow approval from any status except APPLIED
        if signal.status == Signal.Status.APPLIED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation="Cannot approve a signal that has already been applied"
                )
            )
            
        with transaction.atomic():
            # Record previous status for audit
            previous_status = signal.status
            
            signal.status = Signal.Status.APPROVED
            signal.approved_by = user
            signal.approved_at = timezone.now()
            
            # Store transition history if metadata exists
            if hasattr(signal, 'metadata') and signal.metadata is not None:
                if 'status_history' not in signal.metadata:
                    signal.metadata['status_history'] = []
                    
                signal.metadata['status_history'].append({
                    'from_status': previous_status,
                    'to_status': Signal.Status.APPROVED,
                    'changed_by': str(user.id) if user else None,
                    'changed_at': timezone.now().isoformat(),
                    'reason': 'User approval'
                })
                signal.save(update_fields=['status', 'approved_by', 'approved_at', 'metadata'])
            else:
                signal.save(update_fields=['status', 'approved_by', 'approved_at'])
            
            return signal
        
    @classmethod
    def reject_signal(cls, signal, user=None, reason=None):
        """
        Reject a signal, preventing it from being applied.
        
        Args:
            signal: The Signal to reject
            user: User performing the rejection
            reason: Optional reason for rejection
            
        Returns:
            Signal: The updated signal
        """
        # Allow rejection from any status except APPLIED
        if signal.status == Signal.Status.APPLIED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation="Cannot reject a signal that has already been applied"
                )
            )
            
        with transaction.atomic():
            # Record previous status for audit
            previous_status = signal.status
            
            signal.status = Signal.Status.REJECTED
            signal.approved_by = user
            signal.approved_at = timezone.now()
            
            # Initialize metadata if needed
            if not hasattr(signal, 'metadata') or not signal.metadata:
                signal.metadata = {}
                
            # Store status history
            if 'status_history' not in signal.metadata:
                signal.metadata['status_history'] = []
                
            history_entry = {
                'from_status': previous_status,
                'to_status': Signal.Status.REJECTED,
                'changed_by': str(user.id) if user else None,
                'changed_at': timezone.now().isoformat()
            }
            
            # Add reason if provided
            if reason:
                history_entry['reason'] = reason
                signal.metadata['rejection_reason'] = reason
                
            signal.metadata['status_history'].append(history_entry)
            signal.save(update_fields=['status', 'approved_by', 'approved_at', 'metadata'])
            
            return signal
    
    @classmethod
    def mark_dormant(cls, signal, user=None):
        """
        Mark a signal as dormant (inactive but preserved).
        
        Args:
            signal: The Signal to mark dormant
            user: User performing the action
            
        Returns:
            Signal: The updated signal
        """
        # Can mark any signal as dormant regardless of current status
        with transaction.atomic():
            signal.status = Signal.Status.DORMANT
            signal.save(update_fields=['status'])
            
            return signal
    
    @classmethod
    def bulk_approve(cls, signals, user=None):
        """
        Approve multiple signals in bulk.
        
        Args:
            signals: QuerySet or list of Signal objects to approve
            user: User performing the approval
            
        Returns:
            dict: Summary of results with counts
        """
        results = {
            'total': len(signals),
            'approved_count': 0,
            'failed_count': 0,
            'failed_ids': []
        }
        
        for signal in signals:
            try:
                # Allow approval from any status except APPLIED
                if signal.status != Signal.Status.APPLIED:
                    cls.approve_signal(signal, user)
                    results['approved_count'] += 1
                else:
                    results['failed_count'] += 1
                    results['failed_ids'].append({
                        'id': str(signal.id),
                        'reason': 'Signal has already been applied'
                    })
            except Exception as e:
                results['failed_count'] += 1
                results['failed_ids'].append({
                    'id': str(signal.id),
                    'reason': str(e)
                })
                
        return results

    @classmethod
    def bulk_reject(cls, signals, user=None, reason=None):
            """
            Reject multiple signals in bulk.
            
            Args:
                signals: QuerySet or list of Signal objects to reject
                user: User performing the rejection
                reason: Optional common reason for rejection
                
            Returns:
                dict: Summary of results with counts
            """
            results = {
                'total': len(signals),
                'rejected_count': 0,
                'failed_count': 0,
                'failed_ids': []
            }
            
            for signal in signals:
                try:
                    # Allow rejection from any status except APPLIED
                    if signal.status != Signal.Status.APPLIED:
                        cls.reject_signal(signal, user, reason)
                        results['rejected_count'] += 1
                    else:
                        results['failed_count'] += 1
                        results['failed_ids'].append({
                            'id': str(signal.id),
                            'reason': 'Signal has already been applied'
                        })
                except Exception as e:
                    results['failed_count'] += 1
                    results['failed_ids'].append({
                        'id': str(signal.id),
                        'reason': str(e)
                    })
                    
            return results