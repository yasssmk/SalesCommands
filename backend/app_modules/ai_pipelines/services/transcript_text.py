# app_modules/ai_pipelines/services/transcript_text.py
"""
Read a transcript as text: normalisation, speaker labels, "who said this
quote" (TD-279 V). Promoted from the evals/td279 measurement script, which
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
"""

import re


__all__ = [
    'TranscriptText',
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
# spaces, apostrophes, dots and hyphens only (no "/", no ":").
_SPEAKER_LINE_RE = re.compile(r"^\s*([^\W\d_][\w'’.\- ]*?)\s?:\s+(.*\S)\s*$")


def normalize_text(text):
    """The normalised form used for every comparison (module docstring)."""
    text = str(text or '').lower()
    text = text.translate(_APOSTROPHES).translate(_DROPPED_QUOTES)
    text = _ELLIPSIS_RE.sub(' ', text)
    return ' '.join(text.split()).strip(_EDGE_PUNCTUATION)


def _speaker_line(line):
    """(label, utterance) for a "Label: text" line, else None."""
    match = _SPEAKER_LINE_RE.match(line)
    if match is None:
        return None
    label = ' '.join(match.group(1).split())
    if len(label.split()) > _MAX_LABEL_WORDS:
        return None
    return label, match.group(2)


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
