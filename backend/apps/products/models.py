from django.db import models
from django.conf import settings
from apps.core_apps.models import BaseModelApp,AccountLinkedModel
from apps.sales_insight.models import SalesInsight
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit

class Product(BaseModelApp, ClientScopeManager.ModelMixin):

    class ProductType(models.TextChoices):
        REGULAR = "REGULAR", _("Physical or Digital Product")
        SERVICE = "SERVICE", _("Service-Based Offering")

    product_name = models.CharField(
        max_length=255, 
        verbose_name=_('Product Name'),
    )

    product_type = models.CharField(
        max_length=20, 
        choices=ProductType.choices, 
        verbose_name=_("Product Type")
    )

    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Marketing Description")
    )

    target_category = models.ForeignKey(StandardDepartment, on_delete=models.SET_NULL, blank=True, null=True, verbose_name=_("Standard Department Category"))

    # AI & Sales Insights
    value_proposition = models.JSONField(blank=True, null=True, verbose_name=_("Value Proposition"))
    potential_cons = models.JSONField(blank=True, null=True, verbose_name=_("Potential Cons"))
    competitors = models.JSONField(blank=True, null=True, verbose_name=_("Most Frequent Competitors"))

    class Meta:
        db_table = 'products'
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_product_type_display()})"

class BillingCycle(BaseModelApp, ClientScopeManager.ModelMixin):
    """Model to store available billing cycles for pricing"""
    
    class CycleType(models.TextChoices):
        MONTHLY = "MONTHLY", _("Monthly")
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

    def __str__(self):
        return f"{self.get_cycle_type_display()} (x{self.multiplier})"

class Pricing(BaseModelApp, ClientScopeManager.ModelMixin):
    class PricingType(models.TextChoices):
        ONE_TIME = "ONE_TIME", _("One-Time Fee")
        SUBSCRIPTION = "SUBSCRIPTION", _("Subscription")

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
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Base Price")
    )
    currency = models.CharField(
        max_length=10,
        default="USD",
        verbose_name=_("Currency")
    )
    available_cycles = models.ManyToManyField(
        BillingCycle,
        related_name="pricing_models",
        blank=True,
        verbose_name=_("Available Billing Cycles")
    )

    class Meta:
        db_table = "product_pricing"
        verbose_name = _("Pricing")
        verbose_name_plural = _("Pricing Models")

    def __str__(self):
        return f"{self.product.name} - {self.pricing_type} - {self.base_price} {self.currency}"
    

from apps.core_apps.models import StandardDepartment

class AccountProductTarget(models.Model):
    """
    Maps a product's general target (ProductTarget) to a specific account's organizational units.
    This ensures that a product can target relevant departments within a client's company.
    """
    # product_target = models.ForeignKey(ProductTarget, on_delete=models.CASCADE, related_name="account_targets")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="product_targets")
    org_unit = models.ForeignKey(AccountOrganizationUnit, on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Specific Organization Unit"))

    # AI Mapping Fields
    ai_mapping_confidence = models.FloatField(blank=True, null=True, verbose_name=_("AI Mapping Confidence Score"))
    manually_validated = models.BooleanField(default=False, verbose_name=_("Manually Validated by User"))

    class Meta:
        db_table = "account_product_targets"
        verbose_name = _("Account Product Target")
        verbose_name_plural = _("Account Product Targets")

    def __str__(self):
        return f"{self.account.company_name} - {self.product_target.product.name} - {self.org_unit.name if self.org_unit else 'No Specific OrgUnit'}"