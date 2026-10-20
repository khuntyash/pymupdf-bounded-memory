"""Tests for parity.same_output(). They define what "the same output" means."""
import hashlib
import re

import pymupdf

from parity import same_output


def _write(path, texts, cropbox_on_page=None, box_on_page=None):
    doc = pymupdf.open()
    for text in texts:
        doc.new_page(width=300, height=200).insert_text((20, 40), text)
    if cropbox_on_page is not None:
        doc[cropbox_on_page].set_cropbox(pymupdf.Rect(0, 0, 300, 150))
    if box_on_page is not None:  # a graphic with no text, like a barcode
        doc[box_on_page].draw_rect(pymupdf.Rect(150, 60, 250, 120), fill=(0, 0, 0))
    doc.save(str(path))
    doc.close()
    return str(path)


def _md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def test_two_saves_of_the_same_content_are_the_same_output(tmp_path):
    a = _write(tmp_path / "a.pdf", ["ORDER 1", "ORDER 2"])
    b = _write(tmp_path / "b.pdf", ["ORDER 1", "ORDER 2"])
    assert _md5(a) != _md5(b), "the bytes differ (fresh trailer /ID on every save)..."
    assert same_output(a, b) == [], "...but the output is the same"


def test_a_different_page_count_is_a_difference(tmp_path):
    a = _write(tmp_path / "a.pdf", ["ORDER 1", "ORDER 2"])
    b = _write(tmp_path / "b.pdf", ["ORDER 1"])
    assert same_output(a, b) != []


def test_a_different_crop_box_is_a_difference(tmp_path):
    a = _write(tmp_path / "a.pdf", ["ORDER 1", "ORDER 2"])
    b = _write(tmp_path / "b.pdf", ["ORDER 1", "ORDER 2"], cropbox_on_page=1)
    diffs = same_output(a, b)
    assert len(diffs) == 1 and re.search(r"\bpage 1\b", diffs[0]), diffs  # names the page (0-based)


def test_different_text_is_a_difference(tmp_path):
    a = _write(tmp_path / "a.pdf", ["ORDER 1", "ORDER 2"])
    b = _write(tmp_path / "b.pdf", ["ORDER 1", "ORDER 3"])
    diffs = same_output(a, b)
    assert len(diffs) == 1 and re.search(r"\bpage 1\b", diffs[0]), diffs


def test_a_change_with_no_text_is_still_a_difference(tmp_path):
    a = _write(tmp_path / "a.pdf", ["ORDER 1", "ORDER 2"])
    b = _write(tmp_path / "b.pdf", ["ORDER 1", "ORDER 2"], box_on_page=1)
    diffs = same_output(a, b)
    assert len(diffs) == 1 and re.search(r"\bpage 1\b", diffs[0]), diffs
