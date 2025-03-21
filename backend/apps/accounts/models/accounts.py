# apps/account/models/account.py

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.models import ContactDetailsMixin
from apps.core_apps.models import BaseModelApp, SignalAwareMixin, SignalEnabledQualificationMixin
from core.client_scope import ClientScopeManager
from core.error_messages import AccountErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.models import HistoricalTrackingModel
from end_users.models import User, Team

# Personalization: Users could add new choices 
class AccountType(models.TextChoices):
    CLIENT = 'CLIENT', _('Client')
    PROSPECT = 'PROSPECT', _('Prospect')
    PARTNER = 'PARTNER', _('Partner')
    VENDOR = 'VENDOR', _('Vendor')
    OTHER = 'OTHER', _('Other')

class AccountClassification(models.TextChoices):
    SMB = 'SMB', _('Small and Medium Business')
    MIDMARKET = 'MIDMARKET', _('Mid-Market')
    ENTERPRISE = 'ENTERPRISE', _('Enterprise')
    STARTUP = 'STARTUP', _('Startup')
    NONPROFIT = 'NONPROFIT', _('Non-Profit')

class Account(BaseModelApp, ClientScopeManager.ModelMixin, ContactDetailsMixin, SignalAwareMixin, SignalEnabledQualificationMixin, HistoricalTrackingModel):
    """
    Represents a company account in the system.
    """
    company_name = models.CharField(
        max_length=255, 
        verbose_name=_('Company Name'),
    )

    industry = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name=_('Industry')
    )

    type = models.CharField(
        max_length=50, 
        choices=AccountType.choices, 
        blank=True, 
        null=True, 
        verbose_name=_('Account Type')
    )
    
    classification = models.CharField(
        max_length=50, 
        choices=AccountClassification.choices, 
        blank=True, 
        null=True, 
        verbose_name=_('Account Classification')
    )
    
    company_size = models.CharField(
        blank=True, 
        null=True, 
        verbose_name=_('Number of Employees')
    )
    
    annual_revenue = models.CharField(
        blank=True, 
        null=True, 
        verbose_name=_('Annual Revenue')
    )

    objectives = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name=_('Objectives')
    )
    
    compelling_events = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name=_('Compelling Events')
    )
    
    motivations = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name=_('Motivations')
    )
    
    key_kpis = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name=_('Key KPIs')
    )
    
    criteria = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name=_('Criteria')
    )
    
    pain_points = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name=_('Pain Points')
    )
    
    implications = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name=_('Implications')
    )
    
    # Coverage statistics
    coverage_stats = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name=_('Coverage Statistics')
    )

    # Relationships   
    parent_company = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        related_name='direct_child_companies', 
        blank=True, 
        null=True, 
        verbose_name=_('Parent Company')
    )
    
    account_owner = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, verbose_name=_('Account Owner'))
    team_owner = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True, verbose_name=_('Team Owner'))

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['company_name', 'city', 'country'],
        index_fields=['company_name']
    )):
        db_table = 'company_accounts'
        verbose_name = _('Account')
        verbose_name_plural = _('Accounts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account_owner'], name='acc_new_owner_idx'),
            models.Index(fields=['team_owner'], name='acc_new_team_idx'),
        ]
    
    def clean(self):
        """Validate the model"""
        super().clean()
        
        # Ensure account_owner user belongs to team_owner if both are set
        if self.account_owner and self.team_owner:
            if self.account_owner.team != self.team_owner:
                raise StandardizedValidationError(AccountErrorMessages.TEAM_MISMATCH, field_name="account_owner")

    def save(self, *args, **kwargs):
        # If account_owner is set but team isn't, automatically set the team
        if self.account_owner and not self.team_owner:
            self.team_owner = self.account_owner.team
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_name} ({self.get_type_display() if self.type else 'Unknown'})"

    def get_full_hierarchy(self):
        """Retrieve the full hierarchy of parent and child companies."""
        hierarchy = {
            'parents': [],
            'children': list(self.direct_child_companies.all())
        }
        
        current = self
        while current.parent_company:
            hierarchy['parents'].append(current.parent_company)
            current = current.parent_company
        
        return hierarchy
    
    @staticmethod
    def get_account_types():
        return [{'value': choice[0], 'label': choice[1]} for choice in AccountType.choices]

    @staticmethod
    def get_account_classifications():
        return [{'value': choice[0], 'label': choice[1]} for choice in AccountClassification.choices]
    
    def update_qualification_field(self, field_name, new_value, user, signal=None):
        """
        Enhanced update method for qualification fields that tracks signal information
        
        Args:
            field_name (str): Field name to update
            new_value: New value for the field
            user (User): User making the update
            signal (Signal, optional): Signal driving this update
        """
        # Get current value
        current_value = getattr(self, field_name)
        
        # Update the field
        setattr(self, field_name, new_value)
        
        # Initialize historical_data if it doesn't exist
        if not self.historical_data:
            self.historical_data = {}
        
        # Initialize field history if it doesn't exist
        if field_name not in self.historical_data:
            self.historical_data[field_name] = []
        
        # Create history entry
        history_entry = {
            'old_value': current_value,
            'new_value': new_value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None,
        }
        
        # Add signal data if provided
        if signal:
            history_entry.update({
                'source': 'signal',
                'signal_id': str(signal.id),
                'signal_category': signal.category,
                'signal_confidence': signal.confidence,
                'confirmation_count': signal.confirmation_count
            })
            
            # Also track in signal_metadata
            self.track_signal_update(signal, field_name, current_value, new_value)
        
        # Add to historical data
        self.historical_data[field_name].append(history_entry)
        
        # Save the model
        self.save(user=user)
        
        return True

    def get_qualification_data(self, include_signal_info=False):
        """Get all qualification data with optional signal information."""
        qualification_fields = [
            'objectives', 'compelling_events', 'motivations', 
            'key_kpis', 'criteria', 'pain_points', 'implications', 
        ]
        
        return self._get_field_data_with_signals(qualification_fields, include_signal_info)