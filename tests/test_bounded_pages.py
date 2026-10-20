from unittest import mock

import pymupdf
import pytest

from bounded_pages import pages_releasing_store


def _doc(pages: int) -> pymupdf.Document:
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"page {i}")
    return doc


def _count_shrinks():
    calls = []
    patch = mock.patch.object(pymupdf.TOOLS, "store_shrink", side_effect=calls.append)
    return patch, calls


def test_yields_every_page_in_order():
    with _doc(7) as doc:
        assert [i for i, _ in pages_releasing_store(doc)] == list(range(7))


def test_yields_only_the_requested_indices():
    with _doc(7) as doc:
        got = [(i, page.number) for i, page in pages_releasing_store(doc, [5, 1, 3])]
    assert got == [(5, 5), (1, 1), (3, 3)]


def test_empties_the_store_every_n_pages():
    patch, calls = _count_shrinks()
    with patch, _doc(25) as doc:
        list(pages_releasing_store(doc, every=10))
    assert calls == [100, 100]  # after page 10 and page 20, never for the last 5


def test_every_zero_never_touches_the_store():
    patch, calls = _count_shrinks()
    with patch, _doc(25) as doc:
        list(pages_releasing_store(doc, every=0))
    assert calls == []


def test_store_is_emptied_between_pages_never_during_one():
    events = []
    patch = mock.patch.object(pymupdf.TOOLS, "store_shrink", side_effect=lambda _: events.append("shrink"))
    with patch, _doc(4) as doc:
        for i, page in pages_releasing_store(doc, every=2):
            events.append(f"got {i}")
            page.get_text()
            events.append(f"done {i}")
    assert events == ["got 0", "done 0", "got 1", "done 1", "shrink",
                      "got 2", "done 2", "got 3", "done 3", "shrink"]


def test_a_failing_store_call_warns_once_and_the_walk_goes_on():
    patch = mock.patch.object(pymupdf.TOOLS, "store_shrink", side_effect=RuntimeError("gone"))
    with patch, _doc(5) as doc, pytest.warns(RuntimeWarning, match="no longer being released") as caught:
        assert len(list(pages_releasing_store(doc, every=1))) == 5
    assert len(caught) == 1


@pytest.mark.parametrize("bad", [-1, 2.5, True, "10"])
def test_a_bad_every_is_rejected_at_call_time(bad):
    with _doc(1) as doc, pytest.raises(ValueError):
        pages_releasing_store(doc, every=bad)


def test_real_store_release_does_not_change_text_or_rendering():
    with _doc(30) as doc:
        def run(every):
            return [(page.get_text(), page.get_pixmap(dpi=30).digest)
                    for _, page in pages_releasing_store(doc, every=every)]
        baseline = run(0)
        assert run(1) == baseline


def test_releasing_while_a_page_is_held_does_not_change_it():
    # Even the worst moment, in the middle of a page's work, is safe: it is only a cache.
    with _doc(3) as doc:
        page = doc[1]
        before = (page.get_text(), page.get_pixmap(dpi=30).digest)
        pymupdf.TOOLS.store_shrink(100)
        assert (page.get_text(), page.get_pixmap(dpi=30).digest) == before
