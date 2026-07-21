# backend/tests/territories/test_workspace_parity.py
"""
Workspace endpoint parity after the inline -> service migration.

The workspace stats endpoint (/territories/{id}/workspace/) now delegates its
counts to the same services the batched endpoint uses. These tests lock the
response contract and prove the migration carries the opted_out fix into the
workspace view (a CONTACT territory) and stays correct for ACCOUNT territories.
"""

import pytest

from ._builders import mk_account, mk_contact, mk_territory


def _stats(resp):
    body = resp.data
    payload = body['data'] if isinstance(body, dict) and 'data' in body else body
    return payload['stats']


@pytest.mark.django_db
def test_contact_workspace_applies_opted_out(authed_api_a, user_a, client_account_a):
    terr = mk_territory(user_a, client_account_a, {'opted_out': False},
                        ttype='CONTACT')
    acc = mk_account('Acme', user_a, client_account_a)
    mk_contact(acc, user_a, client_account_a, opted_out=False)
    mk_contact(acc, user_a, client_account_a, opted_out=False)
    mk_contact(acc, user_a, client_account_a, opted_out=True)  # now excluded

    resp = authed_api_a.get(f'/territories/{terr.id}/workspace/')
    assert resp.status_code == 200
    assert _stats(resp)['contacts_count'] == 2


@pytest.mark.django_db
def test_account_workspace_counts_match_filter(authed_api_a, user_a, client_account_a):
    terr = mk_territory(user_a, client_account_a, {'classification': 'SMB'},
                        ttype='ACCOUNT')
    mk_account('SMB1', user_a, client_account_a)
    mk_account('SMB2', user_a, client_account_a)
    from app_modules.accounts.models import AccountClassification
    mk_account('ENT', user_a, client_account_a,
               classification=AccountClassification.ENTERPRISE)

    resp = authed_api_a.get(f'/territories/{terr.id}/workspace/')
    assert resp.status_code == 200
    assert _stats(resp)['accounts_count'] == 2
