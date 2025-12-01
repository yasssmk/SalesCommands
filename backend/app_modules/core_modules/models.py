# app_modules/core/models.py
"""
Base models for app_modules package.

All models inherit from ModuleBaseModel which provides:
- UUID primary key
- Client isolation via client_id (multi-tenant)
- Audit fields (created_by, updated_by)
- Timestamps (created_at, updated_at)
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class ModuleBaseModel(models.Model):
    """
    Abstract base model for all app_modules models.
    
    Follows the same pattern as apps.core_apps.models.BaseModelApp
    for compatibility with ClientScopeManager.ModelMixin.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    client_id = models.UUIDField(
        verbose_name=_('Client ID'),
        help_text=_('ID of the client company this record belongs to'),
        db_index=True,
        editable=False
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_created',
        verbose_name=_('Created By')
    )
    
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_updated',
        verbose_name=_('Updated By')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        """
        Override save to handle audit fields.
        
        Usage:
            instance.save(user=request.user, client_id=client_id)
        
        Note:
            Uses self._state.adding instead of self.pk to detect new instances
            because UUID primary keys are auto-generated before save().
        """
        user = kwargs.pop('user', None)
        client_id = kwargs.pop('client_id', None)
        
        # Check if this is a new instance (not yet in database)
        is_new = self._state.adding
        
        # Handle client_id
        if is_new and client_id:
            self.client_id = client_id
        
        # Handle audit fields
        if user and not user.is_anonymous:
            if is_new:
                self.created_by = user
            self.updated_by = user
        
        super().save(*args, **kwargs)
    
    @property
    def client_account_id(self):
        """Alias for compatibility with client_account FK pattern."""
        return self.client_id