# apps/account/models/contact.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from apps.core_apps.models import BaseModelApp, AccountLinkedModel, HistoricalTrackingModel, SignalEnabledQualificationMixin, SignalAwareMixin
from core.client_scope import ClientScopeManager
from core.models import ContactDetailsMixin

class InfluenceLevel(models.TextChoices):
    DECISION_MAKER = 'DECISION_MAKER', _('Decision Maker')
    INFLUENCER = 'INFLUENCER', _('Influencer')
    CHAMPION = 'CHAMPION', _('Champion')
    USER = 'USER', _('User')
    GATEKEEPER = 'GATEKEEPER', _('Gatekeeper')
    BLOCKER = 'BLOCKER', _('Blocker')
    UNKNOWN = 'UNKNOWN', _('Unknown')

class Contact(BaseModelApp, AccountLinkedModel, HistoricalTrackingModel, ContactDetailsMixin, 
              SignalEnabledQualificationMixin, SignalAwareMixin, ClientScopeManager.ModelMixin):
    """
    Represents a contact person at an account.
    """
    # Basic contact information
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
    
    influence_level = models.CharField(
        max_length=50,
        choices=InfluenceLevel.choices,
        default=InfluenceLevel.UNKNOWN,
        verbose_name=_('Influence Level')
    )
    
    # Personal qualification data
    objectives = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Personal Objectives')
    )
    
    pain_points = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Personal Pain Points')
    )
    
    criteria = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Decision Criteria')
    )
    
    buying_authority = models.BooleanField(
        default=False,
        verbose_name=_('Has Buying Authority')
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'email'],
        index_fields=['first_name', 'last_name']
    )):
        db_table = 'accounts_contacts'
        verbose_name = _('Contact')
        verbose_name_plural = _('Contacts')
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_profile_data(self, include_signal_info=False):
        """Get profile data with signals if requested"""
        profile_fields = [
            'first_name', 'last_name', 'job_title', 'influence_level',
            'email', 'phone', 'linkedin', 'department', 'buying_authority'
        ]
        return self._get_field_data_with_signals(profile_fields, include_signal_info, 'PROFILE')