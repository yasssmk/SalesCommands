from django.db import models
from core.models import BaseModel, ContactDetailsMixin
from django.utils.translation import gettext_lazy as _

class Contact(BaseModel, ContactDetailsMixin):
    """
    Contact model representing individuals associated with accounts.
    """
    first_name = models.CharField(max_length=50, verbose_name=_('First Name'))
    last_name = models.CharField(max_length=50, verbose_name=_('Last Name'))
    job_title = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Job Title'))
    
    account = models.ForeignKey('account.Account', on_delete=models.SET_NULL, related_name='contacts', blank=True, null=True, verbose_name=_('Associated Account'))

    class Meta:
        db_table = 'contacts'
        verbose_name = _('Contact')
        verbose_name_plural = _('Contacts')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.job_title if self.job_title else 'No Title'})"
