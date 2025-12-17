# app_modules/contacts/models.py
"""
Contact model for Contacts module.

Represents a contact person linked to a CompanyAccount.
Uses UUID primary key and follows ModuleBaseModel patterns.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from app_modules.core_modules.models.moduleBaseModels import ModuleBaseModel
from core.models import ContactDetailsMixin
from core.client_scope import ClientScopeManager


class InfluenceLevel(models.TextChoices):
    """Influence level choices for contacts."""
    DECISION_MAKER = 'DECISION_MAKER', _('Decision Maker')
    INFLUENCER = 'INFLUENCER', _('Influencer')
    CHAMPION = 'CHAMPION', _('Champion')
    USER = 'USER', _('User')
    GATEKEEPER = 'GATEKEEPER', _('Gatekeeper')
    BLOCKER = 'BLOCKER', _('Blocker')
    UNKNOWN = 'UNKNOWN', _('Unknown')


class Contact(ModuleBaseModel, ClientScopeManager.ModelMixin, ContactDetailsMixin):
    """
    Contact model for Contacts module.
    
    Represents a contact person at a company account.
    Uses UUID primary key for consistency with app_modules models.
    
    Features:
        - Linked to CompanyAccount (required)
        - Contact details via ContactDetailsMixin (email, phone, address, linkedin)
        - Influence level tracking for sales qualification
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """
    
    # ==========================================================================
    # ACCOUNT RELATIONSHIP
    # ==========================================================================
    
    account = models.ForeignKey(
        'module_accounts.CompanyAccount',
        on_delete=models.CASCADE,
        related_name='contacts',
        verbose_name=_('Account'),
        help_text=_('The company account this contact belongs to')
    )
    
    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================
    
    first_name = models.CharField(
        max_length=100,
        verbose_name=_('First Name')
    )
    
    last_name = models.CharField(
        max_length=100,
        verbose_name=_('Last Name')
    )
    
    job_title = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_('Job Title')
    )
    
    department = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_('Department')
    )
    
    standard_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='module_contacts',
        verbose_name=_('Standard Department')
    )
    
    # ==========================================================================
    # QUALIFICATION FIELDS
    # ==========================================================================
    
    influence_level = models.CharField(
        max_length=50,
        choices=InfluenceLevel.choices,
        default=InfluenceLevel.UNKNOWN,
        verbose_name=_('Influence Level')
    )
    
    has_buying_authority = models.BooleanField(
        blank=True,
        null=True,
        verbose_name=_('Has Buying Authority')
    )
    
    # ==========================================================================
    # COMMUNICATION PREFERENCES
    # ==========================================================================
    
    opted_out = models.BooleanField(
        default=False,
        verbose_name=_('Opted Out'),
        help_text=_('Whether the contact has opted out of communications')
    )
    
    # ==========================================================================
    # ADDITIONAL FIELDS
    # ==========================================================================
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    # ==========================================================================
    # META & METHODS
    # ==========================================================================
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'email'],
        index_fields=['first_name', 'last_name']
    )):
        db_table = 'module_contacts'
        verbose_name = _('Contact')
        verbose_name_plural = _('Contacts')
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        """Get the contact's full name."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def department_name(self):
        """Get department name from standard_department if available."""
        if self.standard_department:
            return self.standard_department.get_name_display()
        return self.department
    
    def mark_email_invalid(self, user=None):
        """Mark contact email as invalid."""
        self.email_is_valid = False
        self.save(user=user)
        return self
    
    def mark_phone_invalid(self, user=None):
        """Mark contact phone as invalid."""
        self.phone_is_valid = False
        self.save(user=user)
        return self
    
    def mark_opted_out(self, user=None):
        """Mark contact as opted out of communications."""
        self.opted_out = True
        self.save(user=user)
        return self