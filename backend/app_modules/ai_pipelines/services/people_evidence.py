# app_modules/ai_pipelines/services/people_evidence.py
"""
TD-279 V -- server check of the proof of a People observation, before the
role is trusted (no AI, no database).

  a) the source_quote must be in the transcript (normalised,
     transcript_text.normalize_text) -> else QUOTE_NOT_FOUND;
  b) a person who SPEAKS (their name designates a speaker label, the
     resolve_participant_by_name rule: participant_refs.resolve_speaker_label)
     must have SAID the quote or be NAMED in it -> else QUOTE_NOT_ABOUT_PERSON;
  c) a transcript without speaker labels: only a) applies.

The caller (TranscriptSignalExtractor._build_people_data) keeps the person
and sets role UNKNOWN on a rejected proof. The evals/td279 script measures
the same function.
"""

from ..constants import PeopleEvidenceStatus
from .participant_refs import name_appears_in_text, resolve_speaker_label


__all__ = ['check_people_evidence']


def check_people_evidence(full_name, source_quote, transcript_text):
    """
    Args:
        full_name:       str | None -- the person's name as written by the LLM.
        source_quote:    str -- the quote the role rests on.
        transcript_text: transcript_text.TranscriptText of the run.

    Returns:
        PeopleEvidenceStatus
    """
    if not transcript_text.contains(source_quote):
        return PeopleEvidenceStatus.QUOTE_NOT_FOUND
    label = resolve_speaker_label(full_name, transcript_text.labels)
    if label is not None and not (
        transcript_text.said_by(source_quote, label)
        or name_appears_in_text(full_name, source_quote)
    ):
        return PeopleEvidenceStatus.QUOTE_NOT_ABOUT_PERSON
    return PeopleEvidenceStatus.OK
