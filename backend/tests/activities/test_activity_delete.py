# backend/tests/activities/test_activity_delete.py
"""
A1 — DELETE d'activité + non-régression du GET détail (retrieve).

Contexte prouvé par l'audit A1 :
  * Les FK ``previous_activity`` / ``next_activity`` ont été supprimées en
    migration 0016. ``perform_destroy`` (views/views.py) référence encore
    ``instance.previous_activity_id`` -> AttributeError -> le DELETE est
    RÉELLEMENT cassé (500).
  * La relation avant/après est 100 % DÉRIVÉE au read-time par
    ``ActivitySequenceService`` (aucun lien stocké). Supprimer un maillon au
    milieu d'une séquence => l'avant/après se recolle tout seul à la lecture
    suivante — rien de stocké à mettre à jour.
  * Le GET détail renvoie déjà 200 (``get_object`` overridé par
    ``ScopedQuerysetMixin`` renvoie un objet nu ; le ``select_related`` mort
    de la branche retrieve n'est jamais compilé). Il doit le rester après
    retrait du ``select_related`` mort.

DELETE exige le tier ``admin`` (registry activities : delete = admin:client,
manager/individual:none), d'où les fixtures admin locales.

État attendu :
  * AVANT le fix : les DELETE échouent (AttributeError -> 500) — ROUGE.
  * APRÈS le fix : DELETE -> 204, séquence recollée, GET détail toujours 200.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity


def _detail_url(activity_id):
    return f'/module-activities/{activity_id}/'


# =============================================================================
# FIXTURES — admin (seul tier autorisé à DELETE) + une séquence DC
# =============================================================================

@pytest.fixture
def role_admin_a(db, client_account_a):
    """Reuse the admin-tier role auto-provisioned when the tenant is created
    (creating a second role named 'Admin' would violate the unique
    (name, client_account_id) constraint). Fall back to creating a distinctly
    named admin-tier role if no default admin exists."""
    from end_users.models import UserRole
    existing = UserRole.objects.filter(
        client_account=client_account_a, is_admin=True
    ).first()
    if existing:
        return existing
    return UserRole.objects.create(
        client_account=client_account_a,
        name='QA Admin',
        is_admin=True,
        is_manager=False,
        is_individual=False,
        read=True,
        write=True,
        modify=True,
        can_delete=True,
    )


@pytest.fixture
def admin_user_a(db, client_account_a, role_admin_a):
    from end_users.models import User
    return User.objects.create(
        email='admin@tenant-a.test',
        client_account=client_account_a,
        role=role_admin_a,
        is_active=True,
    )


@pytest.fixture
def standalone_activity(db, account, user_a):
    """Activité sans cycle ni campagne — cas nominal de suppression."""
    a = Activity(
        title='Standalone call',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        scheduled_date=timezone.now().date() + timedelta(days=3),
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.fixture
def decision_cycle_a(db, account, user_a):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(
        account=account,
        owner=user_a,
        name='Delete-fix cycle',
        is_active=True,
    )
    dc.save(user=user_a, client_id=account.client_id)
    return dc


@pytest.fixture
def dc_sequence(db, account, user_a, decision_cycle_a):
    """
    Trois activités PLANNED dans le MÊME decision_cycle, à dates croissantes.
    Le rang de séquence est dérivé (date asc) -> [first, middle, last].
    """
    def _mk(title, days):
        a = Activity(
            title=title,
            activity_type=ActivityType.MEETING,
            status=ActivityStatus.PLANNED,
            account=account,
            owner=user_a,
            decision_cycle=decision_cycle_a,
            scheduled_date=timezone.now().date() + timedelta(days=days),
        )
        a.save(user=user_a, client_id=account.client_id)
        return a

    first = _mk('Seq #1 (first)', 3)
    middle = _mk('Seq #2 (middle)', 6)
    last = _mk('Seq #3 (last)', 9)
    return {'first': first, 'middle': middle, 'last': last}


# =============================================================================
# 1.1 — DELETE nominal : 204 + activité supprimée
# =============================================================================

@pytest.mark.django_db
class TestActivityDelete:

    def test_delete_activity_returns_204_and_removes_it(
        self, api, authenticate, admin_user_a, client_account_a, standalone_activity
    ):
        authenticate(api, admin_user_a, client_account_a.id)
        activity_id = standalone_activity.id

        resp = api.delete(_detail_url(activity_id))

        assert resp.status_code == status.HTTP_204_NO_CONTENT, getattr(resp, 'data', resp)
        assert not Activity.objects.filter(id=activity_id).exists()


# =============================================================================
# 1.2 — Suppression d'un maillon au milieu : l'avant/après se recolle (read-time)
# =============================================================================

@pytest.mark.django_db
class TestSequenceRecollapsesAfterDelete:

    def _seq_context(self, api, activity_id):
        resp = api.get(_detail_url(activity_id))
        assert resp.status_code == status.HTTP_200_OK, getattr(resp, 'data', resp)
        return resp.json()['data']['sequence_context']

    def test_delete_middle_recollapses_prev_next(
        self, api, authenticate, admin_user_a, client_account_a, dc_sequence
    ):
        authenticate(api, admin_user_a, client_account_a.id)
        first = dc_sequence['first']
        middle = dc_sequence['middle']
        last = dc_sequence['last']

        # --- Avant suppression : la séquence connaît les 3 maillons ---
        ctx_first_before = self._seq_context(api, first.id)
        next_ids_before = {a['id'] for a in ctx_first_before['next_activities']}
        assert str(middle.id) in next_ids_before
        assert str(last.id) in next_ids_before

        ctx_last_before = self._seq_context(api, last.id)
        prev_ids_before = {a['id'] for a in ctx_last_before['previous_activities']}
        assert prev_ids_before == {str(middle.id)}  # le plus proche prédécesseur

        # --- Suppression du MILIEU (le DELETE doit réussir) ---
        resp = api.delete(_detail_url(middle.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT, getattr(resp, 'data', resp)
        assert not Activity.objects.filter(id=middle.id).exists()

        # --- Après : recalcul read-time, l'avant/après se recolle ---
        ctx_first_after = self._seq_context(api, first.id)
        next_ids_after = {a['id'] for a in ctx_first_after['next_activities']}
        assert str(middle.id) not in next_ids_after      # maillon disparu
        assert next_ids_after == {str(last.id)}           # first -> last

        ctx_last_after = self._seq_context(api, last.id)
        prev_ids_after = {a['id'] for a in ctx_last_after['previous_activities']}
        assert prev_ids_after == {str(first.id)}          # recollé sur first


# =============================================================================
# 1.3 — Non-régression : le GET détail (retrieve) reste 200
# =============================================================================

@pytest.mark.django_db
class TestRetrieveStill200:

    def test_get_detail_returns_200(
        self, api, authenticate, admin_user_a, client_account_a, standalone_activity
    ):
        authenticate(api, admin_user_a, client_account_a.id)

        resp = api.get(_detail_url(standalone_activity.id))

        assert resp.status_code == status.HTTP_200_OK, getattr(resp, 'data', resp)
        body = resp.json()
        assert body['data']['id'] == str(standalone_activity.id)
