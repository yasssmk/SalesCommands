# apps/opportunities/models/opportunity.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from core.exceptions import StandardizedValidationError


class Opportunity(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Core opportunity entity with minimal essential fields.
    Related data is in separate models for separation of concerns.
    """
    
    class OpportunityStatus(models.TextChoices):
        OPEN = 'OPEN', _('Open')
        WON = 'WON', _('Won')
        LOST = 'LOST', _('Lost')
        PENDING = 'PENDING', _('Pending')
    
    class OpportunityType(models.TextChoices):
        NEW_BUSINESS = 'NEW_BUSINESS', _('New Business')
        EXISTING_CUSTOMER = 'EXISTING_CUSTOMER', _('Existing Customer')
        RENEWAL = 'RENEWAL', _('Renewal')
        UPGRADE = 'UPGRADE', _('Upgrade')
    
    # Basic Information
    title = models.CharField(
        max_length=200,
        verbose_name=_('Opportunity Title')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    # Type and Status
    opportunity_type = models.CharField(
        max_length=20,
        choices=OpportunityType.choices,
        default=OpportunityType.NEW_BUSINESS,
        verbose_name=_('Opportunity Type')
    )
    
    status = models.CharField(
        max_length=20,
        choices=OpportunityStatus.choices,
        default=OpportunityStatus.OPEN,
        verbose_name=_('Status')
    )
    
    # Primary Contact
    contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.CASCADE,
        related_name='opportunities',
        verbose_name=_('Primary Contact')
    )
    
    # Deal Owner
    deal_owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='owned_opportunities',
        null=True,
        verbose_name=_('Deal Owner')
    )
    
    # Important Dates
    date_open = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Date Opened')
    )
    
    expected_close_date = models.DateField(
        verbose_name=_('Expected Close Date')
    )
    
    closed_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Closed Date')
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'title'],
        index_fields=['status', 'deal_owner']
    )):
        db_table = 'opportunities'
        verbose_name = _('Opportunity')
        verbose_name_plural = _('Opportunities')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'status']),
            models.Index(fields=['opportunity_type']),
            models.Index(fields=['expected_close_date']),
            models.Index(fields=['closed_date']),
            models.Index(fields=['date_open']),
            # Composite index for common filtering scenarios
            models.Index(fields=['account', 'status', 'deal_owner'], name='opp_account_status_owner_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.account.company_name} ({self.get_status_display()})"
    
    def update_financials(self):
        """Update financial summary from line items"""
        if hasattr(self, 'financial_summary'):
            self.financial_summary.update_from_line_items()
    
    def mark_as_won(self, close_date=None):
        """Mark opportunity as won"""
        self.status = self.OpportunityStatus.WON
        self.closed_date = close_date or timezone.now().date()
        self.save(update_fields=['status', 'closed_date'])
        
        # Update related models
        if hasattr(self, 'sales_stage'):
            self.sales_stage.set_current_stage('CLOSED_WON')
        
        self.create_history_entry('STATUS_CHANGE', f"Marked as {self.get_status_display()}")
        return self
    
    def mark_as_lost(self, reason=None, close_date=None):
        """Mark opportunity as lost"""
        self.status = self.OpportunityStatus.LOST
        self.closed_date = close_date or timezone.now().date()
        
        if reason:
            if self.notes:
                self.notes += f"\n\nLost reason: {reason}"
            else:
                self.notes = f"Lost reason: {reason}"
        
        self.save(update_fields=['status', 'closed_date', 'notes'])
        
        # Update related models
        if hasattr(self, 'sales_stage'):
            self.sales_stage.set_current_stage('CLOSED_LOST')
        
        self.create_history_entry('STATUS_CHANGE', f"Marked as {self.get_status_display()}", details=reason)
        return self
    
    def create_history_entry(self, change_type, description, details=None):
        """Create a history entry for this opportunity"""
        from .opportunity_tracking import OpportunityHistory
        
        return OpportunityHistory.objects.create(
            opportunity=self,
            change_type=change_type,
            description=description,
            details=details
        )
    
    def get_days_open(self):
        """Calculate days the opportunity has been open"""
        if self.closed_date:
            delta = self.closed_date - self.date_open.date()
        else:
            delta = timezone.now().date() - self.date_open.date()
        return delta.days