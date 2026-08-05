# backend/tests/campaigns/test_enroll_strict_derivation.py
"""
enroll-target derives `strict` on the server (the frontend no longer sends it):

    strict = (enroll_type == 'CONTACT') and (base_qs.count() == 1)

It is exposed in the response body (both exits) purely so the messaging layer
(E6) can pick singular vs plural wording. It decides NOTHING: the set of
enrolled contacts is unchanged, and no R3 case returns HTTP 400 — every case is
a 200/201 success carrying the cause counters.

Real endpoint, Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from app_modules.campaigns.constants import CampaignStatus, CampaignType
from app_modules.campaigns.models import Campaign
from app_modules.contacts.models import Contact

ENROLL_URL = "/campaigns/accounts/enroll-target/"


def _campaign(account, user_a):
    today = timezone.now().date()
    c = Campaign(
        name="E5", campaign_type=CampaignType.TARGETED, status=CampaignStatus.ACTIVE,
        owner=user_a, planned_start_date=today, planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


def _mk(account, user_a, *, email=None, phone=None, linkedin=None, opted_out=False):
    c = Contact(account=account, first_name="C", last_name="X", opted_out=opted_out)
    c.save(user=user_a, client_id=account.client_id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE module_contacts SET email=%s, phone_number=%s, linkedin=%s WHERE id=%s",
            [email, phone, linkedin, str(c.id)],
        )
    return c


def _post(api, campaign, account, *, enroll_type, contact_ids=None, department_id=None):
    data = {"campaign_id": str(campaign.id), "account_id": str(account.id), "type": enroll_type}
    if contact_ids is not None:
        data["contact_ids"] = contact_ids
    if department_id is not None:
        data["department_id"] = department_id
    return api.post(ENROLL_URL, data=data, format="json")


def _body(resp):
    return resp.data.get("data", resp.data)


@pytest.mark.django_db
class TestStrictDerivation:

    def test_contact_single_real_contact_is_strict(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        ct = _mk(account, user_a, email="a@x.io")
        resp = _post(authed_api_a, c, account, enroll_type="CONTACT", contact_ids=[str(ct.id)])
        assert resp.status_code in (200, 201)
        assert _body(resp)["strict"] is True

    def test_contact_single_unreachable_is_strict_and_no_400(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        ct = _mk(account, user_a, email=None, phone=None)  # no channel
        resp = _post(authed_api_a, c, account, enroll_type="CONTACT", contact_ids=[str(ct.id)])
        assert resp.status_code in (200, 201)  # NOT 400
        b = _body(resp)
        assert b["strict"] is True
        assert b["contacts_enrolled"] == 0
        assert b["no_channel_count"] == 1  # cause carried by counters

    def test_contact_two_contacts_is_not_strict(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        c1 = _mk(account, user_a, email="a@x.io")
        c2 = _mk(account, user_a, email="b@x.io")
        resp = _post(authed_api_a, c, account, enroll_type="CONTACT",
                     contact_ids=[str(c1.id), str(c2.id)])
        assert resp.status_code in (200, 201)
        assert _body(resp)["strict"] is False

    def test_account_mode_is_not_strict_even_with_one_contact(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        _mk(account, user_a, email="a@x.io")
        resp = _post(authed_api_a, c, account, enroll_type="ACCOUNT", contact_ids=[])
        assert resp.status_code in (200, 201)
        assert _body(resp)["strict"] is False

    def test_department_mode_is_not_strict(self, authed_api_a, account, user_a):
        from app_modules.core_modules.models.standar_dept import StandardDepartment
        dept, _ = StandardDepartment.objects.get_or_create(name="IT")
        c = _campaign(account, user_a)
        ct = _mk(account, user_a, email="a@x.io")
        ct.standard_department = dept
        ct.save(user=user_a)
        resp = _post(authed_api_a, c, account, enroll_type="DEPARTMENT", department_id=str(dept.id))
        assert resp.status_code in (200, 201)
        assert _body(resp)["strict"] is False

    def test_contact_single_nonexistent_id_is_not_strict(self, authed_api_a, account, user_a):
        import uuid
        c = _campaign(account, user_a)
        resp = _post(authed_api_a, c, account, enroll_type="CONTACT",
                     contact_ids=[str(uuid.uuid4())])  # no such contact -> base_qs.count()==0
        assert resp.status_code in (200, 201)
        assert _body(resp)["strict"] is False
