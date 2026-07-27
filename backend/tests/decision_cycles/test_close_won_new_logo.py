# backend/tests/decision_cycles/test_close_won_new_logo.py
"""
Close-won → new-logo conversion on the account.

Winning a decision cycle converts a PROSPECT account to CLIENT and stamps
``became_client_at`` once. An account already CLIENT (e.g. imported from the
client's existing base) is never converted or re-stamped — it must not be
counted as a new logo. The effect is server-side in the close hook, not a user
edit; it is idempotent across repeated wins.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.accounts.models import AccountType, CompanyAccount
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle


def _mk_account(user, ca, *, type=AccountType.PROSPECT, name='Acc'):
    acc = CompanyAccount(company_name=name, type=type, has_buying_decision=True,
                         account_owner=user)
    acc.save(user=user, client_id=ca.id)
    return acc


def _mk_cycle(user, account, ca, name='dc'):
    dc = DecisionCycle(account=account, owner=user, name=name)
    dc.save(user=user, client_id=ca.id)
    return dc


def _close_won(api_client, cycle):
    return api_client.post(
        f'/decision_cycles/{cycle.id}/close/',
        {'outcome': CycleOutcome.WON}, format='json',
    )


@pytest.mark.django_db
class TestCloseWonNewLogo:

    def test_prospect_becomes_client_and_stamped(self, authed_api_a, user_a, client_account_a):
        acc = _mk_account(user_a, client_account_a, type=AccountType.PROSPECT)
        cycle = _mk_cycle(user_a, acc, client_account_a)

        resp = _close_won(authed_api_a, cycle)
        assert resp.status_code == 200, resp.content

        acc.refresh_from_db()
        assert acc.type == AccountType.CLIENT
        assert acc.became_client_at is not None

    def test_already_client_untouched(self, authed_api_a, user_a, client_account_a):
        # THE integration rule: an imported CLIENT is never a new logo.
        acc = _mk_account(user_a, client_account_a, type=AccountType.CLIENT)
        assert acc.became_client_at is None
        cycle = _mk_cycle(user_a, acc, client_account_a)

        resp = _close_won(authed_api_a, cycle)
        assert resp.status_code == 200, resp.content

        acc.refresh_from_db()
        assert acc.type == AccountType.CLIENT          # unchanged
        assert acc.became_client_at is None            # NOT stamped

    def test_idempotent_second_win_keeps_first_date(self, authed_api_a, user_a, client_account_a):
        acc = _mk_account(user_a, client_account_a, type=AccountType.PROSPECT)
        cycle1 = _mk_cycle(user_a, acc, client_account_a, name='dc1')
        cycle2 = _mk_cycle(user_a, acc, client_account_a, name='dc2')

        assert _close_won(authed_api_a, cycle1).status_code == 200
        acc.refresh_from_db()
        first_date = acc.became_client_at
        assert first_date is not None
        assert acc.type == AccountType.CLIENT

        # Second win on the same (now CLIENT) account: nothing changes.
        assert _close_won(authed_api_a, cycle2).status_code == 200
        acc.refresh_from_db()
        assert acc.became_client_at == first_date      # not moved
        assert acc.type == AccountType.CLIENT

    def test_no_write_on_get(self, authed_api_a, user_a, client_account_a):
        # A GET of the cycle must never convert the account.
        acc = _mk_account(user_a, client_account_a, type=AccountType.PROSPECT)
        cycle = _mk_cycle(user_a, acc, client_account_a)
        resp = authed_api_a.get(f'/decision_cycles/{cycle.id}/')
        assert resp.status_code == 200
        acc.refresh_from_db()
        assert acc.type == AccountType.PROSPECT
        assert acc.became_client_at is None
