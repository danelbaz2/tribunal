"""Reads PDF, TXT and MD, and refuses what cannot be tried.

A charge file may arrive with no question in it -- a document that accuses
nobody of anything -- and a scanned PDF yields empty or scrambled text while
looking perfectly well-formed. Both must fail **loudly at upload**. The
alternative is three confident verdicts about nothing, which is worse than an
error because it looks like a result.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader


class ChargeFileRejected(ValueError):
    """The document cannot be tried. Raised at upload, never later."""


#: A charge shorter than this cannot carry an accusation anyone could argue
#: for three hundred words. It is a floor, not a judgement of quality.
MIN_WORDS = 25

#: A PDF whose pages yield less than this is treated as having no text layer:
#: a scan, or an extraction that produced garbage.
MIN_CHARS_PER_PAGE = 40


@dataclass(frozen=True)
class Extraction:
    text: str
    word_count: int
    pages: int | None
    has_text_layer: bool
    title: str


def count_words(text: str) -> int:
    return len(text.split())


def derive_title(text: str) -> str:
    """A short handle for the case, taken from its own first line.

    Display only. Nothing downstream reads it, and no prompt ever contains it.
    """
    for line in text.splitlines():
        stripped = line.strip().lstrip("# ").strip()
        if stripped:
            return stripped[:200]
    return "Untitled charge"


def extract_pdf(data: bytes) -> tuple[str, int, bool]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as error:  # pypdf raises a family of its own
        raise ChargeFileRejected(f"That PDF could not be read: {error}") from error

    pages = len(reader.pages)
    parts = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(part.strip() for part in parts if part.strip())

    # Extraction that produces almost nothing per page is a scan, not a
    # document. Say so rather than deliberating on the residue.
    has_text_layer = pages > 0 and len(text) >= MIN_CHARS_PER_PAGE * min(pages, 2)
    return text, pages, has_text_layer


def read(data: bytes, filename: str) -> Extraction:
    """Extract, then decide whether this can be tried at all."""
    lowered = filename.lower()

    if lowered.endswith(".pdf"):
        text, pages, has_text_layer = extract_pdf(data)
    elif lowered.endswith((".txt", ".md")):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ChargeFileRejected("That file is not UTF-8 text.") from error
        pages, has_text_layer = None, True
    else:
        raise ChargeFileRejected("Only PDF, TXT and MD are accepted.")

    text = _normalise(text)
    words = count_words(text)

    if not has_text_layer or words == 0:
        raise ChargeFileRejected(
            "No extractable text in that document. A scanned page is not a charge "
            "file; supply one with a text layer."
        )
    if words < MIN_WORDS:
        raise ChargeFileRejected(
            f"A charge of {words} words is too short to argue. Supply at least {MIN_WORDS}."
        )

    return Extraction(
        text=text,
        word_count=words,
        pages=pages,
        has_text_layer=has_text_layer,
        title=derive_title(text),
    )


def read_text(text: str) -> Extraction:
    """The pasted-text path. The same refusals apply."""
    cleaned = _normalise(text)
    words = count_words(cleaned)

    if words == 0:
        raise ChargeFileRejected("The charge file is empty. There is nothing here to try.")
    if words < MIN_WORDS:
        raise ChargeFileRejected(
            f"A charge of {words} words is too short to argue. Supply at least {MIN_WORDS}."
        )

    return Extraction(
        text=cleaned,
        word_count=words,
        pages=None,
        has_text_layer=True,
        title=derive_title(cleaned),
    )


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()
