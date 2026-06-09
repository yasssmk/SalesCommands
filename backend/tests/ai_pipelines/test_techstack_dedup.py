# backend/tests/ai_pipelines/test_techstack_dedup.py
"""
Unit tests for TechStack deduplication in TranscriptSignalExtractor.

The _deduplicate_techstack static method merges multiple candidates
that refer to the same tool (by catalog entry id or pending_tech_name).
"""

import pytest
from unittest.mock import MagicMock

from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)


class TestTechStackDedup:

    def _make_pending_candidate(self, tech_name, source_quote='quote'):
        return {
            'signal_type': 'tech_stack',
            'tech_catalog_entry': None,
            'metadata': {'pending_tech_name': tech_name},
            'source_quote': source_quote,
        }

    def _make_catalog_candidate(self, catalog_id, source_quote='quote'):
        entry = MagicMock()
        entry.id = catalog_id
        return {
            'signal_type': 'tech_stack',
            'tech_catalog_entry': entry,
            'metadata': {},
            'source_quote': source_quote,
        }

    def test_three_same_pending_name_produces_one(self):
        """3x 'Salesforce' (pending) -> 1 signal with 2 additional_quotes."""
        candidates = [
            self._make_pending_candidate('Salesforce', 'We use Salesforce for CRM'),
            self._make_pending_candidate('salesforce', 'Salesforce is our main tool'),
            self._make_pending_candidate(' Salesforce ', 'The team relies on Salesforce'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 1
        assert result[0]['metadata']['pending_tech_name'] == 'Salesforce'
        assert result[0]['source_quote'] == 'We use Salesforce for CRM'
        assert len(result[0]['metadata']['additional_quotes']) == 2

    def test_different_names_produce_separate_signals(self):
        """'Salesforce' + 'HubSpot' + 'Salesforce' -> 2 signals."""
        candidates = [
            self._make_pending_candidate('Salesforce', 'quote 1'),
            self._make_pending_candidate('HubSpot', 'quote 2'),
            self._make_pending_candidate('Salesforce', 'quote 3'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 2
        names = [r['metadata']['pending_tech_name'] for r in result]
        assert names == ['Salesforce', 'HubSpot']
        assert result[0]['metadata']['additional_quotes'] == ['quote 3']
        assert 'additional_quotes' not in result[1]['metadata']

    def test_dedup_by_catalog_entry_id(self):
        """Two candidates with same catalog_entry.id -> 1 signal."""
        catalog_id = 'cat-uuid-123'
        candidates = [
            self._make_catalog_candidate(catalog_id, 'first mention'),
            self._make_catalog_candidate(catalog_id, 'second mention'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 1
        assert result[0]['source_quote'] == 'first mention'
        assert result[0]['metadata']['additional_quotes'] == ['second mention']

    def test_single_candidate_unchanged(self):
        """A single candidate passes through without modification."""
        candidates = [self._make_pending_candidate('Jira', 'We track in Jira')]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 1
        assert result[0]['metadata']['pending_tech_name'] == 'Jira'
        assert 'additional_quotes' not in result[0]['metadata']

    def test_preserves_order_of_first_occurrence(self):
        """Output order matches first occurrence of each group."""
        candidates = [
            self._make_pending_candidate('Slack', 'q1'),
            self._make_pending_candidate('Notion', 'q2'),
            self._make_pending_candidate('Slack', 'q3'),
            self._make_pending_candidate('Notion', 'q4'),
        ]
        result = TranscriptSignalExtractor._deduplicate_techstack(candidates)

        assert len(result) == 2
        assert result[0]['metadata']['pending_tech_name'] == 'Slack'
        assert result[1]['metadata']['pending_tech_name'] == 'Notion'
