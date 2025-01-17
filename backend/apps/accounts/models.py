from django.db import models
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField
from core.models import BaseModel, ContactDetailsMixin
from django.utils.translation import gettext_lazy as _


# Personalization: Users could add new choices 
class AccountType(models.TextChoices):
    CLIENT = 'CLIENT', _('Client')
    PROSPECT = 'PROSPECT', _('Prospect')
    PARTNER = 'PARTNER', _('Partner')
    VENDOR = 'VENDOR', _('Vendor')
    OTHER = 'OTHER', _('Other')

class AccountClassification(models.TextChoices):
    SMB = 'SMB', _('Small and Medium Business')
    ENTERPRISE = 'ENTERPRISE', _('Enterprise')
    STARTUP = 'STARTUP', _('Startup')
    NONPROFIT = 'NONPROFIT', _('Non-Profit')

class Account(BaseModel, ContactDetailsMixin):

    company_name = models.CharField(max_length=255, verbose_name=_('Company Name'))
    industry = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Industry'))

    type = models.CharField(max_length=50, choices=AccountType.choices, blank=True, null=True, verbose_name=_('Account Type'))
    classification = models.CharField(max_length=50, choices=AccountClassification.choices, blank=True, null=True, verbose_name=_('Account Classification'))
    
    number_of_employees = models.CharField(blank=True, null=True, verbose_name=_('Number of Employees'))
    potential = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True, verbose_name=_('Potential Revenue'))
    
    parent_company = models.ForeignKey('self', on_delete=models.SET_NULL, related_name='direct_child_companies', blank=True, null=True, verbose_name=_('Parent Company'))

    # Basic Information
    # company_name = models.CharField(
    #     max_length=255, 
    #     verbose_name=_('Company Name')
    # )
    # industry = models.CharField(
    #     max_length=100, 
    #     blank=True, 
    #     null=True, 
    #     verbose_name=_('Industry')
    # )
    # address = models.TextField(
    #     blank=True, 
    #     null=True, 
    #     verbose_name=_('Address')
    # )
    # city = models.CharField(
    #     max_length=50, 
    #     verbose_name=_('City')
    # )
    # post_code = models.CharField(
    #     max_length=20, 
    #     blank=True, 
    #     null=True, 
    #     verbose_name=_('Post Code')
    # )
    # country = models.CharField(
    #     max_length=50, 
    #     verbose_name=_('Country')
    # )
    # website = models.URLField(
    #     blank=True, 
    #     null=True, 
    #     verbose_name=_('Website')
    # )
    # type = models.CharField(
    #     max_length=50, 
    #     choices=AccountType.choices, 
    #     blank=True, 
    #     null=True, 
    #     verbose_name=_('Account Type')
    # )
    # phone_number = PhoneNumberField(
    #     max_length=20,
    #     blank=True, 
    #     null=True, 
    #     verbose_name=_('Phone Number')
    # )
    
    # # Timestamps
    # created_at = models.DateTimeField(auto_now_add=True)
    # updated_at = models.DateTimeField(auto_now=True)

    # # Segmentation
    # number_of_employees = models.CharField(
    #     blank=True, 
    #     null=True, 
    #     verbose_name=_('Number of Employees')
    # )
    # potential = models.DecimalField(
    #     max_digits=15,
    #     decimal_places=2,
    #     blank=True,
    #     null=True,
    #     verbose_name=_('Potential Revenue')
    # )
    # classification = models.CharField(
    #     max_length=50,
    #     choices=AccountClassification.choices,
    #     blank=True,
    #     null=True,
    #     verbose_name=_('Account Classification')
    # )

    # # Parent-Child Relationship
    # parent_company = models.ForeignKey(
    #     'self',
    #     on_delete=models.SET_NULL,
    #     related_name='direct_child_companies',
    #     blank=True,
    #     null=True,
    #     verbose_name=_('Parent Company')
    # )

    class Meta:
        db_table = 'company_accounts'
        # unique_together = ('company_name', 'city', 'country')
        verbose_name = _('Account')
        verbose_name_plural = _('Accounts')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} ({self.get_type_display()})"

    def get_full_hierarchy(self):
        """
        Retrieve the full hierarchy of parent and child companies.
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
    
    @staticmethod
    def get_account_types():
        return [{'value': choice[0], 'label': choice[1]} for choice in AccountType.choices]

    @staticmethod
    def get_account_classifications():
        return [{'value': choice[0], 'label': choice[1]} for choice in AccountClassification.choices]
