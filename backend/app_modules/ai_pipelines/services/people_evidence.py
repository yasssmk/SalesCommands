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

check_quote_evidence is step a) ALONE -- the quote found in the transcript,
nothing of the person -- shared with the next steps (Sprint Next steps 3.6,
NextStepExtractor): one algorithm. On a quote not found, its detail counts
the parts of the quote split on the speaker labels of THIS transcript
(TranscriptText.quote_parts) and how many are lines of the transcript: all
found = a quote SPLICED from several lines (real content, not verbatim);
none = not in the transcript.
"""

from ..constants import PeopleEvidenceStatus
from .participant_refs import name_appears_in_text, resolve_speaker_label


__all__ = ['check_people_evidence', 'check_quote_evidence']


def check_quote_evidence(source_quote, transcript_text):
    """
    Step a): is the quote in the transcript?

    Returns:
        (PeopleEvidenceStatus.OK, None), or
        (PeopleEvidenceStatus.QUOTE_NOT_FOUND, {'parts': n, 'parts_found': k})
    """
    if transcript_text.contains(source_quote):
        return PeopleEvidenceStatus.OK, None
    parts = transcript_text.quote_parts(source_quote)
    return PeopleEvidenceStatus.QUOTE_NOT_FOUND, {
        'parts': len(parts),
        'parts_found': sum(1 for part in parts if transcript_text.contains(part)),
    }


def check_people_evidence(full_name, source_quote, transcript_text):
    """
    Args:
        full_name:       str | None -- the person's name as written by the LLM.
        source_quote:    str -- the quote the role rests on.
        transcript_text: transcript_text.TranscriptText of the run.

    Returns:
        PeopleEvidenceStatus
    """
    status, _detail = check_quote_evidence(source_quote, transcript_text)
    if status != PeopleEvidenceStatus.OK:
        return status
    label = resolve_speaker_label(full_name, transcript_text.labels)
    if label is not None and not (
        transcript_text.said_by(source_quote, label)
        or name_appears_in_text(full_name, source_quote)
    ):
        return PeopleEvidenceStatus.QUOTE_NOT_ABOUT_PERSON
    return PeopleEvidenceStatus.OK
