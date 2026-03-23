# app_modules/accounts/models.py
"""
CompanyAccount model for Administration module.

This is the new UUID-based Account model, separate from legacy apps.accounts.Account.
Follows the exact same patterns as the legacy model.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from ..core_modules.models import ModuleBaseModel
from core.models import ContactDetailsMixin
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from end_users.models import User
from core.constants import INDUSTRIES, COUNTRIES
from apps.signals.services import SignalDataService # A MODIFIER UNE FOIS CREER AVEC SIGNALS DANS APP_MODULE


class AccountType(models.TextChoices):
    """Account type choices."""
    CLIENT = 'CLIENT', _('Client')
    PROSPECT = 'PROSPECT', _('Prospect')
    PARTNER = 'PARTNER', _('Partner')
    VENDOR = 'VENDOR', _('Vendor')
    OTHER = 'OTHER', _('Other')


class AccountClassification(models.TextChoices):
    """Account classification choices."""
    SMB = 'SMB', _('Small and Medium Business')
    MIDMARKET = 'MIDMARKET', _('Mid-Market')
    ENTERPRISE = 'ENTERPRISE', _('Enterprise')
    STARTUP = 'STARTUP', _('Startup')
    NONPROFIT = 'NONPROFIT', _('Non-Profit')


class CompanyAccount(ModuleBaseModel, ClientScopeManager.ModelMixin, ContactDetailsMixin):
    """
    Company Account model for Administration.
    
    Represents a company/organization that the client is tracking.
    Uses UUID primary key for consistency with end_users models.
    
    Features:
        - Parent/child hierarchy support
        - Partner relationships (M2M)
        - Account ownership (user & team)
        - Contact details via ContactDetailsMixin
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """
    
    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================
    
    company_name = models.CharField(
        max_length=255,
        verbose_name=_('Company Name')
    )
    
    industry = models.CharField(
        max_length=100,
        choices=INDUSTRIES,
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
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Number of Employees')
    )
    
    annual_revenue = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Annual Revenue')
    )
    
    has_buying_decision = models.BooleanField(
        default=True,
        verbose_name=_('Has Buying Decision'),
        help_text=_('Indicates if this account has authority to make buying decisions')
    )
    
    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================
    
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
    
    # ==========================================================================
    # OWNERSHIP
    # ==========================================================================
    
    account_owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='owned_company_accounts',
        verbose_name=_('Account Owner')
    )
    
    # ==========================================================================
    # META
    # ==========================================================================
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['company_name', 'city', 'country'],
        index_fields=['company_name']
    )):
        db_table = 'module_company_accounts'
        verbose_name = _('Company Account')
        verbose_name_plural = _('Company Accounts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account_owner'], name='mod_acc_owner_idx'),
            models.Index(fields=['type'], name='mod_acc_type_idx'),
        ]
    
    def __str__(self):
        type_display = self.get_type_display() if self.type else 'Unknown'
        return f"{self.company_name} ({type_display})"
    
     # ==========================================================================
    # PROPERTIES
    # ==========================================================================
    
    @property
    def team(self):
        """Get team from account_owner. Team is derived, not stored."""
        return self.account_owner.team if self.account_owner else None
    
    @property
    def team_id(self):
        """Get team_id from account_owner for filtering compatibility."""
        return self.account_owner.team_id if self.account_owner else None
    
    # ==========================================================================
    # VALIDATION
    # ==========================================================================
    
    def clean(self):
        """Validate the model."""
        super().clean()
        
    
    def save(self, *args, **kwargs):
        """Override save to handle audit fields."""
        super().save(*args, **kwargs)
    
    # ==========================================================================
    # HIERARCHY METHODS
    # ==========================================================================
    
    def get_full_hierarchy(self):
        """
        Retrieve the full hierarchy of parent and child companies.
        
        Returns:
            dict: {
                'parents': [list of parent accounts up the chain],
                'children': [list of direct child accounts]
            }
        """
        hierarchy = {
            'parents': [],
            'children': list(self.direct_child_companies.all())
        }
        
        current = self
        while current.parent_company:
            hierarchy['parents'].append(current.parent_company)
            current = current.parent_company
        
        return hierarchy
    
    # ==========================================================================
    # PARTNER METHODS
    # ==========================================================================
    
    def validate_partner(self, partner):
        """
        Validate that a partner has the correct type.
        
        Args:
            partner: CompanyAccount to validate as a partner
            
        Returns:
            bool: Whether the partner is valid
            
        Raises:
            StandardizedValidationError: If partner validation fails
        """
        if partner.type != AccountType.PARTNER:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD,
                detail="Partner must have type 'PARTNER'"
            )
        return True
    
    def add_partner(self, partner, user=None):
        """
        Add a partner to this account with validation.
        
        Args:
            partner: CompanyAccount to add as a partner
            user: User making the change (for audit)
            
        Returns:
            bool: Whether the partner was added successfully
        """
        self.validate_partner(partner)
        self.partners.add(partner)
        return True
    
    def remove_partner(self, partner, user=None):
        """
        Remove a partner from this account.
        
        Args:
            partner: CompanyAccount to remove as a partner
            user: User making the change (for audit)
            
        Returns:
            bool: Whether the partner was removed successfully
        """
        if partner not in self.partners.all():
            return False
        
        self.partners.remove(partner)
        return True
    
    # ==========================================================================
    # SIGNALS METHODS
    # ==========================================================================

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
    
    def get_profile_data(self):
        """
        Get profile data for this account from signals.
            
        Returns:
            dict: Profile data from signals
        """
        # return SignalDataService.get_account_profile_data(
        #     account=self,
        # )
    
        return None
    
    def get_qualification_data(self, field_names=None, department=None, 
                           source_contact=None, min_confirmations=None):
        """
        Get qualification data for this account from signals.
        
        Args:
            field_names: Optional list of specific fields to retrieve
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum number of confirmations required
            
        Returns:
            dict: Qualification data from signals
        """
        # return SignalDataService.get_account_qualification_data(
        #     account=self,
        #     field_names=field_names,
        #     department=department,
        #     source_contact=source_contact,
        #     min_confirmations=min_confirmations,
        # )
    
        return None
    
    def get_qualification_by_department(self):
        """
        Get qualification data organized by department.
        
        Returns:
            dict: Qualification data organized by department
        """
        # from apps.signals.models.qualification_signal_model import QualificationSignal
        
        # return SignalDataService.get_by_department(
        #     account=self,
        #     signal_type=QualificationSignal
        # )

        return None
    
    def get_tech_stacks_data(self, department=None, source_contact=None,
                         min_confirmations=None):
        """
        Get tech stack data for this account.
        
        Args:
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum number of confirmations required
            
        Returns:
            dict: Tech stack data from signals
        """
        # return SignalDataService.get_tech_stack_data(
        #     account=self,
        #     department=department,
        #     source_contact=source_contact,
        #     min_confirmations=min_confirmations,
        # )
    
        return None
    
    # ==========================================================================
    # STATIC METHODS
    # ==========================================================================
    
    @staticmethod
    def get_account_types():
        """Return account type choices for frontend."""
        return [
            {'value': choice[0], 'label': choice[1]}
            for choice in AccountType.choices
        ]
    
    @staticmethod
    def get_account_classifications():
        """Return account classification choices for frontend."""
        return [
            {'value': choice[0], 'label': choice[1]}
            for choice in AccountClassification.choices
        ]
    
    @staticmethod
    def get_industries():
        """Return industry choices for frontend."""
        return [
            {'value': choice[0], 'label': str(choice[1])}
            for choice in INDUSTRIES
        ]
    
    @staticmethod
    def get_countries():
        """Return country choices for frontend."""
        return [
            {'value': choice[0], 'label': f"{choice[1]} ({choice[0]})"}
            for choice in COUNTRIES
        ]