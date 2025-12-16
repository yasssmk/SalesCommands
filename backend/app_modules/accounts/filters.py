# backend/app_modules/accounts/filters.py
"""
Custom FilterSet for CompanyAccount with multi-value support.

Uses BaseInFilter to accept comma-separated values for choice fields.
Example: ?type=CLIENT,PROSPECT → filters for type IN ['CLIENT', 'PROSPECT']

Note: This FilterSet works alongside AccountFilterService.
- FilterSet handles direct query params from URL (?type=X&classification=Y)
- AccountFilterService handles territory filter_definition (JSON-based filters)
"""

import django_filters
from django_filters import BaseInFilter, CharFilter, UUIDFilter

from .models import CompanyAccount


class CharInFilter(BaseInFilter, CharFilter):
    """
    Filter that accepts comma-separated string values.
    Example: ?type=CLIENT,PROSPECT → ['CLIENT', 'PROSPECT']
    """
    pass


class CompanyAccountFilter(django_filters.FilterSet):
    """
    Custom FilterSet for CompanyAccount.
    
    Supports:
    - Multi-value filters (comma-separated): type, classification, industry, country
    - Single value filters: account_owner
    """
    
    # Multi-value filters (accept comma-separated values)
    type = CharInFilter(field_name='type', lookup_expr='in')
    classification = CharInFilter(field_name='classification', lookup_expr='in')
    industry = CharInFilter(field_name='industry', lookup_expr='in')
    country = CharInFilter(field_name='country', lookup_expr='in')
    company_size = CharInFilter(field_name='company_size', lookup_expr='in')
    
    # Single value filters
    account_owner = UUIDFilter(field_name='account_owner_id')
    
    class Meta:
        model = CompanyAccount
        fields = ['type', 'classification', 'industry', 'country', 'company_size', 'account_owner']