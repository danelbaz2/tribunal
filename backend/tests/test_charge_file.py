"""Pitfalls 3 and 13 -- refuse at upload, not at the verdict."""

from __future__ import annotations

import pytest

from app import charge_file


def test_the_reference_case_is_accepted(reference_charge):
    extraction = charge_file.read_text(reference_charge)

    assert extraction.word_count > charge_file.MIN_WORDS
    assert extraction.has_text_layer
    assert extraction.title == "Kestrel Wharf — the diverted pump"


@pytest.mark.parametrize("body", ["", "   ", "\n\n\t\n"])
def test_an_empty_charge_is_refused(body):
    with pytest.raises(charge_file.ChargeFileRejected, match="empty"):
        charge_file.read_text(body)


def test_a_charge_too_short_to_argue_is_refused():
    with pytest.raises(charge_file.ChargeFileRejected, match="too short"):
        charge_file.read_text("He did it.")


def test_a_txt_file_is_read(reference_charge):
    extraction = charge_file.read(reference_charge.encode("utf-8"), "case.txt")

    assert extraction.pages is None
    assert extraction.word_count > charge_file.MIN_WORDS


def test_an_unsupported_extension_is_refused(reference_charge):
    with pytest.raises(charge_file.ChargeFileRejected, match="PDF, TXT and MD"):
        charge_file.read(reference_charge.encode("utf-8"), "case.docx")


def test_a_file_that_is_not_utf8_text_is_refused():
    with pytest.raises(charge_file.ChargeFileRejected, match="not UTF-8"):
        charge_file.read(b"\xff\xfe\x00\x01 binary", "case.txt")


def test_a_pdf_with_no_text_layer_is_refused():
    """A scan yields empty or scrambled text and looks perfectly well-formed.
    The trial must not proceed on the residue."""
    scanned = _pdf_with_no_text()

    with pytest.raises(charge_file.ChargeFileRejected, match="No extractable text"):
        charge_file.read(scanned, "scan.pdf")


def test_an_unreadable_pdf_is_refused():
    with pytest.raises(charge_file.ChargeFileRejected, match="could not be read"):
        charge_file.read(b"not a pdf at all", "broken.pdf")


def _pdf_with_no_text() -> bytes:
    """A single blank page: valid PDF, no text layer. Built here rather than
    committed, so the suite carries no binary it cannot explain."""
    from pypdf import PdfWriter

    import io

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
