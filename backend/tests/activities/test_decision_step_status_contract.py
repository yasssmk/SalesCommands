# backend/tests/activities/test_decision_step_status_contract.py
"""
Contract guard for the DecisionStep.status removal.

Commit 3fe5c10 ("drop the dead DecisionStep.status column", migration 0019)
removed the stored ``status`` column — step status is now DERIVED on read via
StepStatusDerivationService. That commit updated the canonical decision_cycles
path but left two references behind in the activities module, which broke the
"create a Decision Cycle from the activity modal" parcours
(POST /module-activities/create-with-entities/):

  1. ActivityCreationService._create_pipeline_steps built DecisionStep(status=...)
     -> TypeError -> CYCLE_CREATION_FAILED.
  2. ActivityDecisionStepSerializer still declared 'status' in Meta.fields
     -> ImproperlyConfigured when serialising the linked step in the response.

These tests lock the invariants so the regression cannot silently return:
a stored ``status`` field must never come back, the serializer must only declare
fields that resolve against the model, and the service's step construction must
stay aligned with the model (no removed field passed to the constructor).
"""

import pytest

from app_modules.activities.serializers import ActivityDecisionStepSerializer
from app_modules.activities.services.activity_creation_service import (
    ActivityCreationService,
)
from app_modules.decision_cycles.models import DecisionStep


def test_decision_step_has_no_stored_status_field():
    """Status is derived, not stored. Re-adding a column would re-enable the
    stale-reference pattern that broke the modal flow."""
    field_names = {f.name for f in DecisionStep._meta.get_fields()}
    assert 'status' not in field_names, (
        "DecisionStep.status was intentionally removed (migration 0019); status "
        "is derived via StepStatusDerivationService. Do not re-add a stored column."
    )


def test_activity_decision_step_serializer_fields_resolve():
    """Building ``.fields`` is exactly what raised ImproperlyConfigured while
    'status' (a removed model column) was still declared. It must resolve
    cleanly and must not re-introduce 'status'."""
    resolved = set(ActivityDecisionStepSerializer().fields.keys())
    assert resolved == {'id', 'name', 'stage', 'stage_display'}
    assert 'status' not in resolved


@pytest.mark.django_db
def test_service_builds_pipeline_steps_with_valid_fields(account, user_a):
    """_create_cycle -> _create_pipeline_steps must construct DecisionStep with
    only real model fields. A re-introduced ``status=`` (or any removed field)
    would raise TypeError here, before any HTTP layer."""
    service = ActivityCreationService(user=user_a, client_id=account.client_id)

    cycle = service._create_cycle({'name': 'Contract guard cycle'}, str(account.id))

    steps = DecisionStep.objects.filter(cycle=cycle)
    assert steps.exists()
    assert steps.filter(stage='QUALIFICATION').exists()
