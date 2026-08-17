# backend/tests/ai_pipelines/test_techstack_dedup.py
"""
Unit tests for TechStack deduplication in TranscriptSignalExtractor.

The _deduplicate_techstack static method merges multiple candidates that
refer to the same tool within one extraction batch.

S10: the grouping key is the NORMALISED `tech_name`
(TechStackSignal._normalize_tech_name — lower + trim + collapse), the
same function the model's save() uses to fill `tech_name_normalized`.
It replaces the previous key, which was the catalog entry id with a
fallback on metadata['pending_tech_name'] — neither of which the
extractor produces anymore.

These are pure-function tests on the candidate dicts: no DB, no LLM.
The end-to-end behaviour through persist_stage() is covered by
tests/ai_pipelines/test_techstack_extraction_raw_name.py.
"""

import pytest

from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)


class TestTechStackDedup:

    def _make_candidate(self, tech_name, source_quote='quote', **overrides):
        candidate = {
            'signal_type': 'tech_stack',
            'tech_name': tech_name,
            'tech_catalog_entry': None,
            'is_competitor': False,
            'is_integration': False,
            'is_to_replace': False,
            'source_quote': source_quote,
        }
        candidate.update(overrides)
        return candidate

    def test_three_spellings_of_one_name_produce_one(self):
        """3x 'Salesforce' with different casing/padding -> 1 signal."""
        candidates = [
            self._make_candidate('Salesforce', 'We use Salesforce for CRM'),
            self._make_candidate('salesforce', 'Salesforce is our main tool'),
            self._make_candidate(' Salesforce ', 'The team relies on Salesforce'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 1
        # The winner keeps its RAW spelling — only the key is normalised.
        assert result[0]['tech_name'] == 'Salesforce'
        assert result[0]['source_quote'] == 'We use Salesforce for CRM'
        assert len(result[0]['metadata']['additional_quotes']) == 2

    def test_internal_whitespace_is_collapsed_for_grouping(self):
        """'Microsoft Teams' and 'microsoft   teams' are one tool."""
        candidates = [
            self._make_candidate('Microsoft Teams', 'q1'),
            self._make_candidate('microsoft   teams', 'q2'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 1
        assert result[0]['tech_name'] == 'Microsoft Teams'
        assert result[0]['metadata']['additional_quotes'] == ['q2']

    def test_different_names_produce_separate_signals(self):
        """'Salesforce' + 'HubSpot' + 'Salesforce' -> 2 signals."""
        candidates = [
            self._make_candidate('Salesforce', 'quote 1'),
            self._make_candidate('HubSpot', 'quote 2'),
            self._make_candidate('Salesforce', 'quote 3'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 2
        names = [r['tech_name'] for r in result]
        assert names == ['Salesforce', 'HubSpot']
        assert result[0]['metadata']['additional_quotes'] == ['quote 3']
        assert not result[1].get('metadata')

    def test_single_candidate_unchanged(self):
        """A single candidate passes through without modification."""
        candidates = [self._make_candidate('Jira', 'We track in Jira')]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 1
        assert result[0]['tech_name'] == 'Jira'
        assert not result[0].get('metadata')

    def test_preserves_order_of_first_occurrence(self):
        """Output order matches first occurrence of each group."""
        candidates = [
            self._make_candidate('Slack', 'q1'),
            self._make_candidate('Notion', 'q2'),
            self._make_candidate('Slack', 'q3'),
            self._make_candidate('Notion', 'q4'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 2
        assert result[0]['tech_name'] == 'Slack'
        assert result[1]['tech_name'] == 'Notion'

    def test_first_candidate_wins_including_its_booleans(self):
        """
        The winner is the first occurrence. Its qualification flags are
        kept as-is — the merge does not OR the losers' flags in. Asserted
        so a future change to that policy is a deliberate one.
        """
        candidates = [
            self._make_candidate('Salesforce', 'q1', is_competitor=True),
            self._make_candidate('salesforce', 'q2', is_integration=True),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 1
        assert result[0]['is_competitor'] is True
        assert result[0]['is_integration'] is False

    def test_existing_metadata_is_not_clobbered(self):
        """additional_quotes is added alongside whatever metadata exists."""
        candidates = [
            self._make_candidate('Slack', 'q1', metadata={'foo': 'bar'}),
            self._make_candidate('slack', 'q2'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 1
        assert result[0]['metadata']['foo'] == 'bar'
        assert result[0]['metadata']['additional_quotes'] == ['q2']
