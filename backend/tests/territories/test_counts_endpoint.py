# backend/tests/territories/test_counts_endpoint.py
"""
Endpoint tests for POST /territories/counts/ (the batched counts endpoint).

Proves:
- per-territory counts are returned in one round-trip, keyed by id, with the
  right type (ACCOUNT -> accounts, CONTACT -> contacts);
- ids that do not exist in the tenant are silently omitted from the map
  (200, not an error) — including a cross-tenant id, which is the isolation
  boundary (territory read scope is client-wide, so an in-tenant id is never
  a 403; an out-of-tenant id is simply not found);
- empty ids -> 400, and an over-cap request (> MAX_COUNTS_IDS) -> 400.

Note on 403: territory `read` scope is 'client' for every tier
(permissions/registry/territories_registry.py), so no in-tenant territory is
ever out of a caller's scope; get_objects_for_bulk's 403 path is therefore
unreachable for territory reads and is not asserted here. Cross-tenant
isolation is covered instead.
"""

import uuid

import pytest

from app_modules.accounts.models import AccountClassification

from ._builders import mk_account, mk_contact, mk_territory

URL = '/territories/counts/'


def _data(resp):
    """Unwrap the response payload's data map."""
    body = resp.data
    return body['data'] if isinstance(body, dict) and 'data' in body else body


@pytest.mark.django_db
def test_returns_per_territory_counts(authed_api_a, user_a, client_account_a):
    acc_terr = mk_territory(user_a, client_account_a, {'classification': 'SMB'},
                            ttype='ACCOUNT')
    mk_account('SMB1', user_a, client_account_a)
    mk_account('SMB2', user_a, client_account_a)

    contact_terr = mk_territory(user_a, client_account_a, {'opted_out': False},
                                ttype='CONTACT')
    # ENTERPRISE so this account is not itself counted by the SMB territory above.
    acc = mk_account('Acme', user_a, client_account_a,
                     classification=AccountClassification.ENTERPRISE)
    mk_contact(acc, user_a, client_account_a, opted_out=False)
    mk_contact(acc, user_a, client_account_a, opted_out=False)
    mk_contact(acc, user_a, client_account_a, opted_out=True)  # excluded

    resp = authed_api_a.post(URL, {'ids': [str(acc_terr.id), str(contact_terr.id)]},
                             format='json')
    assert resp.status_code == 200
    data = _data(resp)

    assert data[str(acc_terr.id)] == {'type': 'ACCOUNT', 'count': 2}
    assert data[str(contact_terr.id)] == {'type': 'CONTACT', 'count': 2}


@pytest.mark.django_db
def test_not_found_id_is_omitted(authed_api_a, user_a, client_account_a):
    terr = mk_territory(user_a, client_account_a, {'classification': 'SMB'})
    mk_account('SMB1', user_a, client_account_a)
    ghost = str(uuid.uuid4())

    resp = authed_api_a.post(URL, {'ids': [str(terr.id), ghost]}, format='json')
    assert resp.status_code == 200
    data = _data(resp)

    assert str(terr.id) in data
    assert data[str(terr.id)]['count'] == 1
    assert ghost not in data


@pytest.mark.django_db
def test_cross_tenant_id_is_isolated(
    authed_api_a, user_a, client_account_a, user_b, client_account_b
):
    """A tenant-B territory requested by a tenant-A caller is not found in the
    tenant and is omitted — no count leaks across tenants."""
    terr_a = mk_territory(user_a, client_account_a, {'classification': 'SMB'})
    mk_account('A1', user_a, client_account_a)

    terr_b = mk_territory(user_b, client_account_b, {'classification': 'SMB'})
    mk_account('B1', user_b, client_account_b)

    resp = authed_api_a.post(URL, {'ids': [str(terr_a.id), str(terr_b.id)]},
                             format='json')
    assert resp.status_code == 200
    data = _data(resp)

    assert str(terr_a.id) in data
    assert str(terr_b.id) not in data


@pytest.mark.django_db
def test_empty_ids_returns_400(authed_api_a):
    resp = authed_api_a.post(URL, {'ids': []}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_over_cap_returns_400(authed_api_a):
    ids = [str(uuid.uuid4()) for _ in range(101)]
    resp = authed_api_a.post(URL, {'ids': ids}, format='json')
    assert resp.status_code == 400
