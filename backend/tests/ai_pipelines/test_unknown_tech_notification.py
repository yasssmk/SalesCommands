# backend/tests/ai_pipelines/test_unknown_tech_notification.py
"""
Emitter test: a newly-detected unknown technology notifies tenant admins (E4).

Exercises TranscriptSignalExtractor._maybe_notify_unknown_tech directly with
persisted TechStackSignals. transaction=True so transaction.on_commit runs
(with no wrapping atomic block the callback fires immediately on the
autocommit save).

Covers:
  - unknown tech (PENDING, LLM-extracted, null catalog) -> one notification
    per active admin (fan-out);
  - a catalog-matched tech -> no notification;
  - a raising NotificationService.emit never propagates: the extracted
    signal still exists (the non-raising contract).
"""

import pytest

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import TechStackSignal
from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)
from app_modules.notifications.models import Notification, NotificationCategory


# =============================================================================
# FIXTURES — two active admins + one non-admin on tenant A
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

def _make_unknown_tech(account, activity, user):
    """A PENDING, LLM-extracted TechStack with no catalog match."""
    sig = TechStackSignal(
        account=account,
        source_activity=activity,
        tech_catalog_entry=None,
        source=SignalSource.LLM_EXTRACTED,
        metadata={'pending_tech_name': 'FooDB'},
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _make_matched_tech(account, activity, user):
    """A TechStack matched to a catalog entry (no notification expected)."""
    from app_modules.tech_catalog.models import TechCatalog
    entry = TechCatalog(company_name='Salesforce', product_name='Sales Cloud')
    entry.save(user=user, client_id=account.client_id)
    sig = TechStackSignal(
        account=account,
        source_activity=activity,
        tech_catalog_entry=entry,
        source=SignalSource.LLM_EXTRACTED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _unknown_tech_qs():
    return Notification.objects.filter(category=NotificationCategory.UNKNOWN_TECH_DETECTED)


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.django_db(transaction=True)
def test_unknown_tech_notifies_all_admins(account, activity, user_a, client_account_a, admins_a):
    """An unknown tech fans out one notification per active admin."""
    signal = _make_unknown_tech(account, activity, user_a)

    TranscriptSignalExtractor()._maybe_notify_unknown_tech(signal, client_account_a.id)

    notifs = _unknown_tech_qs()
    assert notifs.count() == len(admins_a) == 2
    recipient_ids = set(notifs.values_list('recipient_id', flat=True))
    assert recipient_ids == {a.id for a in admins_a}
    notif = notifs.first()
    assert notif.related_object_type == 'tech_stack_signal'
    assert str(notif.related_object_id) == str(signal.id)
    assert notif.payload.get('tech_name') == 'FooDB'


@pytest.mark.django_db(transaction=True)
def test_matched_tech_emits_nothing(account, activity, user_a, client_account_a, admins_a):
    """A catalog-matched tech does not notify anyone."""
    signal = _make_matched_tech(account, activity, user_a)

    TranscriptSignalExtractor()._maybe_notify_unknown_tech(signal, client_account_a.id)

    assert _unknown_tech_qs().count() == 0


@pytest.mark.django_db(transaction=True)
def test_emit_failure_is_non_raising_and_signal_survives(
    account, activity, user_a, client_account_a, admins_a, monkeypatch
):
    """A raising emit never propagates; the extracted signal still exists."""
    signal = _make_unknown_tech(account, activity, user_a)

    def _boom(*args, **kwargs):
        raise RuntimeError('emit exploded')

    monkeypatch.setattr(
        'app_modules.ai_pipelines.services.transcript_signal_extractor.'
        'NotificationService.emit',
        _boom,
    )

    # Must not raise, even though every emit blows up.
    TranscriptSignalExtractor()._maybe_notify_unknown_tech(signal, client_account_a.id)

    # No notifications were created, but the extracted signal survives.
    assert _unknown_tech_qs().count() == 0
    assert TechStackSignal.objects.filter(id=signal.id).exists()
