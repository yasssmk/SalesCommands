# backend/tests/signals/test_attach_signals_to_cycles_command.py
"""
Sprint « Cycle de vie des contacts », étape 2 -- the catch-up command
`manage.py attach_signals_to_cycles` fixes the EXISTING data with the runtime
rules (services/signal_cycle_attachment.py):
  * --dry-run lists what would be attached and writes NOTHING;
  * the real run attaches; a second run finds nothing (re-runnable);
  * a campaign_account sequence is counted ONCE even when two activities of
    the born cycle point at it (dry run deduplicated per signal); the OLDEST
    born activity takes it;
  * a signal on another cycle is never moved.

History is built with signals disabled (no post_save attachment), as the data
written before this step.
"""

import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from core.cache_utils import disable_signals
from tests.signals.test_signal_cycle_attachment import (
    TODAY, _campaign_account, _cycle, _cycle_of, _next_step, _pain, _people,
    _plain_activity, _prospect_activity, _tech_stack,
)


pytestmark = pytest.mark.django_db


def _born_activity(campaign_activity, cycle, user, title='Discovery meeting'):
    """An activity created FROM the campaign activity inside `cycle`."""
    from app_modules.activities.models import Activity
    a = Activity(title=title, activity_type='MEETING', status='PLANNED',
                 account=campaign_activity.account, owner=user,
                 decision_cycle=cycle, decision_step=cycle.qualification,
                 source_activity=campaign_activity,
                 scheduled_date=TODAY + datetime.timedelta(days=7))
    a.save(user=user, client_id=campaign_activity.client_id)
    return a


def _run(*args):
    out = StringIO()
    call_command('attach_signals_to_cycles', *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def history(account, user_a):
    """Data as it stands before this step: nothing attached."""
    with disable_signals():
        ca = _campaign_account(account, user_a)
        won = _prospect_activity(ca, user_a, 'Jordan', outcome='SUCCESSFUL', position=2)
        other = _prospect_activity(ca, user_a, 'Kim', position=1)
        born = _cycle(account, user_a, name='Born')
        _born_activity(won, born, user_a)
        _born_activity(won, born, user_a, title='Second meeting')   # same sequence
        later = _cycle(account, user_a, name='Later')
        analysed = _plain_activity(account, user_a)
        signals = {
            'won_people': _people(won, user_a, 'Jordan Prospect'),
            'other_pain': _pain(other, user_a),
            'won_next_step': _next_step(won, user_a),
            'analysed_people': _people(analysed, user_a, 'Marie Curie'),
            'elsewhere': _people(analysed, user_a, 'On X', decision_cycle=later),
            # 2b (3): TechStack re-included (scope = explicit field).
            'sequence_tech': _tech_stack(other, user_a),
            'analysed_tech': _tech_stack(analysed, user_a),
        }
        x = _cycle(account, user_a, name='X')
        from app_modules.activities.models import Activity
        Activity.objects.filter(pk=analysed.pk).update(
            decision_cycle=x, decision_step=x.qualification,
        )
    return {'born': born, 'x': x, 'later': later, **signals}


def test_dry_run_lists_and_writes_nothing(history):
    out = _run('--dry-run')
    assert 'DRY RUN' in out
    # Deduplicated per signal: people 2, pain 1, tech_stack 2 (2b (3)).
    assert '5 signal(s) would be attached' in out
    totals = out.split('per type: ')[-1]
    for part in ("'people': 2", "'pain': 1", "'tech_stack': 2"):
        assert part in totals
    assert 'kept on another cycle' in out
    for key in ('won_people', 'other_pain', 'analysed_people'):
        assert _cycle_of(history[key]) is None


def test_apply_attaches_then_a_second_run_finds_nothing(history):
    _run()
    assert _cycle_of(history['won_people']) == history['born'].id
    assert _cycle_of(history['other_pain']) == history['born'].id
    assert _cycle_of(history['analysed_people']) == history['x'].id
    assert _cycle_of(history['won_next_step']) is None          # 5.14b
    assert _cycle_of(history['sequence_tech']) == history['born'].id   # 2b (3)
    assert _cycle_of(history['analysed_tech']) == history['x'].id      # 2b (3)
    assert _cycle_of(history['elsewhere']) == history['later'].id  # never moved

    # Re-runnable: nothing left to attach (the signal on another cycle is
    # still reported as kept, never moved).
    second = _run()
    assert '0 signal(s) attached' in second
    assert 'kept on another cycle' in second
    assert _cycle_of(history['elsewhere']) == history['later'].id
