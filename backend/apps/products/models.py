from django.db import models
from django.conf import settings
from apps.core_apps.models import BaseModelApp,AccountLinkedModel
from apps.sales_insight.models import SalesInsight
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _

class Product(BaseModelApp, ClientScopeManager.ModelMixin, AccountLinkedModel):

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

class Pricing(BaseModelApp, ClientScopeManager.ModelMixin, AccountLinkedModel):

    class PricingType(models.TextChoices):
        ONE_TIME = "ONE_TIME", _("One-Time Fee")
        SUBSCRIPTION = "SUBSCRIPTION", _("Subscription")

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="pricing_models")
    pricing_type = models.CharField(max_length=20, choices=PricingType.choices, verbose_name=_("Pricing Type"))
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Price"))
    currency = models.CharField(max_length=10, default="USD", verbose_name=_("Currency"))
    billing_cycle = models.CharField(
        max_length=20, blank=True, null=True,
        choices=[("MONTHLY", "Monthly"), ("YEARLY", "Yearly"), ("3 Years", "3 Years")], 
        verbose_name=_("Billing Cycle")
    )

    class Meta:
        db_table = "product_pricing"
        verbose_name = _("Pricing")
        verbose_name_plural = _("Pricing Models")

    def __str__(self):
        return f"{self.product.name} - {self.pricing_type} - {self.price} {self.currency}"

from apps.core_apps.models import StandardDepartment

class ProductTarget(BaseModelApp, ClientScopeManager.ModelMixin, AccountLinkedModel):

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="targets")
    target_type = models.CharField(
        max_length=20, 
        choices=[("DEPARTMENT", "Department"), ("COMPANY", "Whole Company")],
        verbose_name=_("Target Type")
    )
    department_name = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Department Name"))

    class Meta:
        db_table = "product_targets"
        verbose_name = _("Product Target")
        verbose_name_plural = _("Product Targets")

    def __str__(self):
        return f"{self.product.name} - {self.target_type} ({self.department_name if self.department_name else 'Company-Wide'})"
