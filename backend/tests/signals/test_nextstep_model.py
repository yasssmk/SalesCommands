# backend/tests/signals/test_nextstep_model.py
"""
Model-level invariants for NextStepSignal (Sprint B2).

Covers everything that lives at the ORM / Django model boundary:
  * Shadow-overrides on the BaseSignal field surface
  * canonical_key forced to None (NextStepSignal does not cluster)
  * clean() requires source_activity (mirror of PainSignal /
    BlockerSignal stance)
  * SignalManager.create() dispatch routes 'next_step' → NextStepSignal
  * SignalManager M2M handling (suggested_contacts populated post-save
    via .set(), since model.__init__() cannot accept M2M kwargs)
  * MANUAL → VALIDATED auto, LLM_* → PENDING auto (BaseSignal.save rules)
  * Cache invalidation: SIGNALS_CACHE_TAG only, never SIGNAL_CLUSTERS_CACHE_TAG
  * suggested_due_date nullable
  * Activity.next_step_signal reverse FK + SET_NULL semantics

API-level coverage lives in test_nextstep_api.py.
"""

import datetime

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError

from app_modules.activities.constants import ActivityType
from app_modules.signals.constants import (
    SIGNAL_CLUSTERS_CACHE_TAG,
    SIGNALS_CACHE_TAG,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import NextStepSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# SHADOW OVERRIDES
# =============================================================================

class TestNextStepSignalShadowOverride:
    """`signal_category` must be removed from NextStepSignal entirely."""

    def test_signal_category_field_does_not_exist_on_meta(self):
        with pytest.raises(FieldDoesNotExist):
            NextStepSignal._meta.get_field('signal_category')

    def test_signal_category_class_attr_is_none(self):
        assert NextStepSignal.signal_category is None


# =============================================================================
# CANONICAL KEY — never populated
# =============================================================================

class TestNextStepSignalCanonicalKey:
    """NextStepSignal does not cluster: canonical_key stays None on every save."""

    def test_canonical_key_remains_none_after_manual_save(self, account, activity, user_a):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='Envoyer récap chiffré',
            suggested_activity_type=ActivityType.EMAIL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.refresh_from_db()
        assert ns.canonical_key is None

    def test_canonical_key_remains_none_after_llm_save(self, account, activity, user_a):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='Caler une démo technique',
            suggested_activity_type=ActivityType.MEETING,
            source=SignalSource.LLM_EXTRACTED,
            confidence=0.82,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.refresh_from_db()
        assert ns.canonical_key is None


# =============================================================================
# CLEAN() — source_activity required
# =============================================================================

class TestNextStepSignalClean:
    """The model's clean() enforces source_activity as the lone hard requirement."""

    def test_clean_raises_when_source_activity_missing(self, account):
        ns = NextStepSignal(
            account=account,
            source_activity=None,
            suggested_title='orphan',
            suggested_activity_type=ActivityType.TASK,
            source=SignalSource.MANUAL,
        )
        with pytest.raises(ValidationError) as exc:
            ns.full_clean()
        # Error should bind to the source_activity field for a clean API surface.
        assert 'source_activity' in exc.value.message_dict

    def test_clean_passes_when_source_activity_set(self, account, activity):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='valid suggestion',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        # full_clean() would also validate model fields — we only care about
        # the rule under test here, so we drive .clean() directly to isolate
        # NextStepSignal.clean() and avoid coupling to base validators.
        ns.clean()


# =============================================================================
# SUGGESTED_DUE_DATE — nullable, accepts dates
# =============================================================================

class TestNextStepSignalSuggestedDueDate:
    """suggested_due_date is nullable; both null and concrete dates persist."""

    def test_suggested_due_date_null_persists(self, account, activity, user_a):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='no deadline',
            suggested_activity_type=ActivityType.EMAIL,
            suggested_due_date=None,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.refresh_from_db()
        assert ns.suggested_due_date is None

    def test_suggested_due_date_concrete_persists(self, account, activity, user_a):
        target = datetime.date(2026, 12, 15)
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='deadline set',
            suggested_activity_type=ActivityType.MEETING,
            suggested_due_date=target,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.refresh_from_db()
        assert ns.suggested_due_date == target


# =============================================================================
# SUGGESTED_CONTACTS — M2M populable + SET_NULL irrelevant (m2m no cascade)
# =============================================================================

class TestNextStepSignalSuggestedContacts:
    """
    The M2M `suggested_contacts` is populable post-save; deleting a
    contact removes its association without affecting the next-step row.
    """

    def test_suggested_contacts_populable_with_multiple(
        self, account, activity, contact, contact_extra, user_a,
    ):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='Invite both',
            suggested_activity_type=ActivityType.MEETING,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.suggested_contacts.set([contact, contact_extra])
        ns.refresh_from_db()

        ids = set(ns.suggested_contacts.values_list('id', flat=True))
        assert ids == {contact.id, contact_extra.id}

    def test_suggested_contacts_empty_default(self, account, activity, user_a):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='no attendees',
            suggested_activity_type=ActivityType.TASK,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.refresh_from_db()
        assert ns.suggested_contacts.count() == 0

    def test_contact_delete_removes_association_not_signal(
        self, account, activity, contact, user_a,
    ):
        """
        Deleting a contact must remove its M2M association without
        cascading the NextStepSignal row. M2M tables have no on_delete
        semantic — deleting a related Contact removes the join row,
        but the NextStepSignal survives.
        """
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='attendee will be removed',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.suggested_contacts.set([contact])

        contact.delete()
        ns.refresh_from_db()

        assert ns.suggested_contacts.count() == 0
        assert NextStepSignal.objects.filter(pk=ns.pk).exists()


# =============================================================================
# SIGNAL MANAGER DISPATCH + M2M HANDLING
# =============================================================================

class TestNextStepSignalManagerDispatch:
    """SignalManager.create() must route signal_type='next_step' → NextStepSignal."""

    def test_signal_manager_create_routes_next_step_type(
        self, account, activity, user_a,
    ):
        from app_modules.signals.services import SignalManager

        instance = SignalManager.create(
            data={
                'signal_type': 'next_step',
                'account': account,
                'source_activity': activity,
                'suggested_title': 'via SignalManager',
                'suggested_activity_type': ActivityType.EMAIL,
                'source': SignalSource.MANUAL,
            },
            user=user_a,
            client_id=account.client_id,
        )
        assert isinstance(instance, NextStepSignal)
        assert instance.suggested_title == 'via SignalManager'
        assert instance.canonical_key is None

    def test_signal_manager_create_applies_m2m_via_set(
        self, account, activity, contact, contact_extra, user_a,
    ):
        """
        SignalManager.create() must pop M2M values from data, create
        the row, then apply the M2M via .set() — model.__init__() does
        not accept M2M kwargs.
        """
        from app_modules.signals.services import SignalManager

        instance = SignalManager.create(
            data={
                'signal_type': 'next_step',
                'account': account,
                'source_activity': activity,
                'suggested_title': 'meeting with both',
                'suggested_activity_type': ActivityType.MEETING,
                'suggested_contacts': [contact, contact_extra],
                'source': SignalSource.MANUAL,
            },
            user=user_a,
            client_id=account.client_id,
        )
        assert isinstance(instance, NextStepSignal)
        ids = set(instance.suggested_contacts.values_list('id', flat=True))
        assert ids == {contact.id, contact_extra.id}

    def test_signal_manager_edit_applies_m2m_via_set(
        self, account, activity, contact, contact_extra, user_a,
    ):
        """
        SignalManager.edit() must pop M2M values from updates, apply
        scalar/FK fields via setattr + save, then apply M2M via .set().
        Mirror of the create-path split.
        """
        from app_modules.signals.services import SignalManager

        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='original',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.suggested_contacts.set([contact])

        # Edit: change a scalar AND swap the M2M in one call.
        SignalManager.edit(
            ns,
            {
                'suggested_title': 'revised',
                'suggested_contacts': [contact_extra],
            },
            user=user_a,
        )
        ns.refresh_from_db()
        assert ns.suggested_title == 'revised'
        ids = set(ns.suggested_contacts.values_list('id', flat=True))
        assert ids == {contact_extra.id}


# =============================================================================
# LIFECYCLE — source → status routing (inherited from BaseSignal.save())
# =============================================================================

class TestNextStepSignalLifecycleAutoStatus:
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
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title=f'status check for {source}',
            suggested_activity_type=ActivityType.TASK,
            source=source,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.refresh_from_db()
        assert ns.status == expected_status

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
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='direct llm validated',
            suggested_activity_type=ActivityType.EMAIL,
            source=SignalSource.LLM_EXTRACTED,
            status=SignalStatus.VALIDATED,
        )
        with pytest.raises(ValidationError) as exc:
            ns.save(user=user_a, client_id=account.client_id)
        assert 'status' in exc.value.message_dict

    def test_manual_source_clears_confidence(self, account, activity, user_a):
        """Per BaseSignal.save() rule 1, MANUAL signals clear confidence even
        if a value was passed in — manual signals are trusted by definition."""
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='manual with confidence noise',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
            confidence=0.5,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.refresh_from_db()
        assert ns.confidence is None


# =============================================================================
# ACTIVITY REVERSE FK — Activity.next_step_signal SET_NULL semantics
# =============================================================================

class TestNextStepSignalActivityReverseFK:
    """
    Activity.next_step_signal is the reverse-direction FK introduced in
    this sprint. SET_NULL preserves the materialised Activity when the
    originating NextStepSignal is hard-deleted.
    """

    def test_activity_carries_next_step_signal_fk(
        self, account, activity, user_a,
    ):
        """
        An Activity can be wired to a NextStepSignal at creation time;
        reverse accessor `next_step.created_activities.all()` lists it.
        """
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityType as AT, ActivityStatus

        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='becomes an activity',
            suggested_activity_type=AT.MEETING,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

        materialised = Activity(
            title='Demo techn. mat. from ns',
            activity_type=AT.MEETING,
            status=ActivityStatus.PLANNED,
            account=account,
            owner=user_a,
            next_step_signal=ns,
        )
        materialised.save(user=user_a, client_id=account.client_id)

        ns.refresh_from_db()
        assert list(ns.created_activities.values_list('id', flat=True)) == [
            materialised.id
        ]

    def test_next_step_signal_hard_delete_nulls_activity_fk(
        self, account, activity, user_a,
    ):
        """
        Hard-deleting the NextStepSignal must SET_NULL the FK on the
        materialised Activity, preserving the Activity row for audit.
        """
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityType as AT, ActivityStatus

        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='will be deleted',
            suggested_activity_type=AT.CALL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

        materialised = Activity(
            title='Mat. activity survives',
            activity_type=AT.CALL,
            status=ActivityStatus.PLANNED,
            account=account,
            owner=user_a,
            next_step_signal=ns,
        )
        materialised.save(user=user_a, client_id=account.client_id)

        ns_id = ns.pk
        ns.delete()

        materialised.refresh_from_db()
        assert materialised.next_step_signal_id is None
        assert Activity.objects.filter(pk=materialised.pk).exists()
        assert not NextStepSignal.objects.filter(pk=ns_id).exists()

    def test_next_step_signal_reject_leaves_activity_fk_intact(
        self, account, activity, user_a,
    ):
        """
        REJECTING the NextStepSignal is a status-only change — the FK
        on the materialised Activity remains intact (audit trail
        "this Activity was created from a suggestion later rejected").
        """
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityType as AT, ActivityStatus
        from app_modules.signals.services import SignalManager

        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='will be rejected',
            suggested_activity_type=AT.EMAIL,
            source=SignalSource.LLM_EXTRACTED,
        )
        ns.save(user=user_a, client_id=account.client_id)

        materialised = Activity(
            title='Mat. activity keeps FK',
            activity_type=AT.EMAIL,
            status=ActivityStatus.PLANNED,
            account=account,
            owner=user_a,
            next_step_signal=ns,
        )
        materialised.save(user=user_a, client_id=account.client_id)

        SignalManager.reject(ns, user=user_a, reason='dup')
        ns.refresh_from_db()
        materialised.refresh_from_db()

        assert ns.status == SignalStatus.REJECTED
        assert materialised.next_step_signal_id == ns.pk


# =============================================================================
# CACHE INVALIDATION — receivers wired correctly
# =============================================================================

class TestNextStepSignalCacheInvalidation:
    """
    NextStepSignal writes must bust SIGNALS_CACHE_TAG but never
    SIGNAL_CLUSTERS_CACHE_TAG. Driven via the model save() so the
    post_save receiver fires through transaction.on_commit.

    Requires `transaction=True` so the implicit save transaction commits
    and on_commit callbacks actually run during the test.
    """

    @pytest.mark.django_db(transaction=True)
    def test_save_invalidates_signals_cache_tag(
        self, account, activity, user_a, cache_invalidation_calls,
    ):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='cache spy save',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

        namespaces_hit = [ns_ for _, ns_ in cache_invalidation_calls]
        assert SIGNALS_CACHE_TAG in namespaces_hit, (
            'SIGNALS_CACHE_TAG must be invalidated by NextStepSignal post_save.'
        )

        # The captured client_id must match the next-step's tenant.
        clients_hit = {cid for cid, ns_ in cache_invalidation_calls
                       if ns_ == SIGNALS_CACHE_TAG}
        assert str(account.client_id) in clients_hit

    @pytest.mark.django_db(transaction=True)
    def test_save_does_not_invalidate_clusters_cache_tag(
        self, account, activity, user_a, cache_invalidation_calls,
    ):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='cluster guard',
            suggested_activity_type=ActivityType.MEETING,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

        namespaces_hit = [ns_ for _, ns_ in cache_invalidation_calls]
        assert SIGNAL_CLUSTERS_CACHE_TAG not in namespaces_hit, (
            'NextStepSignal must NOT bust SIGNAL_CLUSTERS_CACHE_TAG '
            '(not part of the cluster model).'
        )

    @pytest.mark.django_db(transaction=True)
    def test_delete_invalidates_signals_cache_tag(
        self, account, activity, user_a, cache_invalidation_calls,
    ):
        ns = NextStepSignal(
            account=account,
            source_activity=activity,
            suggested_title='delete spy',
            suggested_activity_type=ActivityType.TASK,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

        # Reset spy to isolate the delete invocation.
        cache_invalidation_calls.clear()

        ns.delete()

        namespaces_hit = [ns_ for _, ns_ in cache_invalidation_calls]
        assert SIGNALS_CACHE_TAG in namespaces_hit
        assert SIGNAL_CLUSTERS_CACHE_TAG not in namespaces_hit
