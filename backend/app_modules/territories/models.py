# backend/app_modules/territories/models.py
"""
Territory model for sales segmentation.

Territories are saved filters/segments of accounts or contacts
that sales reps use to organize and prioritize their work.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from ..core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from end_users.models import User


class TerritoryType(models.TextChoices):
    """Territory type choices."""
    ACCOUNT = 'ACCOUNT', _('Account-based')
    CONTACT = 'CONTACT', _('Contact-based')


class Territory(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Territory model for sales segmentation.
    
    A territory is a saved set of filters that defines a segment
    of accounts or contacts. Sales reps use territories to:
    - Focus on specific account segments
    - Plan campaigns and activities
    - Track KPIs by segment
    
    Features:
        - Dynamic filtering via filter_definition JSON
        - System territories (built-in, non-deletable)
        - Owner assignment
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """
    
    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Name')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    type = models.CharField(
        max_length=20,
        choices=TerritoryType.choices,
        default=TerritoryType.ACCOUNT,
        verbose_name=_('Territory Type'),
        help_text=_('Whether this territory segments accounts or contacts')
    )
    
    # ==========================================================================
    # SYSTEM FLAGS
    # ==========================================================================
    
    is_system = models.BooleanField(
        default=False,
        verbose_name=_('System Territory'),
        help_text=_('System territories cannot be deleted')
    )
    
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Default Territory'),
        help_text=_('Default territory shown when user opens the page')
    )
    
    # ==========================================================================
    # FILTER DEFINITION
    # ==========================================================================
    
    filter_definition = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Filter Definition'),
        help_text=_('JSON object defining filter rules')
    )
    
    # ==========================================================================
    # OWNERSHIP
    # ==========================================================================
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        related_name='owned_territories',
        verbose_name=_('Owner'),
        help_text=_('User who owns this territory')
    )

    # ==========================================================================
    # COVERAGE SNAPSHOT (manager aggregate)
    # ==========================================================================
    # A LAZY, read-refreshed materialisation of this territory's coverage counts,
    # so the manager's team aggregate is a single GROUP BY over these columns
    # instead of 2 queries × N territories on every Home load. These are
    # DELIBERATELY not live: they are refreshed on read when older than a TTL
    # (~2h) or when the fiscal period changes, and are NOT invalidated by account
    # or activity writes. The per-territory KPI (rep Home) stays live and ignores
    # these. All nullable: a null coverage_computed_at means "never computed"
    # (treated as stale). See territories.services.snapshot.

    coverage_numerator = models.IntegerField(
        null=True, blank=True,
        verbose_name=_('Coverage numerator (snapshot)'),
        help_text=_('Accounts touched with a response in the period — snapshot, not live')
    )

    coverage_denominator = models.IntegerField(
        null=True, blank=True,
        verbose_name=_('Coverage denominator (snapshot)'),
        help_text=_('Total accounts in the territory — snapshot, not live')
    )

    coverage_period_key = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name=_('Coverage period key (snapshot)'),
        help_text=_('The period the snapshot was computed for; a mismatch forces a recompute')
    )

    coverage_computed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Coverage computed at (snapshot)'),
        help_text=_('When the snapshot was last refreshed; null = never (stale)')
    )

    # ==========================================================================
    # META
    # ==========================================================================
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['name'],
        index_fields=['name']
    )):
        db_table = 'module_territories'
        verbose_name = _('Territory')
        verbose_name_plural = _('Territories')
        ordering = ['-is_system', 'name']
        indexes = [
            models.Index(fields=['owner'], name='mod_terr_owner_idx'),
            models.Index(fields=['type'], name='mod_terr_type_idx'),
            models.Index(fields=['is_system'], name='mod_terr_system_idx'),
        ]
    
    def __str__(self):
        type_display = self.get_type_display() if self.type else 'Unknown'
        return f"{self.name} ({type_display})"
    
    # ==========================================================================
    # PROPERTIES
    # ==========================================================================
    
    @property
    def has_filters(self):
        """Check if territory has any filters defined."""
        return bool(self.filter_definition)
    
    @property
    def filter_count(self):
        """Count of active filters."""
        if not self.filter_definition:
            return 0
        return len([v for v in self.filter_definition.values() if v])
    
    # ==========================================================================
    # METHODS
    # ==========================================================================
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of system territories."""
        if self.is_system:
            from core.exceptions import StandardizedValidationError
            raise StandardizedValidationError(
                CoreErrorMessages.CANNOT_DELETE,
                field='system territories'
            )
        return super().delete(*args, **kwargs)
