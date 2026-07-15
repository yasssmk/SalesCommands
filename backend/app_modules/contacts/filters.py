# app_modules/contacts/filters.py
"""
Custom FilterSet for Contact with multi-value support.

Uses BaseInFilter to accept comma-separated values for choice fields.
Example: ?influence_level=DECISION_MAKER,INFLUENCER
"""

import django_filters
from django_filters import BaseInFilter, CharFilter, UUIDFilter, BooleanFilter

from .models import Contact


class CharInFilter(BaseInFilter, CharFilter):
    """
    Filter that accepts comma-separated string values.
    Example: ?influence_level=DECISION_MAKER,INFLUENCER
    """
    pass


class ContactFilter(django_filters.FilterSet):
    """
    Custom FilterSet for Contact.
    
    Supports:
    - Multi-value filters (comma-separated): influence_level
    - Single value filters: account_id, standard_department
    - Boolean filters: opted_out, has_buying_authority, email_is_valid, phone_is_valid
    - Search filters: first_name, last_name, email, job_title
    """
    
    # Multi-value filters
    influence_level = CharInFilter(field_name='influence_level', lookup_expr='in')
    
    # Single value filters
    account_id = UUIDFilter(field_name='account_id')
    # TD-59: the query param is `standard_department` — the app-wide key used by
    # territory filter_definitions and the contact serializer's nested field.
    # The filter still resolves to the FK id column. (Previously exposed as
    # `standard_department_id`, which no client sent -> the department filter was
    # a silent no-op app-wide.)
    standard_department = django_filters.NumberFilter(field_name='standard_department_id')
    # A contact has no owner of its own — "the contact's owner" means the
    # owner of the contact's company account. Used by CONTACT-type territories
    # filtered on "Company's Owner".
    account_owner_id = UUIDFilter(field_name='account__account_owner_id')
    
    # Location filters (multi-value, from ContactDetailsMixin)
    country = CharInFilter(field_name='country', lookup_expr='in')
    state = CharInFilter(field_name='state', lookup_expr='in')
    city = CharInFilter(field_name='city', lookup_expr='in')
    
    # Boolean filters
    opted_out = BooleanFilter(field_name='opted_out')
    has_buying_authority = BooleanFilter(field_name='has_buying_authority')
    email_is_valid = BooleanFilter(field_name='email_is_valid')
    phone_is_valid = BooleanFilter(field_name='phone_is_valid')
    
    # Search filters (icontains for partial match)
    first_name = CharFilter(field_name='first_name', lookup_expr='icontains')
    last_name = CharFilter(field_name='last_name', lookup_expr='icontains')
    email = CharFilter(field_name='email', lookup_expr='icontains')
    job_title = CharFilter(field_name='job_title', lookup_expr='icontains')
    
    # Full name search (custom method)
    search = CharFilter(method='filter_search')
    
    class Meta:
        model = Contact
        fields = [
            'account_id', 'account_owner_id', 'influence_level', 'standard_department',
            'country', 'state', 'city',
            'opted_out', 'has_buying_authority', 'email_is_valid', 'phone_is_valid',
            'first_name', 'last_name', 'email', 'job_title', 'search'
        ]
    
    def filter_search(self, queryset, name, value):
        """
        Search across first_name, last_name, and email.
        """
        from django.db.models import Q
        
        if not value:
            return queryset
        
        return queryset.filter(
            Q(first_name__icontains=value) |
            Q(last_name__icontains=value) |
            Q(email__icontains=value)
        )