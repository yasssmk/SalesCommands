"""
Empty-string -> NULL normalization on Contact writes, exercised through the REAL
HTTP endpoints (not direct save()/serializer calls that would mask a path gap).

Root cause of the recurring unique-constraint collision on
(account, email, client_id): an edit that carries email="" in its payload (e.g. a
department change re-submitting the whole form) rewrites the column to '' instead
of NULL. PostgreSQL allows many NULLs but only one '' per scope, so the '' brings
the collision back. Contact.save() normalizes email/phone_number '' -> NULL, and
every write path funnels through save().

The opt-out action (which never sends email) is the control: it must keep NULL.
"""

import pytest
from rest_framework.test import APIClient


def _auth(user, tenant_id):
    """APIClient authenticated exactly as production JWT auth shapes the claims."""
    api = APIClient()
    role = user.role
    claims = {
        'origin': 'end_users',
        'user_id': str(user.id),
        'client_account': str(tenant_id),
        'role': {
            'id': str(role.id) if role else '',
            'name': role.name if role else '',
            'is_admin': bool(getattr(role, 'is_admin', False)) if role else False,
            'is_manager': bool(getattr(role, 'is_manager', False)) if role else False,
            'is_individual': bool(getattr(role, 'is_individual', False)) if role else False,
        },
        'is_superuser': bool(user.is_superuser),
    }
    api.force_authenticate(user=user, token=claims)
    api.credentials(HTTP_X_CLIENT_ID=str(tenant_id))
    return api


@pytest.mark.django_db
def test_department_edit_with_empty_email_keeps_null(contact_of_a, user_a, client_account_a):
    """PATCH the contact (form re-sends email="") -> column must stay NULL."""
    assert contact_of_a.email is None
    api = _auth(user_a, client_account_a.id)

    resp = api.patch(
        f'/contacts/{contact_of_a.id}/',
        {'email': '', 'job_title': 'Head of Ops'},
        format='json',
    )

    assert resp.status_code == 200, resp.data
    contact_of_a.refresh_from_db()
    assert contact_of_a.email is None


@pytest.mark.django_db
def test_department_edit_with_empty_phone_keeps_null(contact_of_a, user_a, client_account_a):
    """Same guarantee for phone_number on the edit path."""
    api = _auth(user_a, client_account_a.id)

    resp = api.patch(
        f'/contacts/{contact_of_a.id}/',
        {'email': '', 'phone_number': ''},
        format='json',
    )

    assert resp.status_code == 200, resp.data
    contact_of_a.refresh_from_db()
    assert contact_of_a.email is None
    assert contact_of_a.phone_number in (None, '')
    assert not contact_of_a.phone_number  # normalized to NULL


@pytest.mark.django_db
def test_opt_out_keeps_email_null(contact_of_a, user_a, client_account_a):
    """Control path: opt-out never touches email; it must remain NULL."""
    assert contact_of_a.email is None
    api = _auth(user_a, client_account_a.id)

    resp = api.post(f'/contacts/{contact_of_a.id}/mark-opted-out/')

    assert resp.status_code == 200, resp.data
    contact_of_a.refresh_from_db()
    assert contact_of_a.email is None


@pytest.mark.django_db
def test_create_with_empty_email_and_phone_stores_null(account_owned_by_a, user_a, client_account_a):
    """POST create with empty email/phone stores NULL, not ''."""
    api = _auth(user_a, client_account_a.id)

    resp = api.post(
        '/contacts/',
        {
            'first_name': 'E', 'last_name': 'Mpty',
            'account_id': str(account_owned_by_a.id),
            'email': '', 'phone_number': '',
        },
        format='json',
    )

    assert resp.status_code == 201, resp.data
    from app_modules.contacts.models import Contact
    c = Contact.objects.get(id=resp.data['id'])
    assert c.email is None
    assert c.phone_number is None


@pytest.mark.django_db
def test_two_empty_email_contacts_same_account_do_not_collide(account_owned_by_a, user_a, client_account_a):
    """End goal: two empty-email contacts in one account no longer collide."""
    api = _auth(user_a, client_account_a.id)
    payload = lambda fn: {
        'first_name': fn, 'last_name': 'X',
        'account_id': str(account_owned_by_a.id), 'email': '',
    }

    r1 = api.post('/contacts/', payload('A'), format='json')
    r2 = api.post('/contacts/', payload('B'), format='json')

    assert r1.status_code == 201, r1.data
    assert r2.status_code == 201, r2.data  # would be 409 if '' were stored
