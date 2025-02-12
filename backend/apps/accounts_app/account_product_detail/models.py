from django.db import models
from django.utils.translation import gettext_lazy as _
from products.models import Pricing, Product
from accounts.models import Account
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from apps.sales_insight.models import SalesInsight
from core.client_scope import ClientScopeManager
from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from decimal import Decimal

class AccountProductDetail(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Tracks and analyzes potential product usage and revenue for each account.
    Used for whitespace analysis and account targeting.
    """
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='account_details',
        verbose_name=_("Product")
    )
    
    # Target organizational units within the account
    target_org_units = models.ManyToManyField(
        'accounts_app.AccountOrganizationUnit',
        related_name='product_potentials',
        verbose_name=_("Target Organization Units")
    )

    # Potential calculations
    estimated_units = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name=_("Estimated Units/Seats"),
        help_text=_("Estimated number of units/seats for this product")
    )

    selected_pricing = models.ForeignKey(
        'products.Pricing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_potentials',
        verbose_name=_("Selected Pricing Model")
    )

    potential_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Potential Revenue"),
        help_text=_("Calculated potential revenue based on pricing and estimated units")
    )

    revenue_type = models.CharField(
        max_length=10,
        choices=[
            ('MRR', _('Monthly Recurring Revenue')),
            ('QRR', _('Quarterly Recurring Revenue')),
            ('ARR', _('Annual Recurring Revenue')),
            ('ONE_TIME', _('One Time Payment'))
        ],
        verbose_name=_("Revenue Type")
    )

    # AI insights for targeting
    ai_relevance_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
        verbose_name=_("AI Relevance Score"),
        help_text=_("AI-generated score for product relevance to this account")
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("Analysis Notes"),
        help_text=_("Additional notes about product potential in this account")
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'product'],
        index_fields=['revenue_type']
    )):
        db_table = 'account_product_details'
        verbose_name = _("Account Product Detail")
        verbose_name_plural = _("Account Product Details")
        ordering = ['-potential_revenue', 'product__product_name']

    def clean(self):
        """Validate business rules for account product details."""
        super().clean()

        if not self.selected_pricing and self.estimated_units:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="Selected pricing model is required when setting estimated units"
                )
            )

        # Ensure selected_pricing belongs to the product
        if self.selected_pricing and self.selected_pricing.product_id != self.product_id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="Selected pricing model must belong to the specified product"
                )
            )

    def calculate_revenue_multiplier(self):
        """Calculate the revenue multiplier based on pricing term and contract payment term."""
        if not self.selected_pricing:
            return 1

        pricing = self.selected_pricing
        pricing_term = pricing.pricing_term
        contract_term = pricing.contract_payment_term

        # If pricing term is yearly, no multiplication needed
        if pricing_term == pricing.PricingTerms.YEARLY:
            return 1

        # If pricing is quarterly
        if pricing_term == pricing.PricingTerms.QUARTERLY:
            if contract_term == pricing.ContractPaymentTerm.YEARLY:
                return 4
            elif contract_term == pricing.ContractPaymentTerm.QUARTERLY:
                return 1
            # Monthly contract term not possible due to validation

        # If pricing is monthly
        if pricing_term == pricing.PricingTerms.MONTHLY:
            if contract_term == pricing.ContractPaymentTerm.YEARLY:
                return 12
            elif contract_term == pricing.ContractPaymentTerm.QUARTERLY:
                return 3
            elif contract_term == pricing.ContractPaymentTerm.MONTHLY:
                return 1

        return 1  # Default fallback

    def calculate_potential_revenue(self):
        """Calculate potential revenue based on pricing model and estimated units."""
        if not self.selected_pricing or not self.estimated_units:
            return Decimal('0.00')

        pricing = self.selected_pricing
        base_amount = pricing.base_price
        unit_amount = pricing.unit_price * Decimal(str(self.estimated_units))
        multiplier = self.calculate_revenue_multiplier()

        total_amount = base_amount + (unit_amount * Decimal(str(multiplier)))
        
        # Set revenue type based on contract payment term
        self.revenue_type = pricing.get_recurrency_label()
        
        return total_amount

    def save(self, *args, **kwargs):
        # Calculate potential revenue before saving
        self.potential_revenue = self.calculate_potential_revenue()
                   
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account.company_name} - {self.product.product_name} ({self.revenue_type})"