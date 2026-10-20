"""Prove that a memory fix did not change the output.

PARITY IS NOT BYTE EQUALITY. Two saves of the *same* document produce different bytes,
because PyMuPDF writes a fresh random ``/ID`` into the PDF trailer on every save. A
byte-for-byte or MD5 comparison therefore fails even when nothing changed, and a "fix"
that really did change the output would hide among those false alarms.

So compare what a user of the output actually depends on, page by page.
"""
from __future__ import annotations

from typing import List

import pymupdf

# Crop boxes are compared rounded to 0.01 pt (1/7200 inch, far below what a thermal
# printer can show), so float noise from a different code path is not a false alarm.
_PLACES = 2


def same_output(path_a: str, path_b: str) -> List[str]:
    """Compare two output PDFs and return a list of human-readable differences.

    An empty list means "the same output". Each difference is a short message naming
    the page, counted from 0 like ``page.number``, e.g. ``"page 3: text differs"``.

    Rules (``tests/test_parity.py`` checks each one):
      - a different page count is a difference
      - a page whose size / crop box differs is a difference
      - a page whose extracted text differs is a difference
      - a page that renders differently is a difference (catches image-only changes)
      - a PDF that differs ONLY in its trailer /ID (i.e. saved twice) is NOT a difference
    """
    with pymupdf.open(path_a) as doc_a, pymupdf.open(path_b) as doc_b:
        if doc_a.page_count != doc_b.page_count:
            return [f"page count differs: {doc_a.page_count} vs {doc_b.page_count}"]

        # One message per page: the first check that fails. A different crop box always
        # renders differently too, so reporting both would only repeat the same change.
        diffs = []
        for i, (a, b) in enumerate(zip(doc_a, doc_b)):
            box_a = tuple(round(v, _PLACES) for v in a.cropbox)
            box_b = tuple(round(v, _PLACES) for v in b.cropbox)
            if box_a != box_b:
                diffs.append(f"page {i}: crop box differs: {box_a} vs {box_b}")
            elif a.get_text("text") != b.get_text("text"):
                diffs.append(f"page {i}: text differs")
            # A low-resolution render: labels are mostly images and barcodes, which have
            # no text, so a text check alone would miss a changed or missing image.
            elif a.get_pixmap(dpi=30).digest != b.get_pixmap(dpi=30).digest:
                diffs.append(f"page {i}: rendering differs")
        return diffs
