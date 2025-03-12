from django.db import models
from apps.core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from core.error_messages import CoreErrorMessages
from core.constants import CURRENCY
from core.exceptions import StandardizedValidationError
from .product_model import Product


class Pricing(BaseModelApp, ClientScopeManager.ModelMixin):

    class PricingType(models.TextChoices):
        ASSET = "ASSET", _("Asset")
        SERVICE = "SERVICE", _("Service")
        SUBSCRIPTION = "SUBSCRIPTION", _("Subscription")
        USAGE = "USAGE", _("Usage")

    class PricingTerms(models.TextChoices):
        MONTHLY = "MONTHLY", _("Monthly")
        QUARTERLY = "QUARTERLY", _("Quarterly")
        YEARLY = "YEARLY", _("Yearly")
    
    class ContractPaymentTerm(models.TextChoices):
        MONTHLY = "MONTHLY", _("Monthly")
        QUARTERLY = "QUARTERLY", _("Quarterly")
        YEARLY = "YEARLY", _("Yearly")
        ONE_TIME = "ONE_TIME", _("One Time")

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

    contract_payment_term = models.CharField(
        max_length=20,
        choices=ContractPaymentTerm.choices,
        default=ContractPaymentTerm.YEARLY,
        verbose_name=_("Contract Payment Term")
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

    pricing_term = models.CharField(
        max_length=20,
        choices=PricingTerms.choices,
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

        # Rule 1: Billing term is required for subscription and usage pricing
        if self.pricing_type in [self.PricingType.SUBSCRIPTION, self.PricingType.USAGE]:
            if not self.pricing_term:
                raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(
                    field="Pricing term for subscription and usage pricing"
                ))

        # Rule 2: Billing term is not allowed for one time payment
        if self.contract_payment_term == 'ONE_TIME':
            if self.pricing_term:
                raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(
                    field="Pricing term is not allowed for one time payment contract"
                ))

        # Rule 3: Validate product contract payment term compatibility
        if self.pricing_type == self.PricingType.SUBSCRIPTION:
            if self.contract_payment_term == 'ONE_TIME':
                raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(
                    field="Subscription pricing cannot be used with one-time payment products"
                ))

        # Rule 4: Unit price validation for different pricing types
        if self.pricing_type in [self.PricingType.SUBSCRIPTION, self.PricingType.USAGE]:
            if self.unit_price <= 0:
                raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(
                    field="Unit price must be greater than 0 for subscription and usage pricing"
                ))

        # Rule 5: Base price validation for asset and service
        if self.pricing_type in [self.PricingType.ASSET, self.PricingType.SERVICE]:
            if self.base_price < 0:
                raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(
                    field="Base price must be greater than 0 for asset and service pricing"
                ))
        
        #6 : Pricing term cannot exceed contract term
        if self.pricing_term == "YEARLY":
            if self.contract_payment_term == "MONTHLY" or self.contract_payment_term == "QUARTERLY":
                raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(
                    field="Pricing term cannot exceed contract term"
                ))
            
        if self.pricing_term == "QUARTERLY":
            if self.contract_payment_term == "MONTHLY":
                raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(
                    field="Pricing term cannot exceed contract term"
                ))
            
    def get_recurrency_label(self):
            """
            Returns 'MRR', 'QRR', 'ARR', or 'ONE_TIME' 
            based on self.contract_payment_term.
            """
            if self.contract_payment_term == self.ContractPaymentTerm.MONTHLY:
                return "MRR"
            elif self.contract_payment_term == self.ContractPaymentTerm.QUARTERLY:
                return "QRR"
            elif self.contract_payment_term == self.ContractPaymentTerm.YEARLY:
                return "ARR"
            return "ONE_TIME"
            

    def __str__(self):
        return f"{self.product.product_name} - {self.pricing_type} - {self.base_price} {self.currency}"