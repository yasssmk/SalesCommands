from django.db import models
from core.models import ContactDetailsMixin
from django.utils import timezone
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField
from apps.core_apps.models import BaseModelApp, AccountLinkedModel, SignalEnabledQualificationMixin, SignalAwareMixin
from apps.sales_insight.models import QualificationModel
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _

class Contact(BaseModelApp, ClientScopeManager.ModelMixin, AccountLinkedModel, QualificationModel, ContactDetailsMixin, SignalEnabledQualificationMixin, SignalAwareMixin):
    """
    Contact model representing individuals associated with accounts.
    """
    first_name = models.CharField(max_length=50, verbose_name=_('First Name'))
    last_name = models.CharField(max_length=50, verbose_name=_('Last Name'))
    job_title = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Job Title'))
    
    influence_level = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('Influence Level'))
    
    # Relationships
    organization_unit = models.ForeignKey(
        AccountOrganizationUnit,
        on_delete=models.SET_NULL,
        related_name='contacts',
        blank=True,
        null=True,
        verbose_name=_('Organization Unit')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'email'],
        index_fields=['first_name', 'last_name']
    )):
        verbose_name = _('Contact')
        verbose_name_plural = _('Contacts')
        db_table = 'contacts'
        ordering = ['-created_at', 'last_name', 'first_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_profile_data(self, include_signal_info=False):
        """Get profile data with signals if requested"""
        profile_fields = [
            'first_name', 'last_name', 'job_title', 'influence_level',
            'email', 'phone', 'linkedin'
        ]
        return self._get_field_data_with_signals(profile_fields, include_signal_info, 'PROFILE')