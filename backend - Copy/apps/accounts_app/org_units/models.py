from django.db import models
from django.conf import settings
from apps.core_apps.models import BaseModelApp,AccountLinkedModel
from core.client_scope import ClientScopeManager
from apps.sales_insight.models  import QualificationModel
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import StandardDepartment


class AccountOrganizationUnit(BaseModelApp, ClientScopeManager.ModelMixin, AccountLinkedModel, QualificationModel):
    class UnitType(models.TextChoices):
        DEPARTMENT = 'DEPARTMENT', _('Department')
        DIVISION = 'DIVISION', _('Division')
        TEAM = 'TEAM', _('Team')

    organization_name = models.CharField(
        max_length=255, 
        verbose_name=_('Organization Name'),
    )
    
    unit_type = models.CharField(
        max_length=50,
        choices=UnitType.choices,
        verbose_name=_('Unit Type'),
    )

    standard_department = models.ForeignKey(
        StandardDepartment,
        on_delete=models.PROTECT,
        default=1,
        related_name='organization_units',
        verbose_name=_('Standard Department')
    )

    parent_organization_unit = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        related_name='child_organization_units', 
        blank=True, 
        null=True
    )
    
    estimated_employee_count = models.IntegerField(
        blank=True, 
        null=True
    )

    metadata = models.JSONField(
        blank=True, 
        null=True
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'organization_name'],
        index_fields=['organization_name']
    )):
        verbose_name = _('Organization Unit')
        db_table = 'Organization_Unit'
        ordering = ['-created_at', 'organization_name']
        indexes = [
            models.Index(fields=['account']),
            models.Index(fields=['parent_organization_unit'])
        ]
    
