# app_modules/tech_catalog/models.py
"""
TechCatalog model for the tenant-level technology master catalog.

The TechCatalog is a pure reference list of products that the sales
organization needs to recognize on prospect accounts — competitors to
displace, integration targets to land alongside, and contextually
relevant tools to track.

Granularity is at the PRODUCT level, not the company level. A single
vendor (e.g. Salesforce) typically ships multiple products (Sales Cloud,
Service Cloud, Marketing Cloud, etc.); each is a distinct catalog entry.

Identity model:
    A catalog entry is identified by the pair (company_name, product_name).
    Both are required fields. When the vendor and product share a name
    (e.g. "Notion") the admin can leave product_name blank — clean()
    auto-populates it from company_name. Tenant-scoped uniqueness on
    the (company_name, product_name) pair guarantees that two tenants
    can both register "Salesforce / Sales Cloud" without conflict, and
    that one tenant cannot register the same product twice.

Reference-only by design:
    This model is a pure catalog. It carries no contextual notes, no
    workflow status, no derived state. Any commercial context that
    depends on the situation (gameplay notes, observed usage, account
    fit) belongs on the downstream M2M relations that consume the
    catalog (Decision Cycle ↔ TechCatalog, Product ↔ TechCatalog,
    TechStackSignal ↔ TechCatalog), where it has the right scope.

What this model deliberately does NOT have:
    * No `gameplay_notes` / `internal_notes` — those live on the M2M
      consumers.
    * No workflow status (DRAFT / VALIDATED / DEPRECATED) — admin
      curation makes a workflow lane unnecessary at this scope.
    * No aliases / normalized name — exact-match uniqueness within a
      tenant is sufficient until concrete fuzzy-matching needs arise.
    * No category taxonomy — every fixed taxonomy tried so far broke on
      real cases.
    * No soft delete — hard delete via the ViewSet, mirroring the
      CompanyAccount pattern.

Tenant isolation:
    Provided by `ClientScopeManager.ModelMixin` (via `client_id` on
    `ModuleBaseModel`). All reads and writes go through
    `ScopedQuerysetMixin` on the ViewSet, scoped to the requesting
    user's tenant.
"""


from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages


class TechCatalog(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Tenant-level master catalog entry for a single product.

    All fields except `company_name` and `product_name` are optional —
    admins capture as much or as little context as is useful at entry
    time.
    """

    # =========================================================================
    # IDENTITY
    # =========================================================================

    company_name = models.CharField(
        max_length=255,
        verbose_name=_('Company Name'),
        help_text=_(
            'Name of the vendor (e.g. "Salesforce", "Microsoft", "Notion"). '
            'Required.'
        ),
    )

    product_name = models.CharField(
        max_length=255,
        verbose_name=_('Product Name'),
        help_text=_(
            'Name of the specific product (e.g. "Sales Cloud", "Teams"). '
            'Required, but auto-populated from `company_name` when left '
            'blank — useful when the vendor ships a single product '
            'sharing its name (e.g. "Notion" / "Notion").'
        ),
    )

    vendor_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('Vendor URL'),
        help_text=_('Optional canonical URL of the vendor (homepage).'),
    )

    # =========================================================================
    # COMMERCIAL FLAGS
    #
    # Two independent booleans. Any presentational combination
    # (e.g. "competitive integration" when both are true) is computed
    # downstream — the model carries no derived state.
    # =========================================================================

    is_competitor = models.BooleanField(
        default=False,
        verbose_name=_('Is Competitor'),
        help_text=_(
            'True when this product overlaps with what we sell — '
            'replacing it is a winnable angle in a deal.'
        ),
    )

    is_integration_target = models.BooleanField(
        default=False,
        verbose_name=_('Is Integration Target'),
        help_text=_(
            'True when this product is one we connect to — integrating '
            'with it is a winnable angle in a deal.'
        ),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['company_name', 'product_name'],
        index_fields=['company_name'],
    )):
        db_table = 'tech_catalog'
        verbose_name = _('Tech Catalog Entry')
        verbose_name_plural = _('Tech Catalog Entries')
        ordering = ['company_name', 'product_name']

    def __str__(self):
        # When company and product share the same name, collapse the
        # display to a single token instead of "Notion / Notion".
        if self.company_name == self.product_name:
            return self.company_name
        return f'{self.company_name} / {self.product_name}'

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce TechCatalog invariants beyond the field-level checks
        Django runs automatically.

        Rules:
            1. `company_name` is required (non-blank after stripping).
               The CharField itself accepts whitespace-only values;
               stripping here ensures the unique constraint isn't
               bypassed by a blank-looking entry.

            2. `product_name` is required, but blank input is
               auto-resolved to `company_name`. This supports the
               common case where a vendor ships a single product whose
               name matches the vendor's. Both fields are normalized
               (trimmed) before the resolution so that whitespace-only
               input on `product_name` is treated as blank.

        Tenant-scoped uniqueness on `(client_id, company_name,
        product_name)` is enforced by the composite constraint declared
        in Meta — no need to re-check it here.
        """
        super().clean()

        # --- Normalize whitespace on both names ---
        if self.company_name:
            self.company_name = self.company_name.strip()
        if self.product_name:
            self.product_name = self.product_name.strip()

        # --- company_name required ---
        if not self.company_name:
            raise ValidationError({
                'company_name': CoreErrorMessages.REQUIRED_FIELD.format(
                    field='Company name'
                ),
            })

        # --- product_name: auto-fill from company_name when blank ---
        if not self.product_name:
            self.product_name = self.company_name