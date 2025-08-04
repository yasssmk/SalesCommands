from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from core.constants import COUNTRIES
from django.conf import settings
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError, StandardizedPermissionDenied


class BaseModelApp(models.Model):
    """
    Base model for all application models that need client tracking
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Last Updated"))
    client_id = models.UUIDField(
        verbose_name=_('Client ID'),
        help_text=_('ID of the client company this record belongs to'),
        db_index=True,
        editable=False
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="%(class)s_created", blank=True, null=True, verbose_name=_("Created By"))
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="%(class)s_updated", blank=True, null=True, verbose_name=_("Updated By"))


    class Meta:
        abstract = True
        
    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        user=kwargs.pop('user', None)
        client_id = kwargs.pop('client_id', None)
        
        if not self.pk:  # New instance
            if not client_id and not self.client_id:
                 raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
            
            if client_id:
                self.client_id = client_id
            if user:
                self.created_by = user
                self.updated_by = user
        else:  # Existing instance
            # Prevent client_id from being changed
            if client_id and client_id != self.client_id:
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_IMMUTABLE)
            
            if user:
                self.updated_by = user
            
            # Double check against database
            try:
                db_instance = self.__class__.objects.get(pk=self.pk)
                if self.client_id != db_instance.client_id:
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_IMMUTABLE)
            except self.__class__.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        super().save(force_insert=force_insert, force_update=force_update, *args, **kwargs)

    def delete(self, *args, **kwargs):
        client_id = kwargs.pop('client_id', None)
        if client_id and client_id != self.client_id:
            raise StandardizedPermissionDenied(CoreErrorMessages.CLIENT_MISMATCH)
        super().delete(*args, **kwargs)