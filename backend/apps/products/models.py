from django.db import models
from django.conf import settings
from apps.core_apps.models import BaseModelApp,AccountLinkedModel
from apps.sales_insight.models import SalesInsight
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from core.error_messages import CoreErrorMessages
from apps.core_apps.models import StandardDepartment
from django.core.exceptions import ValidationError
from core.constants import CURRENCY
from core.exceptions import StandardizedValidationError, AuthenticationFailed, StandardizedPermissionDenied

class Product(BaseModelApp, ClientScopeManager.ModelMixin):


    product_name = models.CharField(
        max_length=255, 
        verbose_name=_('Product Name'),
    )


    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Marketing Description")
    )

    target_categories = models.ManyToManyField(
        StandardDepartment,
        blank=True,
        related_name="products_for_category",
        verbose_name=_("Standard Department Categories")
    )

    # AI & Sales Insights
    value_proposition = models.JSONField(blank=True, null=True, verbose_name=_("Value Proposition"))
    potential_cons = models.JSONField(blank=True, null=True, verbose_name=_("Potential Cons"))
    competitors = models.JSONField(blank=True, null=True, verbose_name=_("Most Frequent Competitors"))

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['product_name'],
        index_fields=[]
    )):
        db_table = 'products'
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ['product_name']

    def __str__(self):
        return f"{self.product_name}"

class BillingCycle(BaseModelApp, ClientScopeManager.ModelMixin):
    """Model to store available billing cycles for pricing"""
    
    class CycleType(models.TextChoices):
        MONTHLY = "MONTHLY", _("Monthly")
        QUARTERLY = "QUARTERLY", _("Quarterly")
        YEARLY = "YEARLY", _("Yearly")
        THREE_YEARS = "THREE_YEARS", _("3 Years")

    name = models.CharField(
        max_length=255,
        verbose_name=_("Cycle Name"),
        help_text=_("Unique name for this billing cycle offer")
    )

    cycle_type = models.CharField(
        max_length=20,
        choices=CycleType.choices,
        verbose_name=_("Cycle Type")
    )
    
    multiplier = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Price Multiplier"),
        help_text=_("Multiplier applied to base price (e.g., 0.9 for 10% discount)")
    )
    
    class Meta:
        db_table = "billing_cycles"
        verbose_name = _("Billing Cycle")
        verbose_name_plural = _("Billing Cycles")
    
    def clean(self):
        """Ensure multiplier is within valid range."""
        super().clean
        if not (0 < self.multiplier <= 1):
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(
            field="Multiplier must be between 0 and 1"
        ))
           

    def __str__(self):
        return f"{self.get_cycle_type_display()} (x{self.multiplier})"

class Pricing(BaseModelApp, ClientScopeManager.ModelMixin):
    class PricingType(models.TextChoices):
        ASSET = "ASSET", _("Asset")
        SERVICE = "SERVICE", _("Service")
        SUBSCRIPTION = "SUBSCRIPTION", _("Subscription")
        USAGE = "USAGE", _("Usage")

    class BillingTerms(models.TextChoices):
        MONTHLY = "MONTHLY", _("Monthly")
        QUARTERLY = "QUARTERLY", _("Quarterly")
        YEARLY = "YEARLY", _("Yearly")
        THREE_YEARS = "THREE_YEARS", _("3 Years")

    class UnitOfMeasure(models.TextChoices):
        UNIT = "UNIT", _("Unit")
        SEAT = "SEAT", _("Seats")
        GB = "GB", _("GIGA BIT")
        MIN = "MIN", _("Minute")
        API_CALL = "API_CALL", _("API call")
        TOKEN = "TOKEN", _("Token")

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="pricing_models"
    )
    
    pricing_type = models.CharField(
        max_length=20,
        choices=PricingType.choices,
        verbose_name=_("Pricing Type")
    )

    unit_of_measure = models.CharField(
        max_length=20,
        default="UNIT",
        choices=UnitOfMeasure.choices,
        verbose_name=_("Unit of Measure")
    )

    units_per = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Units Per"),
        help_text=_("Number of base units per billing unit (e.g., 60 minutes per hour)")
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1,
        verbose_name=_("Unit Price")
    )

    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Base Price"),
        help_text=_("Flat fee charged before unit pricing")
    )

    billing_term = models.CharField(
        max_length=20,
        choices=BillingTerms.choices,
        verbose_name=_("Billing Term"),
        null=True,
        blank=True
    )

    currency = models.CharField(
        max_length=3,
        choices=CURRENCY,
        default="USD",
        verbose_name=_("Currency")
    )

    formula = models.TextField(blank=True)

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['product', 'pricing_type'],
        index_fields=['pricing_type']
    )):
        db_table = "product_pricing"
        verbose_name = _("Pricing")
        verbose_name_plural = _("Pricing Models")

    def clean(self):
        """Validate business rules for pricing types."""
        super().clean()

        # Validate billing term is required for subscription and usage pricing
        if self.pricing_type in [self.PricingType.SUBSCRIPTION, self.PricingType.USAGE] and not self.billing_term:
            raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(
                field="Billing term is required for subscription and usage pricing"
            ))

        # Validate billing term is not set for other pricing types
        if self.pricing_type not in [self.PricingType.SUBSCRIPTION, self.PricingType.USAGE] and self.billing_term:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(
                field="Billing term is not allowed for this pricing type"
            ))

    def __str__(self):
        return f"{self.product.product_name} - {self.pricing_type} - {self.base_price} {self.currency}"
      

from apps.core_apps.models import StandardDepartment

# class AccountProductTarget(models.Model):
#     """
#     Maps a product's general target (ProductTarget) to a specific account's organizational units.
#     This ensures that a product can target relevant departments within a client's company.
#     """
#     # product_target = models.ForeignKey(ProductTarget, on_delete=models.CASCADE, related_name="account_targets")
#     account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="product_targets")
#     org_unit = models.ForeignKey(AccountOrganizationUnit, on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Specific Organization Unit"))

#     # AI Mapping Fields
#     ai_mapping_confidence = models.FloatField(blank=True, null=True, verbose_name=_("AI Mapping Confidence Score"))
#     manually_validated = models.BooleanField(default=False, verbose_name=_("Manually Validated by User"))

#     class Meta:
#         db_table = "account_product_targets"
#         verbose_name = _("Account Product Target")
#         verbose_name_plural = _("Account Product Targets")

#     def __str__(self):
#         return f"{self.account.company_name} - {self.product_target.product.name} - {self.org_unit.name if self.org_unit else 'No Specific OrgUnit'}"