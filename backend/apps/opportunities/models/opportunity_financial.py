# apps/opportunities/models/opportunity_financial.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError


class OpportunityLineItem(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Represents a product line item in an opportunity
    """
    
    opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='line_items',
        verbose_name=_('Opportunity')
    )
    
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='opportunity_items',
        verbose_name=_('Product')
    )
    
    pricing = models.ForeignKey(
        'products.Pricing',
        on_delete=models.PROTECT,
        related_name='opportunity_items',
        verbose_name=_('Pricing Model')
    )
    
    quantity = models.IntegerField(
        default=1,
        verbose_name=_('Quantity')
    )
    
    # For any price override or custom pricing
    custom_unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Custom Unit Price')
    )
    
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Discount (%)')
    )
    
    line_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Line Total')
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Line Item Notes')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['opportunity', 'product', 'pricing'],
        index_fields=['product']
    )):
        db_table = 'opportunity_line_items'
        verbose_name = _('Opportunity Line Item')
        verbose_name_plural = _('Opportunity Line Items')
        ordering = ['id']
    
    def __str__(self):
        return f"{self.product.product_name} - {self.quantity} × {self.get_unit_price()}"
    
    def get_unit_price(self):
        """Get the effective unit price (custom if set, otherwise from pricing model)"""
        if self.custom_unit_price is not None:
            return self.custom_unit_price
        return self.pricing.unit_price
    
    def calculate_line_total(self):
        """Calculate the total for this line item"""
        unit_price = self.get_unit_price()
        base_amount = self.quantity * unit_price
        
        # Apply discount if any
        if self.discount_percentage > 0:
            discount_amount = (base_amount * self.discount_percentage) / 100
            return base_amount - discount_amount
        
        return base_amount
    
    def get_revenue_type(self):
        """Return the revenue type based on pricing model"""
        return self.pricing.get_recurrency_label()
    
    def get_pricing_type(self):
        """Return the pricing type of this line item"""
        return self.pricing.pricing_type
    
    def save(self, *args, **kwargs):
        # Calculate line total
        self.line_total = self.calculate_line_total()
        super().save(*args, **kwargs)
        
        # Update opportunity financials
        self.opportunity.update_financials()
    
    def clean(self):
        """Validate the model"""
        super().clean()
        
        # Ensure pricing belongs to the selected product
        if self.pricing and self.product and self.pricing.product_id != self.product.id:
            raise StandardizedValidationError(
                "Selected pricing must belong to the selected product",
                field_name="pricing"
            )
        
        # Validate discount percentage range
        if self.discount_percentage < 0 or self.discount_percentage > 100:
            raise StandardizedValidationError(
                "Discount percentage must be between 0 and 100",
                field_name="discount_percentage"
            )
        
        # Validate quantity
        if self.quantity <= 0:
            raise StandardizedValidationError(
                "Quantity must be greater than zero",
                field_name="quantity"
            )


class OpportunityFinancialSummary(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Financial summary for an opportunity - calculated from line items
    """
    
    class ForecastCategory(models.TextChoices):
        PIPELINE = 'PIPELINE', _('Pipeline')
        UPSIDE = 'UPSIDE', _('Upside')
        COMMIT = 'COMMIT', _('Commit')
        CLOSED_WON = 'CLOSED_WON', _('Closed Won')
        CLOSED_LOST = 'CLOSED_LOST', _('Closed Lost')
    
    opportunity = models.OneToOneField(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='financial_summary',
        verbose_name=_('Opportunity')
    )
    
    # Forecasting
    forecast_category = models.CharField(
        max_length=20,
        choices=ForecastCategory.choices,
        default=ForecastCategory.PIPELINE,
        verbose_name=_('Forecast Category')
    )
    
    probability = models.IntegerField(
        default=0,
        verbose_name=_('Probability (%)'),
        help_text=_('Likelihood of closing as a percentage')
    )
    
    # Calculated totals
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Total Amount')
    )
    
    expected_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Expected Revenue')
    )
    
    # Revenue by contract term
    mrr_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('MRR Amount')
    )
    
    qrr_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('QRR Amount')
    )
    
    arr_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('ARR Amount')
    )
    
    one_time_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('One-Time Amount')
    )
    
    # Revenue by pricing type
    asset_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Asset Revenue')
    )
    
    service_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Service Revenue')
    )
    
    subscription_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Subscription Revenue')
    )
    
    usage_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Usage Revenue')
    )
    
    # Currency tracking
    primary_currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_('Primary Currency')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['opportunity'],
        index_fields=['forecast_category']
    )):
        db_table = 'opportunity_financial_summaries'
        verbose_name = _('Opportunity Financial Summary')
        verbose_name_plural = _('Opportunity Financial Summaries')
        indexes = [
            models.Index(fields=['probability']),
            models.Index(fields=['total_amount']),
            # Composite index for financial reporting queries
            models.Index(fields=['forecast_category', 'probability'], name='opp_forecast_prob_idx'),
        ]
    
    def __str__(self):
        return f"Financial summary for {self.opportunity.title}"
    
    def save(self, *args, **kwargs):
        # Calculate expected revenue
        self.expected_revenue = (self.total_amount * self.probability) / 100
        super().save(*args, **kwargs)
    
    def update_from_line_items(self):
        """Update financial summary based on line items"""
        line_items = self.opportunity.line_items.all()
        
        # Reset all amounts
        self.total_amount = Decimal('0.00')
        self.mrr_amount = Decimal('0.00')
        self.qrr_amount = Decimal('0.00')
        self.arr_amount = Decimal('0.00')
        self.one_time_amount = Decimal('0.00')
        self.asset_revenue = Decimal('0.00')
        self.service_revenue = Decimal('0.00')
        self.subscription_revenue = Decimal('0.00')
        self.usage_revenue = Decimal('0.00')
        
        # Calculate totals for each category
        for item in line_items:
            # Add to total amount
            self.total_amount += item.line_total
            
            # Add to appropriate revenue type based on contract payment term
            revenue_type = item.get_revenue_type()
            if revenue_type == 'MRR':
                self.mrr_amount += item.line_total
            elif revenue_type == 'QRR':
                self.qrr_amount += item.line_total
            elif revenue_type == 'ARR':
                self.arr_amount += item.line_total
            else:  # ONE_TIME
                self.one_time_amount += item.line_total
            
            # Add to appropriate pricing type category
            pricing_type = item.get_pricing_type()
            if pricing_type == 'ASSET':
                self.asset_revenue += item.line_total
            elif pricing_type == 'SERVICE':
                self.service_revenue += item.line_total
            elif pricing_type == 'SUBSCRIPTION':
                self.subscription_revenue += item.line_total
            elif pricing_type == 'USAGE':
                self.usage_revenue += item.line_total
        
        # Calculate expected revenue
        self.expected_revenue = (self.total_amount * self.probability) / 100
        
        # Set primary currency (from first line item if available)
        if line_items.exists():
            first_item = line_items.first()
            self.primary_currency = first_item.pricing.currency
        
        self.save()