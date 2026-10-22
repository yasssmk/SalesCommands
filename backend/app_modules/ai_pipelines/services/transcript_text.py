# app_modules/ai_pipelines/services/transcript_text.py
"""
Read a transcript as text: normalisation, speaker labels, "who said this
quote" (TD-279 V), a speaker label wrongly copied at the head of a quote
(strip_speaker_label). Promoted from the evals/td279 measurement script, which
now imports it -- one implementation.

No AI, no database. Used by the People evidence check
(people_evidence.check_people_evidence).

Normalisation (normalize_text)
------------------------------
Case, whitespace (any Unicode space, line breaks), typographic apostrophes
(’ ‘ ʼ ` ´ -> '), double quotes and guillemets (" “ ” „ « » ‹ › -> dropped)
and ellipses (… and "..." -> a space), then the punctuation around the text
is trimmed. Accents are kept: a quote is verbatim.

Speaker labels
--------------
A line "Name: text" (or "Name : text") whose label is 1 to
_MAX_LABEL_WORDS words starting with a letter -- the format of the meeting
exports ("Claire Dubois: Bonjour..."). A timestamp ("00:12:30"), a title
with a date ("... 2026/10/14 10:02 CEST ...") or a sentence never matches.

Header date (D7 / TD-281)
-------------------------
header_date(transcript): the meeting's date read on the export header (first
non-empty line, format TRANSCRIPT_HEADER_DATE_PATTERN in constants.py), as
ISO YYYY-MM-DD; None when there is no such header or the date is not a real
calendar date.
"""

import datetime
import re

from ..constants import TRANSCRIPT_HEADER_DATE_PATTERN


__all__ = [
    'TranscriptText',
    'header_date',
    'normalize_text',
]


# A speaker label is a short name, never a sentence.
_MAX_LABEL_WORDS = 5

_APOSTROPHES = str.maketrans({c: "'" for c in '’‘ʼ`´'})
_DROPPED_QUOTES = str.maketrans({c: ' ' for c in '"“”„«»‹›'})
_ELLIPSIS_RE = re.compile(r'…|\.{3,}')
# Characters trimmed around a normalised text (a quote cut mid-sentence by
# the model keeps or loses its final punctuation).
_EDGE_PUNCTUATION = " .,;:!?'-"

# "Label: text" -- the label starts with a letter and holds letters, digits,
# spaces, apostrophes, dots and hyphens only (no "/", no ":"). The same
# prefix reads a line of the transcript and the head of a quote.
_LABEL_PREFIX = r"^\s*([^\W\d_][\w'’.\- ]*?)\s?:\s+"
_SPEAKER_LINE_RE = re.compile(_LABEL_PREFIX + r"(.*\S)\s*$")
_QUOTE_LABEL_RE = re.compile(_LABEL_PREFIX)
_HEADER_DATE_RE = re.compile(TRANSCRIPT_HEADER_DATE_PATTERN)


def normalize_text(text):
    """The normalised form used for every comparison (module docstring)."""
    text = str(text or '').lower()
    text = text.translate(_APOSTROPHES).translate(_DROPPED_QUOTES)
    text = _ELLIPSIS_RE.sub(' ', text)
    return ' '.join(text.split()).strip(_EDGE_PUNCTUATION)


def header_date(transcript):
    """The meeting's date on the export header, ISO YYYY-MM-DD, else None
    (module docstring)."""
    first_line = next(
        (line for line in str(transcript or '').splitlines() if line.strip()),
        '',
    )
    match = _HEADER_DATE_RE.search(first_line)
    if match is None:
        return None
    try:
        return datetime.date(*(int(part) for part in match.groups())).isoformat()
    except ValueError:
        return None


def _label(match):
    """The label of a prefix match, whitespace collapsed; None when too long
    to be a name."""
    label = ' '.join(match.group(1).split())
    return label if len(label.split()) <= _MAX_LABEL_WORDS else None


def _speaker_line(line):
    """(label, utterance) for a "Label: text" line, else None."""
    match = _SPEAKER_LINE_RE.match(line)
    if match is None or _label(match) is None:
        return None
    return _label(match), match.group(2)


class TranscriptText:
    """
    A transcript read once: its normalised text and its labelled
    utterances.

    Attributes:
        labels:     list[str] -- the distinct speaker labels, in order of
                    first appearance ([] for a transcript without labels).
    """

    def __init__(self, transcript):
        self._normalized = normalize_text(transcript)
        self._utterances = []   # (label, normalised utterance)
        self.labels = []
        for line in str(transcript or '').splitlines():
            parsed = _speaker_line(line)
            if parsed is None:
                continue
            label, utterance = parsed
            self._utterances.append((label, normalize_text(utterance)))
            if label not in self.labels:
                self.labels.append(label)

    def strip_speaker_label(self, quote):
        """
        TD-279: the quote without a leading speaker label ("Claire Dubois:
        Bonjour" -> "Bonjour") -- removed ONLY when that prefix is a label of
        THIS transcript, never on any other ":" ("Objectif : ..."). Anything
        else (non-string included) is returned unchanged.
        """
        if not isinstance(quote, str):
            return quote
        match = _QUOTE_LABEL_RE.match(quote)
        if match is None or _label(match) not in self.labels:
            return quote
        return quote[match.end():]

    @property
    def has_speaker_labels(self):
        return bool(self.labels)

    def contains(self, quote):
        """Is the quote (normalised, non-empty) in the transcript?"""
        quote = normalize_text(quote)
        return bool(quote) and quote in self._normalized

    def said_by(self, quote, label):
        """Is the quote (normalised, non-empty) part of an utterance of
        the speaker `label`?"""
        quote = normalize_text(quote)
        return bool(quote) and any(
            quote in utterance
            for speaker, utterance in self._utterances
            if speaker == label
        )
