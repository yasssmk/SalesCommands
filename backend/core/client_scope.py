# core/client_scope.py
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.db import models
from django.utils.translation import gettext_lazy as _

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
            client_id = self._get_client_id_from_context()
            
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
                    error_message = _(
                        f"An entry with this {field_names} already exists in your organization."
                    )
                raise serializers.ValidationError({"error": error_message})
            
            return data

        def _get_client_id_from_context(self):
            """Helper to get client_id from context"""
            request = self.context.get('request')
            if not request or not request.auth:
                raise serializers.ValidationError("Authentication required")
                
            client_id = request.auth.get('client_account')
            if not client_id:
                raise serializers.ValidationError("Client account required")
                
            return client_id

    class ViewMixin:
        """
        View mixin for client-scoped CRUD operations
        """
        def get_client_id(self):
            """Get client_id from JWT token"""
            if not self.request.auth:
                raise AuthenticationFailed(_("Authentication required"))

            origin = self.request.auth.get('origin')
            
            if origin == 'end_users':
                client_id = self.request.auth.get('client_account')
                if not client_id:
                    raise AuthenticationFailed(_("No client account found in token"))
                return client_id
                
            raise AuthenticationFailed(_("Please log in with a user account"))

        def filter_queryset_by_client(self, queryset):
            """Apply client_id filtering to queryset"""
            return queryset.filter(client_id=self.get_client_id())

        def get_queryset(self):
            """Get client-scoped queryset"""
            assert self.queryset is not None, "Define queryset in your view"
            return self.filter_queryset_by_client(self.queryset.all())

        def check_object_permissions(self, request, obj):
            """Ensure object belongs to client"""
            super().check_object_permissions(request, obj)
            
            client_id = self.get_client_id()
            if not hasattr(obj, 'client_id') or obj.client_id != client_id:
                raise PermissionDenied(_("Not found"))

        def perform_create(self, serializer):
            """Create with client_id"""
            return serializer.save(client_id=self.get_client_id())

        def perform_update(self, serializer):
            """Update with client check"""
            instance = serializer.save()
            self.check_object_permissions(self.request, instance)
            return instance

        def perform_delete(self, instance):
            """Delete with client check"""
            self.check_object_permissions(self.request, instance)
            instance.delete()