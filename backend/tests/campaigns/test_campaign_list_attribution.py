# backend/tests/campaigns/test_campaign_list_attribution.py
"""
Serializer-exposure tests for the Campaign list attribution block.

The campaign card renders an attribution block — owner + team and
executor + team ("Name — TEAM") — mirroring the Territory card's owner+team.
CampaignListSerializer previously exposed only `owner_name` (a flat string),
so the owner's team, the executor, and the executor's team were absent from
the list payload. These tests pin the newly exposed fields:

- owner  -> {id, full_name}          (mirrors TerritoryListSerializer.get_owner)
- owner_team -> {id, name} | None    (mirrors TerritoryListSerializer.get_team)
- executor -> {id, full_name} | None (null when it defaults to the owner)
- executor_team -> {id, name} | None

The list queryset select_related's owner__team / executor__team; the card
consumes these directly (executor line shown only when executor differs from
the owner).
"""

import pytest

URL = '/campaigns/'


def _rows(resp):
    """Unwrap the (possibly double-enveloped, paginated) list payload."""
    body = resp.data
    data = body['data'] if isinstance(body, dict) and 'data' in body else body
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def _row_for(resp, campaign_id):
    for row in _rows(resp):
        if str(row['id']) == str(campaign_id):
            return row
    raise AssertionError(f'campaign {campaign_id} not found in list payload')


def _mk_team(client_account, name):
    from end_users.models.team import Team
    return Team.objects.create(name=name, client_account=client_account)


@pytest.mark.django_db
def test_owner_and_team_exposed_executor_absent(
    authed_api_a, user_a, client_account_a, campaign
):
    """Owner + team are exposed; executor (unset) and its team are None."""
    user_a.first_name = 'Paul'
    user_a.last_name = 'DUPONT'
    user_a.team = _mk_team(client_account_a, 'SALES EMEA')
    user_a.save()

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    row = _row_for(resp, campaign.id)

    assert row['owner'] == {'id': str(user_a.id), 'full_name': 'Paul DUPONT'}
    assert row['owner_team'] == {'id': str(user_a.team_id), 'name': 'SALES EMEA'}
    # Executor defaults to the owner -> stored NULL -> not surfaced as attribution.
    assert row['executor'] is None
    assert row['executor_team'] is None


@pytest.mark.django_db
def test_executor_and_team_exposed_when_set(
    authed_api_a, user_a, client_account_a, role_individual_a, campaign
):
    """A distinct executor with its own team is surfaced separately from the owner."""
    from end_users.models import User

    user_a.first_name = 'Paul'
    user_a.last_name = 'DUPONT'
    user_a.team = _mk_team(client_account_a, 'SALES EMEA')
    user_a.save()

    executor = User.objects.create(
        email='sdr-a@tenant-a.test',
        first_name='Jacques',
        last_name='PAUL',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
        team=_mk_team(client_account_a, 'SDR EMEA'),
    )
    campaign.executor = executor
    campaign.save(user=user_a, client_id=client_account_a.id)

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    row = _row_for(resp, campaign.id)

    assert row['owner']['full_name'] == 'Paul DUPONT'
    assert row['executor'] == {'id': str(executor.id), 'full_name': 'Jacques PAUL'}
    assert row['executor_team'] == {'id': str(executor.team_id), 'name': 'SDR EMEA'}
    # Executor is a different person than the owner (card renders both lines).
    assert row['executor']['id'] != row['owner']['id']
