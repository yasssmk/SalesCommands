from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.products.models import Pricing, Product
from apps.accounts_app.accounts.models import Account
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
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
from django.utils import timezone

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
        'org_units.AccountOrganizationUnit',
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

    # Analysis data storage
    objectives_alignment = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Objectives Alignment"),
        help_text=_("Alignment between account objectives and product benefits")
    )
    
    pain_points_coverage = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Pain Points Coverage"),
        help_text=_("Coverage of account pain points by product features")
    )
    
    economic_impact = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Economic Impact"),
        help_text=_("Economic impact analysis of the product for this account")
    )
    
    coverage_stats = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Coverage Statistics"),
        help_text=_("Statistical metrics about product coverage")
    )
    
    last_analysis_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Analysis Date"),
        help_text=_("When the product alignment was last analyzed")
    )

    tech_relationships = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Tech Stack Relationships"),
        help_text=_("Relationships between this product and customer's existing technologies")
    )
    

    notes = models.TextField(
        blank=True,
        verbose_name=_("Analysis Notes"),
        help_text=_("Additional notes about product potential in this account")
    )

    historical_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Historical Data"),
        help_text=_("Stores changes in key fields over time")
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'product'],
        index_fields=['revenue_type']
    )):
        db_table = 'account_product_details'
        verbose_name = _("Account Product Detail")
        verbose_name_plural = _("Account Product Details")
        ordering = ['-potential_revenue', 'product__product_name']

    def track_field_change(self, field_name, old_value, new_value, user):
        """
        Tracks changes to fields and updates historical_data.
        """
        if not self.historical_data:
            self.historical_data = {}

        if field_name not in self.historical_data:
            self.historical_data[field_name] = []

        self.historical_data[field_name].append({
            'old_value': old_value,
            'new_value': new_value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None,
            'source': 'signal'
        })

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

    def save(self, *args, **kwargs):
        """
        Override save method to track changes before saving.
        Also ensures that `self.potential_revenue` is calculated before saving.
        """
        user = kwargs.pop('user', None)  # Extract user if provided in save()

        if self.pk:  # Only track changes for existing records
            old_instance = AccountProductDetail.objects.get(pk=self.pk)

            for field in ['estimated_units', 'selected_pricing', 'potential_revenue', 'ai_relevance_score',
                         'objectives_alignment', 'pain_points_coverage', 'economic_impact', 'tech_relationships']:
                old_value = getattr(old_instance, field, None)
                new_value = getattr(self, field, None)

                if old_value != new_value:
                    self.track_field_change(field, old_value, new_value, user)

        # ✅ Keep potential revenue calculation before saving
        self.potential_revenue = self.calculate_potential_revenue()

        # Update last_analysis_date if analysis fields are being updated
        analysis_fields = ['objectives_alignment', 'pain_points_coverage', 'economic_impact', 'coverage_stats', 'tech_relationships']
        if any(hasattr(self, field) and getattr(self, field) != getattr(self.__class__.objects.get(pk=self.pk), field, None) 
               for field in analysis_fields if self.pk):
            self.last_analysis_date = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account.company_name} - {self.product.product_name} ({self.revenue_type})"
