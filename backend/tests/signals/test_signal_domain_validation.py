# backend/tests/signals/test_signal_domain_validation.py
"""
Volet 2 — validate `what` (domain) at persistence: LOG + EXCLUDE, never drop.

The LLM can emit a `what` outside the controlled SignalWhat vocabulary — the
COST bug: "reduce operational costs by 15%" came back as what="COST" (a
DIMENSION value) in the domain slot. Per the PO decision (traceability >
cleanliness):

  * VALIDATE `what` in the shared persist path (SignalManager.create), mirroring
    target_department's exact-match discipline.
  * On an out-of-list `what`: PERSIST the signal flagged is_domain_valid=False
    (NOT dropped) so it stays in the DB and recoverable for reprocessing, and
    LOG the anomaly with full context.
  * EXCLUDE the flagged signal from every user-facing surface — the aggregated
    list, the clusters, and the pending counts.

A valid `what` is stored normally (is_domain_valid=True) and surfaces as usual.
"""

import pytest

from app_modules.signals.constants import (
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
)
from app_modules.signals.models import ObjectiveSignal, PainSignal
from app_modules.signals.services import SignalClusterService
from app_modules.signals.services.signal_manager import SignalManager


pytestmark = pytest.mark.django_db


AGG_URL = '/module-signals/all/'
COUNTS_URL = '/module-signals/by-activity/{activity_id}/counts/'


def _create_objective(account, activity, user, *, what, summary):
    """Create an LLM-extracted objective through the shared persist path."""
    return SignalManager.create(
        data={
            'signal_type': 'objective',
            'account': account,
            'source_activity': activity,
            'source': SignalSource.LLM_EXTRACTED,
            'status': SignalStatus.PENDING,
            'what': what,
            'dimension': SignalDimension.COST,
            'summary': summary,
            'source_quote': 'we want to reduce operational costs by 15% this year',
            'scope_level': ScopeLevel.BUSINESS,
        },
        user=user,
        client_id=account.client_id,
    )


def _create_pain(account, activity, user, *, what, summary):
    return SignalManager.create(
        data={
            'signal_type': 'pain',
            'account': account,
            'source_activity': activity,
            'source': SignalSource.LLM_EXTRACTED,
            'status': SignalStatus.PENDING,
            'what': what,
            'dimension': SignalDimension.COST,
            'summary': summary,
            'source_quote': 'operational costs keep climbing',
            'scope_level': ScopeLevel.BUSINESS,
        },
        user=user,
        client_id=account.client_id,
    )


# =============================================================================
# PERSISTENCE — flag + log, never drop
# =============================================================================

class TestDomainValidationAtPersistence:

    def test_out_of_list_what_is_persisted_flagged_and_logged(
        self, account, activity, user_a, caplog,
    ):
        with caplog.at_level('WARNING'):
            sig = _create_objective(
                account, activity, user_a,
                what='COST',  # a DIMENSION value in the DOMAIN slot
                summary='reduce operational costs by 15%',
            )

        # Persisted — NOT dropped (traceability > cleanliness).
        assert ObjectiveSignal.objects.filter(id=sig.id).exists()
        # Flagged out of the user-facing surfaces.
        assert sig.is_domain_valid is False
        # The raw domain value is preserved for reprocessing (nothing lost).
        assert sig.what == 'COST'

        # Logged with enough context to reprocess.
        record = next(
            (r for r in caplog.records
             if r.message == 'signal_what_out_of_taxonomy'),
            None,
        )
        assert record is not None, 'the anomaly must be logged'
        assert record.raw_what == 'COST'
        assert record.signal_type == 'objective'
        assert record.summary == 'reduce operational costs by 15%'
        assert record.source_quote
        assert record.source_activity_id == str(activity.id)
        assert record.client_id == str(account.client_id)

    def test_valid_what_is_stored_normally_and_not_logged(
        self, account, activity, user_a, caplog,
    ):
        with caplog.at_level('WARNING'):
            sig = _create_objective(
                account, activity, user_a,
                what=SignalWhat.OPS,  # a real DOMAIN code
                summary='reduce operational costs by 15%',
            )

        assert sig.is_domain_valid is True
        assert sig.what == SignalWhat.OPS
        assert not any(
            r.message == 'signal_what_out_of_taxonomy' for r in caplog.records
        )

    def test_manual_signal_with_valid_domain_is_unaffected(
        self, account, activity, user_a,
    ):
        # A signal type carrying a valid domain stays visible; the guard only
        # trips on an out-of-list `what`.
        sig = _create_pain(
            account, activity, user_a,
            what=SignalWhat.OPS, summary='operational process is manual',
        )
        assert sig.is_domain_valid is True


# =============================================================================
# EXCLUSION — flagged signal absent from user-facing surfaces
# =============================================================================

class TestDomainExclusionFromUserFacingSurfaces:

    def test_flagged_signal_absent_from_aggregated_list(
        self, authed_api_a, account, activity, user_a,
    ):
        valid = _create_objective(
            account, activity, user_a,
            what=SignalWhat.OPS, summary='valid operational objective',
        )
        flagged = _create_objective(
            account, activity, user_a,
            what='COST', summary='flagged out-of-domain objective',
        )

        resp = authed_api_a.get(AGG_URL, {'account_id': str(account.id)})
        assert resp.status_code == 200
        body = resp.json()
        ids = {row['id'] for row in body['results']}

        assert str(valid.id) in ids, 'the valid signal must surface'
        assert str(flagged.id) not in ids, 'the flagged signal must be hidden'

    def test_flagged_signal_absent_from_clusters(
        self, account, activity, user_a,
    ):
        # A valid pain and a flagged pain share the same canonical axes; only
        # the valid one may form/join a cluster.
        _create_pain(
            account, activity, user_a,
            what=SignalWhat.OPS, summary='valid operational pain',
        )
        _create_pain(
            account, activity, user_a,
            what='COST', summary='flagged out-of-domain pain',
        )

        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id, signal_type='pain',
        )
        # The valid pain clusters at OPS×COST; the flagged one (COST×COST) is
        # excluded, so it neither forms its own cluster nor joins any.
        member_summaries = {
            m.get('summary')
            for c in clusters
            for m in c.get('members', [])
        }
        assert 'flagged out-of-domain pain' not in member_summaries
        keys = {c['canonical_key'] for c in clusters}
        assert 'pain:COST:COST' not in keys

    def test_flagged_signal_not_counted_in_pending_badge(
        self, authed_api_a, account, activity, user_a,
    ):
        _create_objective(
            account, activity, user_a,
            what=SignalWhat.OPS, summary='valid pending objective',
        )
        _create_objective(
            account, activity, user_a,
            what='COST', summary='flagged pending objective',
        )

        resp = authed_api_a.get(COUNTS_URL.format(activity_id=activity.id))
        assert resp.status_code == 200
        body = resp.json()
        # Only the valid objective is counted; the flagged one is invisible.
        assert body['by_type']['objective']['pending'] == 1
