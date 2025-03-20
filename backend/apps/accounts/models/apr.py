# apps/account/models/apr.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from core.client_scope import ClientScopeManager
from django.utils import timezone
from apps.core_apps.models import HistoricalTrackingModel

class RevenueType(models.TextChoices):
    ONE_TIME = 'ONE_TIME', _('One-Time')
    MRR = 'MRR', _('Monthly Recurring Revenue')
    QRR = 'QRR', _('Quarterly Recurring Revenue')
    ARR = 'ARR', _('Annual Recurring Revenue')

class AccountProductRelationship(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin, HistoricalTrackingModel):
    """
    Represents the relationship between an account and a product,
    including analysis of alignment and potential value.
    """
    # Product relationship
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='account_relationships',
        verbose_name=_('Product')
    )
    
    selected_pricing = models.ForeignKey(
        'products.Pricing',
        on_delete=models.SET_NULL,
        related_name='account_relationships',
        null=True,
        blank=True,
        verbose_name=_('Selected Pricing')
    )
    
    # Business fields
    estimated_units = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Estimated Units')
    )
    
    potential_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_('Potential Revenue')
    )
    
    revenue_type = models.CharField(
        max_length=50,
        choices=RevenueType.choices,
        default=RevenueType.ONE_TIME,
        verbose_name=_('Revenue Type')
    )
    
    # Analysis data
    objectives_alignment = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Objectives Alignment')
    )
    
    pain_points_coverage = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Pain Points Coverage')
    )
    
    economic_impact = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Economic Impact')
    )
    
    contribution_to_coverage = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Contribution to Coverage')
    )
    
    ai_relevance_score = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_('AI Relevance Score')
    )
    
    last_analysis_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Analysis Date')
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    # Product-specific buying steps
    buying_process = models.ForeignKey(
        'accounts_new.BuyingProcessStep',
        on_delete=models.SET_NULL,
        related_name='product_relationships',
        null=True,
        blank=True,
        verbose_name=_('Associated Buying Process')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        db_table = 'account_product_relationships'
        verbose_name = _('Account Product Relationship')
        verbose_name_plural = _('Account Product Relationships')
        ordering = ['-created_at']
        # Ensure unique account-product combinations
        unique_together = ('account', 'product')
    
    def __str__(self):
        return f"{self.account.company_name} - {self.product.product_name}"
    
    def save(self, *args, **kwargs):
        # Calculate potential revenue if pricing is selected
        if self.selected_pricing and self.estimated_units:
            # Get the price value from the pricing model
            price = self.selected_pricing.price or 0
            self.potential_revenue = price * self.estimated_units
        
        # Set last analysis date if applicable fields were updated
        analysis_fields = ['objectives_alignment', 'pain_points_coverage', 
                           'economic_impact', 'ai_relevance_score']
        
        for field in analysis_fields:
            if field in kwargs.get('update_fields', []):
                self.last_analysis_date = timezone.now()
                break
                
        super().save(*args, **kwargs)

    def clean(self):
        """Validate business rules for account product details."""
        super().clean()

        # if not self.selected_pricing and self.estimated_units:
        #     raise StandardizedValidationError(
        #         CoreErrorMessages.REQUIRED_FIELD.format(
        #             field="Selected pricing model is required when setting estimated units"
        #         )
        #     )

        # Ensure selected_pricing belongs to the product
        if self.selected_pricing and self.selected_pricing.product_id != self.product_id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="Selected pricing model must belong to the specified product"
                )
            )

    def calculate_revenue_multiplier(self):
        """Calculate revenue multiplier based on pricing terms"""
        if not self.selected_pricing:
            return 1

        pricing = self.selected_pricing
        pricing_term = pricing.pricing_term
        contract_term = pricing.contract_payment_term

        multiplier_map = {
            pricing.PricingTerms.YEARLY: 1,
            pricing.PricingTerms.QUARTERLY: {
                pricing.ContractPaymentTerm.YEARLY: 4,
                pricing.ContractPaymentTerm.QUARTERLY: 1
            },
            pricing.PricingTerms.MONTHLY: {
                pricing.ContractPaymentTerm.YEARLY: 12,
                pricing.ContractPaymentTerm.QUARTERLY: 3,
                pricing.ContractPaymentTerm.MONTHLY: 1
            }
        }

        if pricing_term in multiplier_map:
            if isinstance(multiplier_map[pricing_term], dict):
                return multiplier_map[pricing_term].get(contract_term, 1)
            return multiplier_map[pricing_term]
        return 1

    def calculate_potential_revenue(self):
        """Calculate potential revenue based on pricing and units"""
        if not self.selected_pricing or not self.estimated_units:
            return Decimal('0.00')

        pricing = self.selected_pricing
        unit_per = pricing.units_per
        base_amount = pricing.base_price
        unit_amount = pricing.unit_price * Decimal(str(self.estimated_units))/unit_per
        multiplier = self.calculate_revenue_multiplier()

        total_amount = base_amount + (unit_amount * Decimal(str(multiplier)))
        self.revenue_type = pricing.get_recurrency_label()
        
        return total_amount

    def __str__(self):
        return f"{self.account.company_name} - {self.product.product_name} ({self.revenue_type})"
    