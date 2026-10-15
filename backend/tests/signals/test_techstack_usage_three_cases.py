# backend/tests/signals/test_techstack_usage_three_cases.py
"""
TechStack usage in THREE cases (Sprint TechStack, T0).

PO decision: usage at the prospect is DEPARTMENT (+ the departments that use
the tool), COMPANY, or UNKNOWN. TEAM disappears; "not said" is UNKNOWN (never
null); DEPARTMENT <=> at least one usage department.

Three proof surfaces:
  * DATA MIGRATION 0045 (harness of test_migration_backfill_constraint_
    departments.py: roll back, seed via the HISTORICAL model, call the module
    forwards()/reverse()) — every (scope × has-departments) combination, the
    reversibility marker on modified rows only, reverse, idempotence.
  * CHOICES endpoint — usage_scopes is exactly the three cases, labelled
    Department / Company / Unknown.
  * API (Create + PATCH) — TEAM refused; the DEPARTMENT <=> departments rule
    enforced as a standard 400.
"""

import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db(transaction=True)


MIGRATION_MODULE = (
    'app_modules.signals.migrations.0045_techstack_usage_scope_three_cases'
)
BEFORE_MIGRATION = ('module_signals', '0044_alter_constraintsignal_rigidity')
MARKER = 'usage_scope_migrated_from'


# =============================================================================
# DATA MIGRATION
# =============================================================================

def _head_target():
    loader = MigrationExecutor(connection).loader
    leaves = [n for n in loader.graph.leaf_nodes() if n[0] == 'module_signals']
    return leaves[0]


def _hist_apps():
    return MigrationExecutor(connection).loader.project_state(BEFORE_MIGRATION).apps


def _migration():
    return importlib.import_module(MIGRATION_MODULE)


@pytest.fixture
def before_migration_schema():
    head = _head_target()
    MigrationExecutor(connection).migrate([BEFORE_MIGRATION])
    try:
        yield
    finally:
        MigrationExecutor(connection).migrate([head])


def _make_tech(hist, account, activity, user, *, name, scope, depts=(), metadata=None):
    Tech = hist.get_model('module_signals', 'TechStackSignal')
    sig = Tech.objects.create(
        account_id=account.id,
        client_id=account.client_id,
        source_activity_id=activity.id,
        tech_name=name,
        tech_name_normalized=name.lower(),
        usage_scope=scope,
        source=SignalSource.LLM_EXTRACTED,
        status=SignalStatus.PENDING,
        metadata=metadata if metadata is not None else {},
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    if depts:
        sig.usage_departments.set([d.id for d in depts])
    return sig


# (label, origin scope, with departments?, expected scope after forwards)
MATRIX = [
    ('company_nodept',    'COMPANY',    False, 'COMPANY'),
    ('company_dept',      'COMPANY',    True,  'DEPARTMENT'),
    ('department_dept',   'DEPARTMENT', True,  'DEPARTMENT'),
    ('department_nodept', 'DEPARTMENT', False, 'UNKNOWN'),
    ('unknown_nodept',    'UNKNOWN',    False, 'UNKNOWN'),
    ('unknown_dept',      'UNKNOWN',    True,  'DEPARTMENT'),
    ('team_dept',         'TEAM',       True,  'DEPARTMENT'),
    ('team_nodept',       'TEAM',       False, 'UNKNOWN'),
    ('null_nodept',       None,         False, 'UNKNOWN'),
    ('null_dept',         None,         True,  'DEPARTMENT'),
]


@pytest.fixture
def seeded(before_migration_schema, account, activity, user_a):
    hist = _hist_apps()
    StandardDepartment = hist.get_model('core_modules', 'StandardDepartment')
    marketing, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    rows = {}
    for label, origin, with_dept, _expected in MATRIX:
        rows[label] = _make_tech(
            hist, account, activity, user_a,
            name=f'Tool {label}', scope=origin,
            depts=[marketing] if with_dept else (),
            metadata={'kept': 'yes'},
        )
    return rows


class TestUsageScopeMigration:

    def test_forwards_normalises_every_combination(self, seeded):
        hist = _hist_apps()
        Tech = hist.get_model('module_signals', 'TechStackSignal')

        _migration().forwards(hist, None)

        for label, origin, _with_dept, expected in MATRIX:
            row = Tech.objects.get(pk=seeded[label].pk)
            assert row.usage_scope == expected, label
            if origin == expected:
                # Untouched rows carry NO marker.
                assert MARKER not in row.metadata, label
            else:
                # Modified rows carry the ORIGIN value (null included).
                assert MARKER in row.metadata, label
                assert row.metadata[MARKER] == origin, label
            # Pre-existing metadata is preserved.
            assert row.metadata['kept'] == 'yes', label

    def test_no_team_and_no_null_left(self, seeded):
        hist = _hist_apps()
        Tech = hist.get_model('module_signals', 'TechStackSignal')

        _migration().forwards(hist, None)

        assert not Tech.objects.filter(usage_scope='TEAM').exists()
        assert not Tech.objects.filter(usage_scope__isnull=True).exists()

    def test_reverse_restores_the_origin_and_removes_the_marker(self, seeded):
        hist = _hist_apps()
        Tech = hist.get_model('module_signals', 'TechStackSignal')

        _migration().forwards(hist, None)
        _migration().reverse(hist, None)

        for label, origin, _with_dept, _expected in MATRIX:
            row = Tech.objects.get(pk=seeded[label].pk)
            assert row.usage_scope == origin, label
            assert MARKER not in row.metadata, label
            assert row.metadata['kept'] == 'yes', label

    def test_forwards_is_idempotent(self, seeded):
        hist = _hist_apps()
        Tech = hist.get_model('module_signals', 'TechStackSignal')

        _migration().forwards(hist, None)
        _migration().forwards(hist, None)

        row = Tech.objects.get(pk=seeded['team_nodept'].pk)
        assert row.usage_scope == 'UNKNOWN'
        # The ORIGIN is kept on a second run, not overwritten by UNKNOWN.
        assert row.metadata[MARKER] == 'TEAM'


# =============================================================================
# CHOICES
# =============================================================================

class TestUsageScopeChoices:

    def test_usage_scopes_is_exactly_the_three_cases(self, authed_api_a):
        response = authed_api_a.get(reverse('module_signals:choices'))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['data']['usage_scopes'] == [
            {'value': 'DEPARTMENT', 'label': 'Department'},
            {'value': 'COMPANY',    'label': 'Company'},
            {'value': 'UNKNOWN',    'label': 'Unknown'},
        ]


# =============================================================================
# API — TEAM refused, DEPARTMENT <=> departments
# =============================================================================

@pytest.fixture
def marketing(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return d


def _tech(account, activity, user, *, scope='UNKNOWN', depts=()):
    sig = TechStackSignal(
        account=account, source_activity=activity,
        source=SignalSource.MANUAL, tech_name='HubSpot',
        usage_scope=scope,
    )
    sig.save(user=user, client_id=account.client_id)
    if depts:
        sig.usage_departments.set(depts)
    return sig


def _patch(api, sig, payload):
    return api.patch(
        reverse('module_signals:tech-stack-detail', kwargs={'pk': sig.id}),
        payload, format='json',
    )


def _create(api, account, activity, payload):
    return api.post(
        reverse('module_signals:tech-stack-list'),
        {'account': str(account.id), 'source_activity': str(activity.id),
         'tech_name': 'HubSpot', **payload},
        format='json',
    )


class TestUsageScopeApiRules:

    def test_patch_team_is_refused(self, authed_api_a, account, activity, user_a):
        sig = _tech(account, activity, user_a)
        response = _patch(authed_api_a, sig, {'usage_scope': 'TEAM'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_department_without_department_is_refused(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _tech(account, activity, user_a)
        response = _patch(
            authed_api_a, sig,
            {'usage_scope': 'DEPARTMENT', 'usage_departments': []},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        sig.refresh_from_db()
        assert sig.usage_scope == 'UNKNOWN'

    def test_patch_departments_on_company_is_refused(
        self, authed_api_a, account, activity, user_a, marketing,
    ):
        sig = _tech(account, activity, user_a, scope='COMPANY')
        response = _patch(authed_api_a, sig, {'usage_departments': [marketing.id]})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_department_with_departments_is_accepted(
        self, authed_api_a, account, activity, user_a, marketing,
    ):
        sig = _tech(account, activity, user_a)
        response = _patch(
            authed_api_a, sig,
            {'usage_scope': 'DEPARTMENT', 'usage_departments': [marketing.id]},
        )
        assert response.status_code == status.HTTP_200_OK, response.json()
        sig.refresh_from_db()
        assert sig.usage_scope == 'DEPARTMENT'
        assert list(sig.usage_departments.values_list('id', flat=True)) == [marketing.id]

    def test_patch_switch_to_company_clearing_departments_is_accepted(
        self, authed_api_a, account, activity, user_a, marketing,
    ):
        sig = _tech(account, activity, user_a, scope='DEPARTMENT', depts=[marketing])
        response = _patch(
            authed_api_a, sig,
            {'usage_scope': 'COMPANY', 'usage_departments': []},
        )
        assert response.status_code == status.HTTP_200_OK, response.json()

    def test_notes_only_patch_is_not_blocked(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _tech(account, activity, user_a)
        response = _patch(authed_api_a, sig, {'notes': 'happy with it'})
        assert response.status_code == status.HTTP_200_OK, response.json()

    def test_create_department_without_department_is_refused(
        self, authed_api_a, account, activity,
    ):
        response = _create(
            authed_api_a, account, activity,
            {'usage_scope': 'DEPARTMENT', 'usage_departments': []},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_scope_is_unknown(self, authed_api_a, account, activity):
        response = _create(authed_api_a, account, activity, {})
        assert response.status_code == status.HTTP_201_CREATED, response.json()
        sig = TechStackSignal.objects.get(id=response.json()['data']['id'])
        assert sig.usage_scope == 'UNKNOWN'
