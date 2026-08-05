# backend/tests/contacts/test_filter_reachable.py
"""
Characterization tests for ``Contact.filter_reachable`` — the single source of
the enrollment "reachable channel" predicate (E1 socle).

They pin the CURRENT behaviour before the six duplicated call sites are swapped
onto this method, so any drift during the refactor turns red.

Scope: channel presence ONLY. ``opted_out`` is NOT handled by
``filter_reachable`` (it stays at each call site) and is therefore not
exercised here.

The exact DB column values (SQL NULL vs empty string) are written via raw SQL,
so the ``''`` / ``NULL`` distinction the predicate depends on is reproduced
deterministically, independent of any ``PhoneNumberField`` coercion.

Documented debt (preserved verbatim, revisited in E2): a contact with
``email='' + phone_number=NULL`` (and its mirror ``email=NULL + phone_number=''``)
is treated as REACHABLE, because ``.exclude(Q(email='') & Q(phone_number=''))``
never matches when one side is NULL (``NULL = ''`` is NULL in SQL).
"""
import itertools

import pytest
from django.db import connection

from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact

_counter = itertools.count(1)


def _mk(client_account_a, user_a, *, email, phone):
    """
    Create a Contact whose ``email`` / ``phone_number`` columns hold EXACTLY the
    given values (``None`` -> SQL NULL, ``''`` -> empty string, ``str`` ->
    literal), each in its own account to sidestep the ``(account, email)``
    unique constraint.
    """
    acc = CompanyAccount(company_name=f'Acc-{next(_counter)}', account_owner=user_a)
    acc.save(user=user_a, client_id=client_account_a.id)
    c = Contact(account=acc, first_name='T', last_name='C')
    c.save(user=user_a, client_id=client_account_a.id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE module_contacts SET email=%s, phone_number=%s WHERE id=%s",
            [email, phone, str(c.id)],
        )
    return c


def _reachable_ids(pks, email_only=False):
    qs = Contact.objects.filter(pk__in=pks)
    return set(
        Contact.filter_reachable(qs, email_only=email_only).values_list('id', flat=True)
    )


@pytest.mark.django_db
class TestFilterReachableDefault:
    """email_only=False -> reachable when email OR phone is present."""

    def test_email_only_present_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='a@b.io', phone=None)
        assert _reachable_ids([c.id]) == {c.id}

    def test_phone_only_present_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email=None, phone='+14155552671')
        assert _reachable_ids([c.id]) == {c.id}

    def test_both_present_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='a@b.io', phone='+14155552671')
        assert _reachable_ids([c.id]) == {c.id}

    def test_both_null_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email=None, phone=None)
        assert _reachable_ids([c.id]) == set()

    def test_both_empty_string_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='', phone='')
        assert _reachable_ids([c.id]) == set()

    def test_debt_empty_email_null_phone_passes(self, client_account_a, user_a):
        """DEBT (revisited in E2): email='' + phone=NULL is treated as reachable."""
        c = _mk(client_account_a, user_a, email='', phone=None)
        assert _reachable_ids([c.id]) == {c.id}

    def test_debt_null_email_empty_phone_passes(self, client_account_a, user_a):
        """DEBT (revisited in E2): mirror — email=NULL + phone='' is treated as reachable."""
        c = _mk(client_account_a, user_a, email=None, phone='')
        assert _reachable_ids([c.id]) == {c.id}

    def test_mixed_set_returns_only_reachable(self, client_account_a, user_a):
        """A mixed queryset returns exactly the reachable subset."""
        ok = _mk(client_account_a, user_a, email='a@b.io', phone=None)
        ko = _mk(client_account_a, user_a, email=None, phone=None)
        assert _reachable_ids([ok.id, ko.id]) == {ok.id}


@pytest.mark.django_db
class TestFilterReachableEmailOnly:
    """email_only=True -> reachable when email is present (mirrors #5/#6)."""

    def test_email_present_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='a@b.io', phone=None)
        assert _reachable_ids([c.id], email_only=True) == {c.id}

    def test_phone_only_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email=None, phone='+14155552671')
        assert _reachable_ids([c.id], email_only=True) == set()

    def test_email_empty_string_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='', phone=None)
        assert _reachable_ids([c.id], email_only=True) == set()
