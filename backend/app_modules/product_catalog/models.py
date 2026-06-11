# app_modules/product_catalog/models.py
"""
ProductCatalog model for the tenant-level product master catalog.

Admin-curated reference list of the products the sales organization
sells. Each entry represents a distinct product line; downstream
DealProduct rows attach catalog entries to a DecisionCycle with
quantity and optional price override.

Identity model:
    A catalog entry is identified by `name`, tenant-scoped.
    Uniqueness on (client_id, name) is enforced by the composite
    constraint declared in Meta.

Tenant isolation:
    Provided by ClientScopeManager.ModelMixin (client_id on
    ModuleBaseModel). All reads/writes go through ScopedQuerysetMixin.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages


class ProductCatalog(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Tenant-level master catalog entry for a single product.
    """

    # =========================================================================
    # IDENTITY
    # =========================================================================

    name = models.CharField(
        max_length=255,
        verbose_name=_('Product Name'),
        help_text=_('Name of the product (e.g. "Enterprise License", "Professional Services"). Required.'),
    )

    description = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Description'),
        help_text=_('Optional description of the product.'),
    )

    value_proposition = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Value Proposition'),
        help_text=_('Benefits and value for the sales pitch.'),
    )

    # =========================================================================
    # PRICING
    # =========================================================================

    default_unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Default Unit Price'),
        help_text=_('Default unit price; can be overridden per deal.'),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['name'],
        index_fields=['name'],
    )):
        db_table = 'product_catalog'
        verbose_name = _('Product Catalog Entry')
        verbose_name_plural = _('Product Catalog Entries')
        ordering = ['name']

    def __str__(self):
        return self.name

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        super().clean()

        if self.name:
            self.name = self.name.strip()

        if not self.name:
            raise ValidationError({
                'name': CoreErrorMessages.REQUIRED_FIELD.format(
                    field='Product name'
                ),
            })
