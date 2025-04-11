# apps/signals/models/base_signal_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp, AccountLinkedModel


class BaseSignal(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Base signal model for tracking sales insights across different categories.
    This provides common functionality for all signal types.
    """
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        APPLIED = 'APPLIED', _('Applied')
        MERGED = 'MERGED', _('Merged')
    
    # Core field to store signal value
    value = models.JSONField(
        verbose_name=_('Signal Value')
    )
    
    # Status and lifecycle
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Signal Status')
    )
    
    # Source information
    source = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Data Source')
    )
    
    source_contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.SET_NULL,
        related_name='%(class)s_provided',
        null=True,
        blank=True,
        verbose_name=_('Source Contact')
    )
    
    source_department = models.ForeignKey(
        'core_apps.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='%(class)s_department',
        null=True,
        blank=True,
        verbose_name=_('Source Department')
    )
    
    # Tracking and confirmation
    confirmation_count = models.PositiveIntegerField(
        default=1, 
        verbose_name=_('Confirmation Count')
    )
    
    last_confirmed_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name=_('Last Confirmed At')
    )
    
    # Reference to merged signal
    merged_into = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='merged_from_signals',
        null=True,
        blank=True,
        verbose_name=_('Merged Into Signal')
    )
    
    # Approval tracking
    approved_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='%(class)s_approved',
        null=True,
        blank=True,
        verbose_name=_('Approved By')
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    
    # Additional metadata for flexible extensions
    metadata = models.JSONField(
        verbose_name=_('Metadata'),
        help_text=_('Additional metadata for validations, history, and context'),
        null=True,
        blank=True
    )

    class Meta:
        abstract = True
    
    def clean(self):
        """Basic validation common to all signals"""
        super().clean()
        
        # Set source department from contact if available and not set
        if self.source_contact and not self.source_department and hasattr(self.source_contact, 'standard_department'):
            self.source_department = self.source_contact.standard_department
    
    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        user = kwargs.pop('user', None)
        client_id = kwargs.pop('client_id', None)
        
        # Auto-approve manual entries
        if self.source == 'manual_entry' and self.status == self.Status.PENDING:
            self.status = self.Status.APPROVED
        
        # Let the parent classes handle the rest
        super().save(force_insert=force_insert, force_update=force_update, 
                    user=user, client_id=client_id, *args, **kwargs)
    
    def __str__(self):
        """String representation of the signal"""
        return f"Signal: {self.get_status_display()}"