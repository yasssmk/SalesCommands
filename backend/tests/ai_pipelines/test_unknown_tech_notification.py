# backend/tests/ai_pipelines/test_unknown_tech_notification.py
"""
Emitter test: the unknown-technology notification (E4) is DORMANT since S10.

Original contract
-----------------
`_maybe_notify_unknown_tech` fanned one notification out to every active
tenant admin whenever the LLM produced a TechStackSignal it could not
match to the tenant's TechCatalog (PENDING + LLM_EXTRACTED + null FK).
A catalog-matched tech notified nobody.

Why it is dormant (S10 sub-step 2)
----------------------------------
The extraction path no longer performs any catalogue match, so
`tech_catalog_entry_id is None` now holds for EVERY extracted tech
signal. Left as-is, the emitter would notify every admin about every
tool mentioned on every call. "Unknown" lost its meaning along with the
catalogue lookup, so the helper returns before emitting anything.

These tests lock that in, so the emitter cannot come back to life by
accident before sub-step 5 deletes it. If the product later wants a
"new tool seen on this account" notification, it is a NEW emitter keyed
on the normalised tech name — and it gets its own tests.

The non-raising contract is still asserted: the persist loop swallows
per-signal exceptions, so this helper must never propagate one.

TODO(S10 sub-step 5): delete this file together with
_maybe_notify_unknown_tech, its call site in persist_stage() and
NotificationCategory.UNKNOWN_TECH_DETECTED.
"""

import pytest

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import TechStackSignal
from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)
from app_modules.notifications.models import Notification, NotificationCategory


# =============================================================================
# FIXTURES — two active admins on tenant A
# =============================================================================

@pytest.fixture
def role_admin_a(db, client_account_a):
    from end_users.models import UserRole
    # The Admin role (is_admin=True) is auto-created by the
    # create_default_roles signal on ClientAccount creation.
    return UserRole.objects.get(client_account=client_account_a, name='Admin')


@pytest.fixture
def admins_a(db, client_account_a, role_admin_a):
    from end_users.models import User
    return [
        User.objects.create(
            email=f'admin{i}@tenant-a.test',
            client_account=client_account_a,
            role=role_admin_a,
            is_active=True,
        )
        for i in range(2)
    ]


# =============================================================================
# HELPERS
# =============================================================================

def _make_extracted_tech(account, activity, user, tech_name='FooDB'):
    """
    A PENDING, LLM-extracted TechStack on the S10 contract: raw name on
    the column, no catalogue FK. Under the OLD rule this shape was
    exactly the "unknown tech" trigger.
    """
    sig = TechStackSignal(
        account=account,
        source_activity=activity,
        tech_catalog_entry=None,
        tech_name=tech_name,
        source=SignalSource.LLM_EXTRACTED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _unknown_tech_qs():
    return Notification.objects.filter(
        category=NotificationCategory.UNKNOWN_TECH_DETECTED
    )


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.django_db(transaction=True)
def test_extracted_tech_notifies_nobody(
    account, activity, user_a, client_account_a, admins_a,
):
    """
    The emitter is dormant: the shape that used to fan out to every admin
    now emits nothing. Without this guard, every tool on every call would
    notify every admin.
    """
    signal = _make_extracted_tech(account, activity, user_a)
    assert signal.status == SignalStatus.PENDING
    assert signal.tech_catalog_entry_id is None

    TranscriptSignalExtractor()._maybe_notify_unknown_tech(
        signal, client_account_a.id,
    )

    assert _unknown_tech_qs().count() == 0


@pytest.mark.django_db(transaction=True)
def test_no_notification_for_any_number_of_techs(
    account, activity, user_a, client_account_a, admins_a,
):
    """A whole transcript's worth of tools stays silent."""
    for name in ('Salesforce', 'HubSpot', 'Slack', 'Notion'):
        signal = _make_extracted_tech(account, activity, user_a, tech_name=name)
        TranscriptSignalExtractor()._maybe_notify_unknown_tech(
            signal, client_account_a.id,
        )

    assert _unknown_tech_qs().count() == 0
    assert Notification.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_helper_is_non_raising_and_signal_survives(
    account, activity, user_a, client_account_a, admins_a, monkeypatch,
):
    """
    The non-raising contract holds. persist_stage() swallows per-signal
    exceptions, so a notification failure must never make an
    already-extracted signal disappear — asserted here with emit()
    rigged to explode, which the dormant guard means we never reach.
    """
    signal = _make_extracted_tech(account, activity, user_a)

    def _boom(*args, **kwargs):
        raise RuntimeError('emit exploded')

    monkeypatch.setattr(
        'app_modules.ai_pipelines.services.transcript_signal_extractor.'
        'NotificationService.emit',
        _boom,
    )

    # Must not raise.
    TranscriptSignalExtractor()._maybe_notify_unknown_tech(
        signal, client_account_a.id,
    )

    assert _unknown_tech_qs().count() == 0
    assert TechStackSignal.objects.filter(id=signal.id).exists()
