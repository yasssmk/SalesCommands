# core/client_scope.py
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from core.error_messages import CoreErrorMessages

class ClientScopeManager:
    """
    Comprehensive manager for client scoping functionality.
    Handles CRUD operations, validation, and data filtering.
    """
    
    class ModelMixin(models.Model):
        class Meta:
            abstract = True

        @classmethod
        def get_meta_constraints(cls, unique_fields=None, index_fields=None):
            """
            Helper to get all meta constraints at once.
            Usage: 
                class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
                    unique_fields=['field1', 'field2'],
                    index_fields=['field1']
                ))
            """
            meta_dict = {
                'abstract': False
            }
            
            if unique_fields:
                meta_dict['unique_together'] = cls.get_client_scoped_unique_together(*unique_fields)
                
            if index_fields:
                meta_dict['indexes'] = cls.get_client_scoped_indexes(*index_fields)
                
            return type('Meta', (), meta_dict)

        @classmethod
        def get_client_scoped_unique_together(cls, *fields):
            """Helper to create unique_together constraints with client_id"""
            return [(*fields, 'client_id')]

        @classmethod
        def get_client_scoped_indexes(cls, *fields):
            """Helper to create indexes including client_id"""
            return [models.Index(fields=[*fields, 'client_id'])]

    class SerializerMixin(serializers.Serializer):
        """
        Serializer mixin for client-scoped validation
        """
        def validate_client_scoped_uniqueness(self, data, unique_fields, model_class=None, error_message=None):
            """Validate uniqueness within client scope"""
            model = model_class or self.Meta.model
            instance = getattr(self, 'instance', None)
            
            try:
                client_id = self._get_client_id_from_context()
            except serializers.ValidationError as e:
                raise serializers.ValidationError({
                    'client_id': str(e)
                })
            
            filter_kwargs = {
                'client_id': client_id,
                **{f"{field}__iexact": data.get(field) 
                   for field in unique_fields 
                   if data.get(field)}
            }
            
            duplicate_exists = model.objects.filter(
                **filter_kwargs
            ).exclude(
                pk=instance.pk if instance else None
            ).exists()
            
            if duplicate_exists:
                if not error_message:
                    field_names = ', '.join(unique_fields)
                    error_message = CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                        fields=field_names
                    )
                raise serializers.ValidationError({
                    "error": error_message
                })
            
            return data
            

        def _get_client_id_from_context(self):
            """Helper to get client_id from context"""
            request = self.context.get('request')
            if not request or not request.auth:
                raise serializers.ValidationError(CoreErrorMessages.AUTH_REQUIRED)
                
            client_id = request.auth.get('client_account')
            if not client_id:
                raise serializers.ValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
                
            return client_id

    class ViewMixin:
        """
        View mixin for client-scoped CRUD operations
        """
        def get_client_id(self):
            """Get client_id from JWT token"""
            if not self.request.auth:
                raise AuthenticationFailed(CoreErrorMessages.AUTH_REQUIRED)

            origin = self.request.auth.get('origin')
            
            if origin == 'end_users':
                client_id = self.request.auth.get('client_account')
                if not client_id:
                    raise AuthenticationFailed(CoreErrorMessages.CLIENT_ID_REQUIRED)
                return client_id
                
            raise AuthenticationFailed(CoreErrorMessages.PERMISSION_DENIED)
        
        def validate_client_id(self, obj):
            """Validate that an object belongs to the current client"""
            if not hasattr(obj, 'client_id'):
                raise ValidationError({
                    'error': CoreErrorMessages.CLIENT_SCOPE_UNSUPPORTED
                })
            
            current_client = self.get_client_id()
            if str(obj.client_id) != str(current_client):
                raise PermissionDenied(CoreErrorMessages.CLIENT_MISMATCH)

        def filter_queryset_by_client(self, queryset):
            """Apply client_id filtering with additional validation"""
            client_id = self.get_client_id()
            filtered_queryset = queryset.filter(client_id=client_id)
            
            # Add debugging for development
            if settings.DEBUG:
                print(f"Filtering queryset for client {client_id}")
                print(f"Original count: {queryset.count()}")
                print(f"Filtered count: {filtered_queryset.count()}")
                
            return filtered_queryset

    def perform_create(self, serializer):
        """Create with strict client_id enforcement"""
        try:
            client_id = self.get_client_id()
            instance = serializer.save(client_id=client_id)
            self.validate_client_id(instance)
            return instance
        except Exception as e:
            print(f"Error in perform_create: {str(e)}", exc_info=True)
            raise

    def perform_update(self, serializer):
        """Update with strict client_id validation"""
        try:
            instance = serializer.instance
            self.validate_client_id(instance)
            
            if 'client_id' in serializer.validated_data:
                raise ValidationError({
                    'client_id': CoreErrorMessages.CLIENT_ID_IMMUTABLE
                })
                
            updated = serializer.save()
            self.validate_client_id(updated)
            return updated
        except Exception as e:
            print(f"Error in perform_update: {str(e)}", exc_info=True)
            raise

    def perform_delete(self, instance):
        """Delete with client_id validation"""
        try:
            self.validate_client_id(instance)
            instance.delete(client_id=self.get_client_id())
        except Exception as e:
            print(f"Error in perform_delete: {str(e)}", exc_info=True)
            raise

    def check_object_permissions(self, request, obj):
        """Enhanced permission checking"""
        super().check_object_permissions(request, obj)
        self.validate_client_id(obj)