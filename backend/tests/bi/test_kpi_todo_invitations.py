# backend/tests/bi/test_kpi_todo_invitations.py
"""
KPI 1 (Palier 3c) — the todo also includes ACCEPTED invitations.

Closes the product loop "accept an invitation -> the activity enters my todo".
Proves:
- an ACCEPTED E2 invitation to an activity I do NOT own enters my todo,
  bucketed normally;
- PENDING and DECLINED invitations are EXCLUDED (the key product rule);
- owner + invited-accepted are UNIONed and DEDUPed (an activity I both own
  and was invited-accepted to counts once);
- the invited path is PERSONAL: another user's accepted invitation is not in
  my todo (scope negative), and under team scope a manager sees THEIR OWN
  accepted invitations, not their members' (Option A);
- C6 owner inheritance still holds with the feature on;
- the compute stays query-bounded.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.activities import todo_my_activities, TodoBucket
from app_modules.bi.signals import cache_invalidation as ci
from app_modules.notifications.models import (
    NotificationCategory, NotificationResponseStatus,
)
from app_modules.notifications.services import NotificationService
from permissions.compat import AuthContext


TODAY = timezone.now().date()


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_act(owner, account, ca, status=ActivityStatus.PLANNED, due=None):
    a = Activity(title='t', activity_type=ActivityType.CALL, status=status,
                 account=account, owner=owner, due_date=due)
    a.save(user=owner, client_id=ca.id)
    return a


def _invite(activity, recipient, actor, ca, status=NotificationResponseStatus.ACCEPTED):
    """Invite `recipient` to `activity` (by `actor`) and set the response state.
    Mirrors production: invited_users M2M + an E2 notification (emitted PENDING,
    then moved to the terminal response)."""
    activity.invited_users.add(recipient)
    n = NotificationService.emit(
        client_id=ca.id, recipient=recipient, actor=actor,
        category=NotificationCategory.ACTIVITY_INVITATION,
        title='inv', related_object_type='activity', related_object_id=activity.id,
    )
    assert n.response_status == NotificationResponseStatus.PENDING
    if status != NotificationResponseStatus.PENDING:
        n.response_status = status
        n.save(user=recipient)
    return n


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpi(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield todo_my_activities
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def me(db, client_account_a, role_individual_a):
    return _mk_user('me@a.test', client_account_a, role_individual_a)


@pytest.fixture
def other(db, client_account_a, role_individual_a):
    """Another rep — owns their own account/activities, invites `me`."""
    return _mk_user('other@a.test', client_account_a, role_individual_a)


@pytest.fixture
def other_account(db, client_account_a, other):
    return _mk_account('Other Corp', other, client_account_a)


@pytest.mark.django_db
class TestAcceptedInvitationEntersTodo:

    def test_accepted_invitation_in_todo(self, kpi, me, other, other_account, client_account_a):
        """Activity owned by `other` (no C6 to me), I'm invited & ACCEPTED ->
        it's in MY todo, bucketed normally."""
        act = _mk_act(other, other_account, client_account_a, due=TODAY)
        _invite(act, me, other, client_account_a, NotificationResponseStatus.ACCEPTED)

        res = cached_run(kpi, _ctx(me, client_account_a), scope='mine')
        assert res.value == {TodoBucket.TODAY: 1}

    def test_owner_plus_accepted_union(self, kpi, me, other, other_account, client_account_a):
        """My own activity + an accepted-invitation activity -> both, deduped
        buckets."""
        my_acc = _mk_account('My Corp', me, client_account_a)
        _mk_act(me, my_acc, client_account_a, due=TODAY - timedelta(days=2))     # overdue, owned
        invited = _mk_act(other, other_account, client_account_a, due=TODAY)      # today, invited
        _invite(invited, me, other, client_account_a, NotificationResponseStatus.ACCEPTED)

        res = cached_run(kpi, _ctx(me, client_account_a), scope='mine')
        assert res.value == {TodoBucket.OVERDUE: 1, TodoBucket.TODAY: 1}

    def test_owner_and_invited_same_activity_deduped(
        self, kpi, me, other, client_account_a
    ):
        """An activity I OWN and am ALSO invited-accepted to counts ONCE."""
        my_acc = _mk_account('My Corp', me, client_account_a)
        act = _mk_act(me, my_acc, client_account_a, due=TODAY)   # I own it
        _invite(act, me, other, client_account_a, NotificationResponseStatus.ACCEPTED)  # + invited

        res = cached_run(kpi, _ctx(me, client_account_a), scope='mine')
        assert res.value == {TodoBucket.TODAY: 1}   # not 2


@pytest.mark.django_db
class TestPendingDeclinedExcluded:

    def test_pending_invitation_excluded(self, kpi, me, other, other_account, client_account_a):
        act = _mk_act(other, other_account, client_account_a, due=TODAY)
        _invite(act, me, other, client_account_a, NotificationResponseStatus.PENDING)

        res = cached_run(kpi, _ctx(me, client_account_a), scope='mine')
        assert res.value == {}   # PENDING is not actioned -> not in todo

    def test_declined_invitation_excluded(self, kpi, me, other, other_account, client_account_a):
        act = _mk_act(other, other_account, client_account_a, due=TODAY)
        _invite(act, me, other, client_account_a, NotificationResponseStatus.DECLINED)

        res = cached_run(kpi, _ctx(me, client_account_a), scope='mine')
        assert res.value == {}   # DECLINED -> not in todo


@pytest.mark.django_db
class TestScopeIsolation:

    def test_other_users_accepted_invitation_not_in_my_todo(
        self, kpi, me, other, other_account, client_account_a
    ):
        """`other` accepted an invitation (to a third party's activity); it is
        in other's todo, never in mine."""
        third = _mk_user('third@a.test', client_account_a, other.role)
        third_acc = _mk_account('Third Corp', third, client_account_a)
        act = _mk_act(third, third_acc, client_account_a, due=TODAY)
        _invite(act, other, third, client_account_a, NotificationResponseStatus.ACCEPTED)

        assert cached_run(kpi, _ctx(me, client_account_a), scope='mine').value == {}
        assert cached_run(kpi, _ctx(other, client_account_a), scope='mine').value == {TodoBucket.TODAY: 1}

    def test_c6_preserved_with_feature_on(
        self, kpi, me, other, client_account_a
    ):
        """me owns an account; other's activity on it shows via C6 (mine),
        independent of any invitation."""
        my_acc = _mk_account('My Corp', me, client_account_a)
        _mk_act(other, my_acc, client_account_a, due=TODAY + timedelta(days=1))  # C6

        res = cached_run(kpi, _ctx(me, client_account_a), scope='mine')
        assert res.value == {TodoBucket.UPCOMING: 1}

    def test_team_scope_includes_only_managers_own_invitations(
        self, kpi, client_account_a, role_individual_a
    ):
        """Option A: a manager's team todo = team owned work + the MANAGER's own
        accepted invitations, NOT the members' accepted invitations."""
        from end_users.models import Team

        manager = _mk_user('mgr@a.test', client_account_a, role_individual_a)
        team = Team.objects.create(name='T', client_account=client_account_a, manager=manager)
        member = _mk_user('mbr@a.test', client_account_a, role_individual_a)
        member.team = team
        member.save()
        outsider = _mk_user('out@a.test', client_account_a, role_individual_a)
        out_acc = _mk_account('Out Corp', outsider, client_account_a)

        mgr_acc = _mk_account('Mgr Corp', manager, client_account_a)
        mbr_acc = _mk_account('Mbr Corp', member, client_account_a)
        _mk_act(manager, mgr_acc, client_account_a, due=TODAY - timedelta(days=1))  # overdue, owned
        _mk_act(member, mbr_acc, client_account_a, due=TODAY)                       # today, team-owned

        # manager's OWN accepted invitation -> included
        mgr_inv = _mk_act(outsider, out_acc, client_account_a, due=TODAY + timedelta(days=2))
        _invite(mgr_inv, manager, outsider, client_account_a, NotificationResponseStatus.ACCEPTED)
        # member's accepted invitation -> must NOT leak into manager's team todo
        mbr_inv = _mk_act(outsider, out_acc, client_account_a, due=TODAY + timedelta(days=2))
        _invite(mbr_inv, member, outsider, client_account_a, NotificationResponseStatus.ACCEPTED)

        res = cached_run(kpi, _ctx(manager, client_account_a), scope='team')
        # overdue (mgr own) + today (member own, team) + upcoming (mgr invite only)
        assert res.value == {
            TodoBucket.OVERDUE: 1,
            TodoBucket.TODAY: 1,
            TodoBucket.UPCOMING: 1,   # exactly the manager's invite, not 2
        }


@pytest.mark.django_db
class TestQueryBound:

    def test_bounded(self, kpi, me, other, other_account, client_account_a,
                     django_assert_num_queries):
        act = _mk_act(other, other_account, client_account_a, due=TODAY)
        _invite(act, me, other, client_account_a, NotificationResponseStatus.ACCEPTED)

        # One aggregate query; the invited path is an EXISTS/IN sub-query, not N+1.
        with django_assert_num_queries(1):
            res = cached_run(kpi, _ctx(me, client_account_a), scope='mine')
            _ = res.value
