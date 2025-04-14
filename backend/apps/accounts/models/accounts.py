# apps/account/models/account.py

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.models import ContactDetailsMixin
from apps.core_apps.models import BaseModelApp,  HistoricalTrackingModel
from core.client_scope import ClientScopeManager
from core.error_messages import AccountErrorMessages, CoreErrorMessages
from core.exceptions import StandardizedValidationError
from end_users.models import User, Team
from apps.signals.services import SignalDataService
from apps.signals.models import SignalAwareMixin, SignalEnabledQualificationMixin

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

class Account(BaseModelApp, ClientScopeManager.ModelMixin, ContactDetailsMixin):
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

    has_buying_decision = models.BooleanField(
        default=True,
        verbose_name=_('Has Buying Decision'),
        help_text=_('Indicates if this account has authority to make buying decisions')
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
    
    partners = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='partnered_with',
        blank=True,
        verbose_name=_('Partners')
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
    
    def validate_partner(self, partner):
        """
        Validate that a partner has the correct type.
        To be called before adding a partner relationship.
        
        Args:
            partner: Account to validate as a partner
            
        Returns:
            bool: Whether the partner is valid
            
        Raises:
            StandardizedValidationError: If partner validation fails
        """
        if partner.type != AccountType.PARTNER:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD,
                detail="partners"
            )
        return True
        
    def add_partner(self, partner, user=None):
        """
        Add a partner to this account with validation.
        
        Args:
            partner: Account to add as a partner
            user: User making the change
            
        Returns:
            bool: Whether the partner was added successfully
        """
        # Validate the partner
        if not self.validate_partner(partner):
            return False
            
        # Add the partner
        self.partners.add(partner)
        
        # Track the change
        old_partners = list(self.partners.all().values_list('id', flat=True))
        new_partners = old_partners + [partner.id]
        
        # Track the change if historical tracking is supported
        if hasattr(self, 'track_field_change'):
            self.track_field_change('partners', old_partners, new_partners, user)
            
        return True
        
    def remove_partner(self, partner, user=None):
        """
        Remove a partner from this account.
        
        Args:
            partner: Account to remove as a partner
            user: User making the change
            
        Returns:
            bool: Whether the partner was removed successfully
        """
        if partner not in self.partners.all():
            return False
            
        # Get partners before removal
        old_partners = list(self.partners.all().values_list('id', flat=True))
        
        # Remove the partner
        self.partners.remove(partner)
        
        # Get partners after removal
        new_partners = list(self.partners.all().values_list('id', flat=True))
        
        # Track the change if historical tracking is supported
        if hasattr(self, 'track_field_change'):
            self.track_field_change('partners', old_partners, new_partners, user)
            
        return True
    
    def update_profile_fields_from_signals(self):
        """
        Update the company_size and annual_revenue fields from profile signals.
        Called during save to ensure the fields are always up-to-date.
        """
        # Only proceed if we have an ID (not a new account)
        if not self.pk:
            return
            
        # Get profile data from signals
        profile_data = SignalDataService.get_account_profile_data(self)
        
        # Update company_size if it exists in signals
        if 'company_size' in profile_data:
            signal_value = profile_data['company_size']['value']
            # If value is a number, convert it to string
            if isinstance(signal_value, (int, float)):
                self.company_size = str(signal_value)
            else:
                self.company_size = signal_value
                
        # Update annual_revenue if it exists in signals
        if 'annual_revenue' in profile_data:
            signal_value = profile_data['annual_revenue']['value']
            # If value is a number, convert it to string
            if isinstance(signal_value, (int, float)):
                self.annual_revenue = str(signal_value)
            else:
                self.annual_revenue = signal_value
    
    def get_profile_data(self, include_signal_info=False):
        """
        Get profile data for this account from signals.
        
        Args:
            include_signal_info: Whether to include detailed signal information
            
        Returns:
            dict: Profile data from signals
        """
        return SignalDataService.get_account_profile_data(
            account=self,
            include_signal_info=include_signal_info
        )
    
    def get_qualification_data(self, field_names=None, department=None, 
                           source_contact=None, min_confirmations=None,
                           include_signal_info=False):
        """
        Get qualification data for this account from signals.
        
        Args:
            field_names: Optional list of specific fields to retrieve
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum number of confirmations required
            include_signal_info: Whether to include signal metadata
            
        Returns:
            dict: Qualification data from signals
        """
        return SignalDataService.get_account_qualification_data(
            account=self,
            field_names=field_names,
            department=department,
            source_contact=source_contact,
            min_confirmations=min_confirmations,
            include_signal_info=include_signal_info
        )
    
    def get_qualification_by_department(self):
        """
        Get qualification data organized by department.
        
        Returns:
            dict: Qualification data organized by department
        """
        from apps.signals.models.qualification_signal_model import QualificationSignal
        
        return SignalDataService.get_by_department(
            account=self,
            signal_type=QualificationSignal
        )
    
    def get_tech_stacks_data(self, department=None, source_contact=None,
                         min_confirmations=None, include_signal_info=False):
        """
        Get tech stack data for this account.
        
        Args:
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum number of confirmations required
            include_signal_info: Whether to include signal metadata
            
        Returns:
            dict: Tech stack data from signals
        """
        return SignalDataService.get_tech_stack_data(
            account=self,
            department=department,
            source_contact=source_contact,
            min_confirmations=min_confirmations,
            include_signal_info=include_signal_info
        )