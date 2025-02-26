from django.db import models
from django.utils import timezone
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from apps.accounts_app.contacts.models import Contact
from apps.accounts_app.account_product_detail.models import AccountProductDetail

from apps.accounts_app.org_units.models import AccountOrganizationUnit

class Signal(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Signal model that tracks changes in key entities and attributes.
    """

    class EntityType(models.TextChoices):
        ACCOUNT = "account", "Account"
        ORG_UNIT = "org_unit", "Organization Unit"
        CONTACT = "contact", "Contact"
        APD = "account_product_detail", "Account-Product Detail"
        # Add more as needed

    class SignalStatus(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        DORMANT = "dormant", "Dormant"

    class Confidence(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    entity_type = models.CharField(
        max_length=50, 
        choices=EntityType.choices, 
        verbose_name="Entity Type"
    )

    field_name = models.CharField(max_length=100, verbose_name="Field Name")
    value = models.JSONField(blank=True, null=True, verbose_name="Signal Value")

    signal_type = models.CharField(max_length=50, default="CUMULATIVE")  # or use choices
    confidence = models.CharField(
        max_length=10, 
        choices=Confidence.choices, 
        default=Confidence.MEDIUM
    )

    status = models.CharField(
        max_length=20, 
        choices=SignalStatus.choices, 
        default=SignalStatus.OPEN
    )

    source = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    revisit_date = models.DateTimeField(blank=True, null=True)
    resolved_date = models.DateTimeField(blank=True, null=True)

    # ForeignKey fields dynamically assigned based on entity type
    org_unit = models.ForeignKey(
        AccountOrganizationUnit,
        on_delete=models.CASCADE,
        related_name='signals',
        null=True, blank=True,
        verbose_name=_("Linked Org Unit")
    )

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='signals',
        null=True, blank=True,
        verbose_name=_("Linked Contact")
    )

    account_product_detail = models.ForeignKey(
        AccountProductDetail,
        on_delete=models.CASCADE,
        related_name='signals',
        null=True, blank=True,
        verbose_name=_("Linked Account-Product Detail")
    )

    def __str__(self):
        return f"{self.entity_type} - {self.field_name} [{self.signal_type}]"

    def save(self, *args, **kwargs):
        """
        Enforce ForeignKey constraint dynamically based on entity_type.
        Ensure only the correct ForeignKey field is populated.
        """
        entity_map = {
            self.EntityType.ACCOUNT: self.account,  
            self.EntityType.ORG_UNIT: self.org_unit,
            self.EntityType.CONTACT: self.contact,
            self.EntityType.APD: self.account_product_detail,
        }

        # Ensure only one ForeignKey is filled
        for entity, value in entity_map.items():
            if entity == self.entity_type and not value:
                raise ValueError(f"Signal must be linked to a {entity}")

        super().save(*args, **kwargs)
