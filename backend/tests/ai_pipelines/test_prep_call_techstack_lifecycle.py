# backend/tests/ai_pipelines/test_prep_call_techstack_lifecycle.py
"""
Sprint 2 Game Plan — sub-step S6 (TD-314): the prep call reads the TechStack
like the deal health — its usage scope (Department / Company / Unknown, and
the using departments) and its discontinuation (a past date = « no longer
used », a future date = « planned exit ») — and no longer reads `to_replace`.

Before: the prep-call pack carried `{tech_name, is_to_replace}` per tool
(input_pack_assembler.py `_serialize_techstack_signals`); a discontinued tool
came out as a plain « Incumbent », whatever its date, with no scope; a
`to_replace` bucket was still fed by is_to_replace (always False on
extraction since the TechStack sprint; the deal health stopped reading it at
its step 3b).

Now: the PACK carries the deal health's own TechStack rows
(DealHealthEvidenceBuilder.serialize_techstack_signals — the step 3b reading,
reused, not duplicated; labels in ai_pipelines/constants.py), so the v2
Game Plan reuses the same pack; the v1 prompt (prompts/prep_call/context.py)
only prints what the pack gives.

Real path: POST /module-ai-pipelines/prep-call/run/ with the real
PrepCallPipeline; the fake LLM provider records the prompt.

DB: Postgres.
"""

import datetime
import json

import pytest
from django.utils import timezone

from app_modules.signals.constants import SignalSource, SignalStatus, UsageScope

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF, _preparable_activity
from tests.signals.test_signal_cycle_attachment import _cycle


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


@pytest.fixture
def cycle(account, user_a):
    return _cycle(account, user_a)


@pytest.fixture
def activity(account, user_a, cycle):
    return _preparable_activity(account, user_a, cycle)


def _dept(name):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name=name)
    return d


def _tech(cycle, user, tech_name, *, scope=UsageScope.UNKNOWN, departments=(),
          discontinued_on=None, is_to_replace=False):
    from app_modules.signals.models import TechStackSignal
    sig = TechStackSignal(
        account=cycle.account, decision_cycle=cycle,
        source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
        tech_name=tech_name, source_quote=f'They use {tech_name}',
        usage_scope=scope,
        is_discontinued=discontinued_on is not None,
        discontinued_date=discontinued_on,
        is_to_replace=is_to_replace,
    )
    sig.save(user=user, client_id=cycle.client_id)
    if departments:
        sig.usage_departments.set(departments)
    return sig


def _prompt(api, activity, provider):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    prompts = [c['user'] for c in provider.calls if c['stage'] == 'prep_call']
    assert len(prompts) == 1, provider.calls  # the real pipeline ran once
    return prompts[0]


def _line(prompt, tool):
    lines = [l for l in prompt.splitlines() if f': {tool}' in l]
    assert len(lines) == 1, (tool, lines)
    return lines[0]


def test_a_tool_discontinued_in_the_past_is_no_longer_used(
    authed_api_a, activity, cycle, user_a, provider,
):
    past = timezone.localdate() - datetime.timedelta(days=30)
    _tech(cycle, user_a, 'Pipedrive', discontinued_on=past)

    line = _line(_prompt(authed_api_a, activity, provider), 'Pipedrive')

    assert 'no longer used' in line
    assert past.isoformat() in line
    assert 'planned exit' not in line


def test_a_tool_discontinued_in_the_future_is_a_planned_exit(
    authed_api_a, activity, cycle, user_a, provider,
):
    future = timezone.localdate() + datetime.timedelta(days=60)
    _tech(cycle, user_a, 'Zendesk', discontinued_on=future)

    line = _line(_prompt(authed_api_a, activity, provider), 'Zendesk')

    assert 'planned exit' in line
    assert future.isoformat() in line
    assert 'no longer used' not in line


def test_the_usage_scope_and_departments_are_present(
    authed_api_a, activity, cycle, user_a, provider,
):
    _tech(cycle, user_a, 'Notion', scope=UsageScope.COMPANY)
    _tech(cycle, user_a, 'NetSuite', scope=UsageScope.DEPARTMENT,
          departments=[_dept('Finance')])

    prompt = _prompt(authed_api_a, activity, provider)

    assert str(UsageScope.COMPANY.label) in _line(prompt, 'Notion')
    netsuite = _line(prompt, 'NetSuite')
    assert str(UsageScope.DEPARTMENT.label) in netsuite
    assert 'Finance' in netsuite
    # A tool in use is not flagged as discontinued.
    assert 'no longer used' not in netsuite and 'planned exit' not in netsuite


def test_to_replace_is_no_longer_read(
    authed_api_a, activity, cycle, user_a, provider,
):
    _tech(cycle, user_a, 'Freshdesk', is_to_replace=True)

    prompt = _prompt(authed_api_a, activity, provider)

    assert 'To replace' not in prompt
    assert 'Freshdesk' in prompt  # the tool itself is still in the context
