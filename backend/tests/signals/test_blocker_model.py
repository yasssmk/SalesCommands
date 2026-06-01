# backend/tests/signals/test_blocker_model.py
"""
Model-level invariants for BlockerSignal (Sprint B1).

Covers everything that lives at the ORM / Django model boundary:
  * Shadow-overrides on the BaseSignal field surface
  * canonical_key forced to None (BlockerSignal does not cluster)
  * clean() requires source_activity (mirror of PainSignal stance)
  * Contact SET_NULL semantics
  * SignalManager.create() dispatch routes 'blocker' → BlockerSignal
  * MANUAL → VALIDATED auto, LLM_* → PENDING auto (BaseSignal.save rules)
  * Cache invalidation : SIGNALS_CACHE_TAG only, never SIGNAL_CLUSTERS_CACHE_TAG

API-level coverage lives in test_blocker_api.py.
"""

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError

from app_modules.signals.constants import (
    SIGNAL_CLUSTERS_CACHE_TAG,
    SIGNALS_CACHE_TAG,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import BlockerSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# SHADOW OVERRIDES
# =============================================================================

class TestBlockerSignalShadowOverride:
    """`signal_category` must be removed from BlockerSignal entirely."""

    def test_signal_category_field_does_not_exist_on_meta(self):
        with pytest.raises(FieldDoesNotExist):
            BlockerSignal._meta.get_field('signal_category')

    def test_signal_category_class_attr_is_none(self):
        assert BlockerSignal.signal_category is None


# =============================================================================
# CANONICAL KEY — never populated
# =============================================================================

class TestBlockerSignalCanonicalKey:
    """BlockerSignal does not cluster: canonical_key stays None on every save."""

    def test_canonical_key_remains_none_after_manual_save(self, account, activity, user_a):
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='Budget non confirmé pour Q3',
            source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)
        b.refresh_from_db()
        assert b.canonical_key is None

    def test_canonical_key_remains_none_after_llm_save(self, account, activity, user_a):
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='Décideur final pas identifié',
            source=SignalSource.LLM_EXTRACTED,
            confidence=0.82,
        )
        b.save(user=user_a, client_id=account.client_id)
        b.refresh_from_db()
        assert b.canonical_key is None


# =============================================================================
# CLEAN() — source_activity required
# =============================================================================

class TestBlockerSignalClean:
    """The model's clean() enforces source_activity as the lone hard requirement."""

    def test_clean_raises_when_source_activity_missing(self, account):
        b = BlockerSignal(
            account=account,
            source_activity=None,
            summary='orphan blocker',
            source=SignalSource.MANUAL,
        )
        with pytest.raises(ValidationError) as exc:
            b.full_clean()
        # Error should bind to the source_activity field for a clean API surface.
        assert 'source_activity' in exc.value.message_dict

    def test_clean_passes_when_source_activity_set(self, account, activity):
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='valid blocker',
            source=SignalSource.MANUAL,
        )
        # full_clean() would also validate model fields — we only care about
        # the rule under test here, so we drive .clean() directly to isolate
        # BlockerSignal.clean() and avoid coupling to base validators.
        b.clean()


# =============================================================================
# CONTACT — SET_NULL preserves the blocker
# =============================================================================

class TestBlockerSignalContactRelation:
    """Deleting the attributed Contact must null out the FK, not the blocker."""

    def test_contact_set_null_on_delete_preserves_blocker(
        self, account, activity, contact, user_a,
    ):
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='Attribué à Jane',
            source=SignalSource.MANUAL,
            contact=contact,
        )
        b.save(user=user_a, client_id=account.client_id)
        b.refresh_from_db()
        assert b.contact_id == contact.id

        contact.delete()
        b.refresh_from_db()

        assert b.contact_id is None
        assert BlockerSignal.objects.filter(pk=b.pk).exists()


# =============================================================================
# SIGNAL MANAGER DISPATCH
# =============================================================================

class TestBlockerSignalManagerDispatch:
    """SignalManager.create() must route signal_type='blocker' → BlockerSignal."""

    def test_signal_manager_create_routes_blocker_type(
        self, account, activity, user_a,
    ):
        from app_modules.signals.services import SignalManager

        instance = SignalManager.create(
            data={
                'signal_type': 'blocker',
                'account': account,
                'source_activity': activity,
                'summary': 'via SignalManager',
                'source': SignalSource.MANUAL,
            },
            user=user_a,
            client_id=account.client_id,
        )
        assert isinstance(instance, BlockerSignal)
        assert instance.summary == 'via SignalManager'
        assert instance.canonical_key is None


# =============================================================================
# LIFECYCLE — source → status routing (inherited from BaseSignal.save())
# =============================================================================

class TestBlockerSignalLifecycleAutoStatus:
    """source value drives the initial status: MANUAL=VALIDATED, LLM_*=PENDING."""

    @pytest.mark.parametrize(
        'source,expected_status',
        [
            (SignalSource.MANUAL, SignalStatus.VALIDATED),
            (SignalSource.LLM_EXTRACTED, SignalStatus.PENDING),
            (SignalSource.LLM_MODIFIED, SignalStatus.PENDING),
            (SignalSource.EXTERNAL_RESEARCH, SignalStatus.PENDING),
        ],
        ids=['manual->validated', 'llm_extracted->pending',
             'llm_modified->pending', 'external_research->pending'],
    )
    def test_source_drives_initial_status(
        self, account, activity, user_a, source, expected_status,
    ):
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary=f'status check for {source}',
            source=source,
        )
        b.save(user=user_a, client_id=account.client_id)
        b.refresh_from_db()
        assert b.status == expected_status

    def test_llm_source_cannot_be_created_with_validated_status(
        self, account, activity, user_a,
    ):
        """
        BaseSignal.save() rule 2 — defence-in-depth at the ORM layer.
        LLM-sourced signals must transit through PENDING; setting
        status=VALIDATED at create time bypasses the human-review gate
        and is rejected. The API path cannot reach this code (the Create
        serializer doesn't expose `status`), so we cover the rule by
        invoking save() directly.
        """
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='direct llm validated',
            source=SignalSource.LLM_EXTRACTED,
            status=SignalStatus.VALIDATED,
        )
        with pytest.raises(ValidationError) as exc:
            b.save(user=user_a, client_id=account.client_id)
        assert 'status' in exc.value.message_dict

    def test_manual_source_clears_confidence(self, account, activity, user_a):
        """Per BaseSignal.save() rule 1, MANUAL signals clear confidence even
        if a value was passed in — manual signals are trusted by definition."""
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='manual with confidence noise',
            source=SignalSource.MANUAL,
            confidence=0.5,
        )
        b.save(user=user_a, client_id=account.client_id)
        b.refresh_from_db()
        assert b.confidence is None


# =============================================================================
# CACHE INVALIDATION — receivers wired correctly
# =============================================================================

class TestBlockerSignalCacheInvalidation:
    """
    BlockerSignal writes must bust SIGNALS_CACHE_TAG but never
    SIGNAL_CLUSTERS_CACHE_TAG. Driven via the model save() so the
    post_save receiver fires through transaction.on_commit.

    Requires `transaction=True` so the implicit save transaction commits
    and on_commit callbacks actually run during the test.
    """

    @pytest.mark.django_db(transaction=True)
    def test_save_invalidates_signals_cache_tag(
        self, account, activity, user_a, cache_invalidation_calls,
    ):
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='cache spy save',
            source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)

        namespaces_hit = [ns for _, ns in cache_invalidation_calls]
        assert SIGNALS_CACHE_TAG in namespaces_hit, (
            'SIGNALS_CACHE_TAG must be invalidated by BlockerSignal post_save.'
        )

        # The captured client_id must match the blocker's tenant.
        clients_hit = {cid for cid, ns in cache_invalidation_calls
                       if ns == SIGNALS_CACHE_TAG}
        assert str(account.client_id) in clients_hit

    @pytest.mark.django_db(transaction=True)
    def test_save_does_not_invalidate_clusters_cache_tag(
        self, account, activity, user_a, cache_invalidation_calls,
    ):
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='cluster guard',
            source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)

        namespaces_hit = [ns for _, ns in cache_invalidation_calls]
        assert SIGNAL_CLUSTERS_CACHE_TAG not in namespaces_hit, (
            'BlockerSignal must NOT bust SIGNAL_CLUSTERS_CACHE_TAG '
            '(not part of the cluster model).'
        )

    @pytest.mark.django_db(transaction=True)
    def test_delete_invalidates_signals_cache_tag(
        self, account, activity, user_a, cache_invalidation_calls,
    ):
        b = BlockerSignal(
            account=account,
            source_activity=activity,
            summary='delete spy',
            source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)

        # Reset spy to isolate the delete invocation.
        cache_invalidation_calls.clear()

        b.delete()

        namespaces_hit = [ns for _, ns in cache_invalidation_calls]
        assert SIGNALS_CACHE_TAG in namespaces_hit
        assert SIGNAL_CLUSTERS_CACHE_TAG not in namespaces_hit
