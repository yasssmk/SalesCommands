# backend/tests/contacts/conftest.py
"""
Pytest fixtures for the contacts module tests.

Complements backend/tests/signals/conftest.py: re-exports the tenant /
user / role fixtures and adds two same-tenant accounts owned by two
different users, each with one contact. This lets ContactFilter's
account_owner_id (a contact scoped by its company account's owner) be
exercised without cross-tenant noise.
"""

import pytest

from tests.signals.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
)


# =============================================================================
# SECOND USER — same tenant as user_a, distinct owner
# =============================================================================

@pytest.fixture
def user_a2(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='rep-a2@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


# =============================================================================
# TWO ACCOUNTS in the same tenant, owned by different users
# =============================================================================

@pytest.fixture
def account_owned_by_a(db, client_account_a, user_a):
    from app_modules.accounts.models import CompanyAccount
    acc = CompanyAccount(company_name='Acme (A)', account_owner=user_a)
    acc.save(user=user_a, client_id=client_account_a.id)
    return acc


@pytest.fixture
def account_owned_by_a2(db, client_account_a, user_a, user_a2):
    from app_modules.accounts.models import CompanyAccount
    acc = CompanyAccount(company_name='Globex (A2)', account_owner=user_a2)
    acc.save(user=user_a, client_id=client_account_a.id)
    return acc


# =============================================================================
# ONE CONTACT per account
# =============================================================================

@pytest.fixture
def contact_of_a(db, account_owned_by_a, user_a):
    from app_modules.contacts.models import Contact
    c = Contact(
        account=account_owned_by_a,
        first_name='Alice',
        last_name='Owner-A',
    )
    c.save(user=user_a, client_id=account_owned_by_a.client_id)
    return c


@pytest.fixture
def contact_of_a2(db, account_owned_by_a2, user_a):
    from app_modules.contacts.models import Contact
    c = Contact(
        account=account_owned_by_a2,
        first_name='Bob',
        last_name='Owner-A2',
    )
    c.save(user=user_a, client_id=account_owned_by_a2.client_id)
    return c
