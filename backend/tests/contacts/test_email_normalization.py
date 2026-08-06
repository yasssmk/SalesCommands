"""
Empty-string -> NULL normalization on Contact writes, exercised through the real
write paths (not a convenient save()-only shortcut).

Root cause of the recurring unique-constraint collision on
(account, email, client_id): a contact edit that carries email="" in its payload
rewrites the column to '' instead of NULL. PostgreSQL allows many NULLs but only
one '' per scope, so the '' reintroduces the collision. Contact.save() normalizes
email and phone_number '' -> NULL, and every write path funnels through save().

Covers the two observed edit paths (department change via the serializer, opt-out
via the action) plus creation, and guards that a real value is preserved.
"""

import pytest

from app_modules.contacts.models import Contact
from app_modules.contacts.serializers import ContactSerializer


@pytest.mark.django_db
def test_department_edit_with_empty_email_stays_null(contact_of_a):
    """Department-change edit: the form re-sends email="" -> must persist as NULL."""
    assert contact_of_a.email is None

    # Mirrors ContactViewSet.update -> ContactSerializer.update: the front submits
    # the whole form (email empty) while changing another field.
    ContactSerializer(context={'request': None}).update(
        contact_of_a, {'email': '', 'job_title': 'Head of Ops'}
    )

    contact_of_a.refresh_from_db()
    assert contact_of_a.email is None


@pytest.mark.django_db
def test_opt_out_keeps_email_null(contact_of_a):
    """Opt-out action never touches email; it must remain NULL."""
    assert contact_of_a.email is None

    contact_of_a.mark_opted_out(user=None)

    contact_of_a.refresh_from_db()
    assert contact_of_a.email is None


@pytest.mark.django_db
def test_create_with_empty_email_and_phone_stores_null(account_owned_by_a, user_a):
    """Creation with empty email/phone stores NULL, not ''."""
    c = Contact(
        account=account_owned_by_a,
        first_name='E', last_name='Mpty',
        email='', phone_number='',
    )
    c.save(user=user_a, client_id=account_owned_by_a.client_id)

    c.refresh_from_db()
    assert c.email is None
    assert c.phone_number is None


@pytest.mark.django_db
def test_two_empty_email_contacts_same_account_do_not_collide(account_owned_by_a, user_a):
    """The end goal: two empty-email contacts in one account no longer collide."""
    cid = account_owned_by_a.client_id
    a = Contact(account=account_owned_by_a, first_name='A', last_name='X', email='')
    a.save(user=user_a, client_id=cid)
    b = Contact(account=account_owned_by_a, first_name='B', last_name='Y', email='')
    b.save(user=user_a, client_id=cid)  # would raise IntegrityError if '' were stored

    a.refresh_from_db()
    b.refresh_from_db()
    assert a.email is None and b.email is None


@pytest.mark.django_db
def test_real_email_is_preserved(account_owned_by_a, user_a):
    c = Contact(
        account=account_owned_by_a,
        first_name='R', last_name='eal',
        email='real@example.com',
    )
    c.save(user=user_a, client_id=account_owned_by_a.client_id)

    c.refresh_from_db()
    assert c.email == 'real@example.com'
