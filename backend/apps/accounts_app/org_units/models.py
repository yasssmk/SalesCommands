from django.db import models
from django.conf import settings
from apps.core_apps.models import BaseModelApp,AccountLinkedModel
from apps.sales_insight.models import SalesInsight
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from core.error_messages import CoreErrorMessages, ValidationErrorMessages

class AccountOrganizationUnit(BaseModelApp, AccountLinkedModel):
    class UnitType(models.TextChoices):
        DEPARTMENT = 'DEPARTMENT', _('Department')
        DIVISION = 'DIVISION', _('Division')
        TEAM = 'TEAM', _('Team')

    organization_name = models.CharField(
        max_length=255, 
        verbose_name=_('Organization Name'),
        error_messages={
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Organization name'),
            'max_length': ValidationErrorMessages.MAX_LENGTH.format(
                field='Organization name',
                max_length=255
            )
        }
    )
    
    unit_type = models.CharField(
        max_length=50,
        choices=UnitType.choices,
        verbose_name=_('Unit Type')
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

    org_insights = models.OneToOneField(
        SalesInsight, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='linked_org'
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'organization_name'],
        index_fields=['organization_name']
    )):
        verbose_name = _('Organization Unit')
        ordering = ['-created_at', 'organization_name']
        indexes = [
            models.Index(fields=['account']),
            models.Index(fields=['parent_organization_unit'])
        ]
    
