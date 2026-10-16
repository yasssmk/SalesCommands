# backend/tests/ai_pipelines/test_techstack_lifecycle_extraction.py
"""
Sprint TechStack T4 — techstack prompt v3: lifecycle + notes extraction.

The model now emits, ONLY when said (else null, never guessed):
usage_start_year, renewal_date, discontinued_date (YYYY-MM-DD, relative dates
resolved with the activity date of the context), cost_description (verbatim),
is_discontinued, notes (HOW the tool is used + what the prospect thinks of
it). is_to_replace left the output schema — the builder forces it to False.

Builder rules (_build_techstack_data):
  * year = an integer within the module bounds, else null;
  * dates = ISO dates that parse, else null; texts stripped;
  * D2 — discontinued without a valid date -> not discontinued, no date, the
    stated phrase (source_quote) appended to the notes;
  * D3 — the same tool cited twice -> the EMPTY lifecycle / notes fields of
    the first candidate are completed by the later one.

Harness = test_techstack_extraction_raw_name.py: the real persist_stage()
the pipeline orchestrator calls (safety filter + builder + dedup chained),
no LLM provider involved.
"""

import datetime

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (
    TECHSTACK_PROMPT_VERSION,
    build_techstack_request,
)
from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)


pytestmark = pytest.mark.django_db


def _raw(tech_name, **overrides):
    payload = {
        'tech_name':         tech_name,
        'usage_scope':       'UNKNOWN',
        'usage_departments': [],
        'source_quote':      f'We use {tech_name}',
        'confidence':        0.9,
        'is_inferred':       False,
    }
    payload.update(overrides)
    return payload


def _persist(activity, account, user, raw_signals):
    persisted, _dropped = TranscriptSignalExtractor().persist_stage(
        stage='techstack',
        raw_signals=raw_signals,
        activity=activity,
        user=user,
        client_id=account.client_id,
        confidence_min=0.5,
        drop_inferred=True,
    )
    return persisted


def _one(activity, account, user, **fields):
    persisted = _persist(activity, account, user, [_raw('HubSpot', **fields)])
    assert len(persisted) == 1
    sig = persisted[0]
    sig.refresh_from_db()
    return sig


# =============================================================================
# A — the new fields are persisted, texts cleaned
# =============================================================================

class TestLifecycleFieldsPersisted:

    def test_every_lifecycle_field_and_notes_land_on_the_signal(
        self, account, activity, user_a,
    ):
        sig = _one(
            activity, account, user_a,
            usage_start_year=2019,
            renewal_date='2027-03-31',
            cost_description='  12k€ per year  ',
            is_discontinued=True,
            discontinued_date='2026-06-30',
            notes='  Used for SSO; they find it reliable.  ',
        )
        assert sig.usage_start_year == 2019
        assert sig.renewal_date == datetime.date(2027, 3, 31)
        assert sig.cost_description == '12k€ per year'
        assert sig.is_discontinued is True
        assert sig.discontinued_date == datetime.date(2026, 6, 30)
        assert sig.notes == 'Used for SSO; they find it reliable.'

    def test_not_said_leaves_the_fields_empty(self, account, activity, user_a):
        sig = _one(activity, account, user_a)
        assert sig.usage_start_year is None
        assert sig.renewal_date is None
        assert sig.cost_description == ''
        assert sig.is_discontinued is False
        assert sig.discontinued_date is None
        assert sig.notes == ''

    def test_explicit_nulls_leave_the_fields_empty(self, account, activity, user_a):
        sig = _one(
            activity, account, user_a,
            usage_start_year=None, renewal_date=None, cost_description=None,
            is_discontinued=None, discontinued_date=None, notes=None,
        )
        assert sig.usage_start_year is None
        assert sig.renewal_date is None
        assert sig.cost_description == ''
        assert sig.is_discontinued is False
        assert sig.notes == ''

    def test_is_to_replace_is_forced_false(self, account, activity, user_a):
        sig = _one(activity, account, user_a, is_to_replace=True)
        assert sig.is_to_replace is False


# =============================================================================
# B — invalid dates / years -> null
# =============================================================================

class TestInvalidValuesAreDropped:

    @pytest.mark.parametrize('value', ['next spring', '2027-02-30', '31/03/2027', 20270331, ''])
    def test_invalid_renewal_date_is_null(self, value, account, activity, user_a):
        sig = _one(activity, account, user_a, renewal_date=value)
        assert sig.renewal_date is None

    @pytest.mark.parametrize('value', [1900, 2999, 2019.5, True, 'about 2019', ''])
    def test_out_of_bounds_or_non_integer_year_is_null(self, value, account, activity, user_a):
        sig = _one(activity, account, user_a, usage_start_year=value)
        assert sig.usage_start_year is None

    def test_integer_string_year_is_accepted(self, account, activity, user_a):
        sig = _one(activity, account, user_a, usage_start_year='2019')
        assert sig.usage_start_year == 2019

    def test_date_ignored_when_not_discontinued(self, account, activity, user_a):
        sig = _one(
            activity, account, user_a,
            is_discontinued=False, discontinued_date='2026-06-30',
        )
        assert sig.is_discontinued is False
        assert sig.discontinued_date is None


# =============================================================================
# C — D2: discontinued without a valid date
# =============================================================================

class TestDiscontinuedWithoutDate:

    @pytest.mark.parametrize('date', [None, '', 'in the summer', '2026-13-01'])
    def test_no_valid_date_means_not_discontinued_and_the_phrase_goes_to_notes(
        self, date, account, activity, user_a,
    ):
        sig = _one(
            activity, account, user_a,
            is_discontinued=True, discontinued_date=date,
            source_quote='We are going to drop HubSpot at some point.',
        )
        assert sig.is_discontinued is False
        assert sig.discontinued_date is None
        assert 'We are going to drop HubSpot at some point.' in sig.notes

    def test_the_phrase_is_appended_to_existing_notes(self, account, activity, user_a):
        sig = _one(
            activity, account, user_a,
            is_discontinued=True, discontinued_date=None,
            notes='Used for marketing emails.',
            source_quote='We will stop using HubSpot.',
        )
        assert sig.notes.startswith('Used for marketing emails.')
        assert 'We will stop using HubSpot.' in sig.notes


# =============================================================================
# D — D3: the same tool cited twice completes the empty fields
# =============================================================================

class TestSameToolTwiceCompletesEmptyFields:

    def test_second_mention_fills_the_empty_fields_of_the_first(
        self, account, activity, user_a,
    ):
        persisted = _persist(activity, account, user_a, [
            _raw('Salesforce', usage_start_year=2018, source_quote='We are on Salesforce since 2018.'),
            _raw('salesforce', usage_start_year=2020, renewal_date='2027-01-31',
                 cost_description='80k a year', notes='Reporting is painful.',
                 source_quote='Salesforce renews in January, 80k a year.'),
        ])
        assert len(persisted) == 1
        sig = persisted[0]
        sig.refresh_from_db()
        # Non-empty field of the FIRST candidate kept.
        assert sig.usage_start_year == 2018
        assert sig.tech_name == 'Salesforce'
        # EMPTY fields of the first completed by the second.
        assert sig.renewal_date == datetime.date(2027, 1, 31)
        assert sig.cost_description == '80k a year'
        assert sig.notes == 'Reporting is painful.'

    def test_second_mention_fills_the_discontinuation_pair(
        self, account, activity, user_a,
    ):
        persisted = _persist(activity, account, user_a, [
            _raw('Zendesk', source_quote='We use Zendesk for support.'),
            _raw('Zendesk', is_discontinued=True, discontinued_date='2026-12-31',
                 source_quote='Zendesk goes away at the end of the year.'),
        ])
        assert len(persisted) == 1
        sig = persisted[0]
        sig.refresh_from_db()
        assert sig.is_discontinued is True
        assert sig.discontinued_date == datetime.date(2026, 12, 31)


# =============================================================================
# E — prompt v3 content
# =============================================================================

class TestPromptV3:

    def test_version_is_v3_or_later(self):
        # v4 (T4b) keeps the v3 content asserted below.
        assert TECHSTACK_PROMPT_VERSION == 'v4'

    def test_schema_carries_the_new_fields_and_not_is_to_replace(self):
        prompt = build_techstack_request('transcript')
        for field in (
            '"usage_start_year"', '"renewal_date"', '"cost_description"',
            '"is_discontinued"', '"discontinued_date"', '"notes"',
        ):
            assert field in prompt, field
        assert 'is_to_replace' not in prompt

    def test_only_when_said_never_guessed(self):
        prompt = build_techstack_request('transcript')
        assert 'ONLY when the transcript says it' in prompt
        assert 'never guess' in prompt

    def test_relative_dates_use_the_conversation_date(self):
        # v4 (T4b): the context names it "Conversation date".
        prompt = build_techstack_request('transcript')
        assert 'Conversation date' in prompt
        assert 'YYYY-MM-DD' in prompt

    def test_notes_cover_how_the_tool_is_used_and_the_prospect_opinion(self):
        prompt = build_techstack_request('transcript')
        assert 'HOW the prospect uses the tool' in prompt
        assert 'what the prospect THINKS of it' in prompt

    def test_one_technology_one_signal_with_the_salesforce_azure_ad_example(self):
        prompt = build_techstack_request('transcript')
        assert 'ONE technology = ONE signal' in prompt
        assert 'On est sur Salesforce et on a un SSO Azure AD.' in prompt
        assert '"tech_name": "Azure AD"' in prompt
        assert '"notes": "SSO"' in prompt
