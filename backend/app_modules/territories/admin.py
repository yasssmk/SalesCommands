# backend/app_modules/territories/admin.py
"""
Django Admin configuration for Territory module.
"""

from django.contrib import admin
from .models import Territory


@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    """Admin configuration for Territory model."""
    
    list_display = [
        'name', 'type', 'is_system', 'is_default',
        'owner', 'created_at', 'updated_at'
    ]
    list_filter = ['type', 'is_system', 'is_default', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'client_id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    ordering = ['-is_system', 'name']
    
    fieldsets = (
        ('Identity', {
            'fields': ('id', 'client_id', 'name', 'description')
        }),
        ('Configuration', {
            'fields': ('type', 'is_system', 'is_default', 'filter_definition')
        }),
        ('Ownership', {
            'fields': ('owner',)
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )