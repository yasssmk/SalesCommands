from django.db import models
from django.utils.translation import gettext_lazy as _

class AccountLinkedModel(models.Model):
    """Base model for entities that need account tracking"""
    account = models.ForeignKey(
        'accounts_new.Account',
        on_delete=models.CASCADE,
        verbose_name=_('Account'),
        related_name='%(class)s_set_new'
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['account'])
        ]

    def save(self, *args, **kwargs):
        if self.account and not self.client_id:
            self.client_id = self.account.client_id
        super().save(*args, **kwargs)
