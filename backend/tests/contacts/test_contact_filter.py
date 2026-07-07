# backend/tests/contacts/test_contact_filter.py
"""
ContactFilter.account_owner_id tests.

A contact has no owner of its own; "the contact's owner" resolves to the
owner of the contact's company account. The account_owner_id filter must
therefore return only contacts whose account is owned by the given user.
"""

import pytest

from app_modules.contacts.filters import ContactFilter
from app_modules.contacts.models import Contact


@pytest.mark.django_db
def test_account_owner_id_returns_only_contacts_of_that_owner(
    contact_of_a, contact_of_a2, user_a
):
    qs = Contact.objects.all()
    filtered = ContactFilter(
        {'account_owner_id': str(user_a.id)}, queryset=qs
    ).qs

    ids = set(filtered.values_list('id', flat=True))
    assert contact_of_a.id in ids
    assert contact_of_a2.id not in ids


@pytest.mark.django_db
def test_account_owner_id_absent_returns_all(
    contact_of_a, contact_of_a2
):
    qs = Contact.objects.all()
    filtered = ContactFilter({}, queryset=qs).qs

    ids = set(filtered.values_list('id', flat=True))
    assert contact_of_a.id in ids
    assert contact_of_a2.id in ids


@pytest.mark.django_db
def test_account_owner_id_unknown_owner_returns_none(
    contact_of_a, contact_of_a2, user_a2, account_owned_by_a2
):
    # A valid UUID that owns no account here (reuse a contact's id as a
    # syntactically valid but non-owner UUID).
    qs = Contact.objects.all()
    filtered = ContactFilter(
        {'account_owner_id': str(contact_of_a.id)}, queryset=qs
    ).qs

    assert filtered.count() == 0
