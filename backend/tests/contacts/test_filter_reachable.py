# backend/tests/contacts/test_filter_reachable.py
"""
Tests for ``Contact.filter_reachable`` — the single source of the enrollment
"reachable channel" predicate.

Scope: channel presence ONLY. ``opted_out`` is NOT handled by
``filter_reachable`` (it stays at each call site) and is therefore not
exercised here.

The exact DB column values (SQL NULL vs empty string) are written via raw SQL,
so the ``''`` / ``NULL`` distinction the predicate depends on is reproduced
deterministically, independent of any ``PhoneNumberField`` coercion.

Reachability rule (E2): a contact is reachable when email OR phone OR linkedin
is present (non-NULL and non-empty). The earlier ``email='' + phone=NULL`` SQL
debt is fixed: the exclude now spans all three channels, so a row with only
empty/NULL channels is correctly excluded. EMAIL_ONLY stays strictly email —
LinkedIn does not count there.
"""
import itertools

import pytest
from django.db import connection

from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact

_counter = itertools.count(1)

_LINKEDIN = 'https://linkedin.com/in/test'


def _mk(client_account_a, user_a, *, email, phone, linkedin=None):
    """
    Create a Contact whose ``email`` / ``phone_number`` / ``linkedin`` columns
    hold EXACTLY the given values (``None`` -> SQL NULL, ``''`` -> empty string,
    ``str`` -> literal), each in its own account to sidestep the
    ``(account, email)`` unique constraint.
    """
    acc = CompanyAccount(company_name=f'Acc-{next(_counter)}', account_owner=user_a)
    acc.save(user=user_a, client_id=client_account_a.id)
    c = Contact(account=acc, first_name='T', last_name='C')
    c.save(user=user_a, client_id=client_account_a.id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE module_contacts SET email=%s, phone_number=%s, linkedin=%s WHERE id=%s",
            [email, phone, linkedin, str(c.id)],
        )
    return c


def _reachable_ids(pks, email_only=False):
    qs = Contact.objects.filter(pk__in=pks)
    return set(
        Contact.filter_reachable(qs, email_only=email_only).values_list('id', flat=True)
    )


@pytest.mark.django_db
class TestFilterReachableDefault:
    """email_only=False -> reachable when email OR phone OR linkedin is present."""

    def test_email_only_present_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='a@b.io', phone=None)
        assert _reachable_ids([c.id]) == {c.id}

    def test_phone_only_present_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email=None, phone='+14155552671')
        assert _reachable_ids([c.id]) == {c.id}

    def test_both_present_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='a@b.io', phone='+14155552671')
        assert _reachable_ids([c.id]) == {c.id}

    # ---- LinkedIn as a channel (E2) --------------------------------------

    def test_linkedin_only_present_passes(self, client_account_a, user_a):
        """Core of E2: LinkedIn alone (no email, no phone) is now reachable."""
        c = _mk(client_account_a, user_a, email=None, phone=None, linkedin=_LINKEDIN)
        assert _reachable_ids([c.id]) == {c.id}

    def test_email_and_linkedin_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='a@b.io', phone=None, linkedin=_LINKEDIN)
        assert _reachable_ids([c.id]) == {c.id}

    def test_phone_and_linkedin_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email=None, phone='+14155552671', linkedin=_LINKEDIN)
        assert _reachable_ids([c.id]) == {c.id}

    def test_linkedin_empty_string_only_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email=None, phone=None, linkedin='')
        assert _reachable_ids([c.id]) == set()

    # ---- No channel -> excluded ------------------------------------------

    def test_all_null_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email=None, phone=None, linkedin=None)
        assert _reachable_ids([c.id]) == set()

    def test_all_empty_string_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='', phone='', linkedin='')
        assert _reachable_ids([c.id]) == set()

    # ---- Former SQL debt, now FIXED (E2) ---------------------------------

    def test_fixed_empty_email_null_phone_excluded(self, client_account_a, user_a):
        """E2 fix: email='' + phone=NULL (no linkedin) is now correctly EXCLUDED."""
        c = _mk(client_account_a, user_a, email='', phone=None, linkedin=None)
        assert _reachable_ids([c.id]) == set()

    def test_fixed_null_email_empty_phone_excluded(self, client_account_a, user_a):
        """E2 fix: mirror — email=NULL + phone='' (no linkedin) is now EXCLUDED."""
        c = _mk(client_account_a, user_a, email=None, phone='', linkedin=None)
        assert _reachable_ids([c.id]) == set()

    def test_mixed_set_returns_only_reachable(self, client_account_a, user_a):
        """A mixed queryset returns exactly the reachable subset (incl. LinkedIn-only)."""
        ok_email = _mk(client_account_a, user_a, email='a@b.io', phone=None)
        ok_linkedin = _mk(client_account_a, user_a, email=None, phone=None, linkedin=_LINKEDIN)
        ko = _mk(client_account_a, user_a, email=None, phone=None, linkedin=None)
        assert _reachable_ids([ok_email.id, ok_linkedin.id, ko.id]) == {ok_email.id, ok_linkedin.id}


@pytest.mark.django_db
class TestFilterReachableEmailOnly:
    """email_only=True -> reachable when email is present. LinkedIn does NOT count."""

    def test_email_present_passes(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='a@b.io', phone=None)
        assert _reachable_ids([c.id], email_only=True) == {c.id}

    def test_phone_only_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email=None, phone='+14155552671')
        assert _reachable_ids([c.id], email_only=True) == set()

    def test_email_empty_string_excluded(self, client_account_a, user_a):
        c = _mk(client_account_a, user_a, email='', phone=None)
        assert _reachable_ids([c.id], email_only=True) == set()

    def test_linkedin_only_excluded(self, client_account_a, user_a):
        """EMAIL_ONLY is strictly email — LinkedIn-only stays excluded (E2 must not leak here)."""
        c = _mk(client_account_a, user_a, email=None, phone=None, linkedin=_LINKEDIN)
        assert _reachable_ids([c.id], email_only=True) == set()
