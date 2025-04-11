# apps/signals/serializers/base_signal_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from ..models.base_signal_model import BaseSignal
from django.utils import timezone

class BaseSignalSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, 
                          serializers.ModelSerializer):
    """
    Base serializer for all signal types with common fields and validation.
    """
    
    status_label = serializers.SerializerMethodField(read_only=True)
    source_contact_summary = serializers.SerializerMethodField(read_only=True)
    source_department_summary = serializers.SerializerMethodField(read_only=True)
    merged_from_signals_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = BaseSignal
        fields = [
            'id', 
            'account', 
            'value',
            'status', 'status_label',
            'source',
            'source_contact', 'source_contact_summary',
            'source_department', 'source_department_summary',
            'confirmation_count',
            'last_confirmed_at',
            'merged_into',
            'merged_from_signals_count',
            'metadata',
            'created_at', 'updated_at', 
            'created_by', 'updated_by'
        ]
        read_only_fields = [
            'id', 'confirmation_count', 'last_confirmed_at',
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'status_label', 'source_contact_summary', 'source_department_summary',
            'merged_from_signals_count'
        ]
    
    def get_status_label(self, obj):
        """Get human-readable status name"""
        return obj.get_status_display()
    
    def get_source_contact_summary(self, obj):
        """Get simplified contact information"""
        if obj.source_contact:
            return {
                'id': obj.source_contact.id,
                'name': f"{getattr(obj.source_contact, 'first_name', '')} {getattr(obj.source_contact, 'last_name', '')}".strip(),
                'role': getattr(obj.source_contact, 'job_title', None)
            }
        return None
    
    def get_source_department_summary(self, obj):
        """Get simplified department information"""
        if obj.source_department:
            return {
                'id': obj.source_department.id,
                'name': getattr(obj.source_department, 'name', ''),
                'display_name': getattr(obj.source_department, 'get_name_display', lambda: '')()
            }
        return None
    
    def get_merged_from_signals_count(self, obj):
        """Count signals that have been merged into this one"""
        if not obj.pk:
            return 0
        return obj.merged_from_signals.count() if hasattr(obj, 'merged_from_signals') else 0
    
    def validate(self, data):
        """Common validation for all signal types"""
        data = super().validate(data)
        
        # Validate source_contact belongs to account if provided
        account = data.get('account')
        if account:
            source_contact = data.get('source_contact')
            if source_contact and hasattr(source_contact, 'account') and source_contact.account.id != account.id:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_FIELD: "Source contact must belong to the specified account"
                })
        
        # Validate client scope for related entities
        client_id = self._get_client_id_from_context()
        
        source_contact = data.get('source_contact')
        if source_contact and hasattr(source_contact, 'client_id') and str(source_contact.client_id) != str(client_id):
            raise StandardizedValidationError({
                'source_contact': CoreErrorMessages.CLIENT_MISMATCH
            })
        
        
        return data
    
    def can_be_merged_with(self, target_signal):
        """
        Check if this signal can be merged with the target signal.
        
        Args:
            target_signal: Signal to merge into
            
        Returns:
            bool: True if signals can be merged, False otherwise
        """
        # Signals must have the same account
        if self.account_id != target_signal.account_id:
            return False
            
        # Signals must be of the same type
        if self.__class__ != target_signal.__class__:
            return False
            
        # Check field_name match if both have field_name
        if hasattr(self, 'field_name') and hasattr(target_signal, 'field_name'):
            if self.field_name != target_signal.field_name:
                return False
                
        # Signals must have appropriate status
        if self.status == self.Status.MERGED:
            return False
            
        if target_signal.status != self.Status.APPROVED:
            return False
            
        return True
    
    def mark_as_merged(self, target_signal, user=None):
        """
        Mark this signal as merged into the target signal.
        
        Args:
            target_signal: Signal this one was merged into
            user: User who performed the merge
            
        Returns:
            None
        """
        self.status = self.Status.MERGED
        self.merged_into = target_signal
        self.save(user=user)
        
    def add_merge_history(self, source_signal, user=None):
        """
        Add a merge history record for a signal that was merged into this one.
        
        Args:
            source_signal: Signal that was merged into this one
            user: User who performed the merge
            
        Returns:
            None
        """
        if not self.metadata:
            self.metadata = {}
            
        if 'merge_history' not in self.metadata:
            self.metadata['merge_history'] = []
            
        # Add merge record
        self.metadata['merge_history'].append({
            'merged_signal_id': str(source_signal.id),
            'field_name': getattr(source_signal, 'field_name', None),
            'timestamp': timezone.now().isoformat(),
            'merged_by': str(user.id) if user else None,
            'confirmations_added': source_signal.confirmation_count
        })