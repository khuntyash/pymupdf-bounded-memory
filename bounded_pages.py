"""Walk PDF pages while keeping MuPDF's object store small.

THE MEMORY IS NOT PYTHON'S. MuPDF, the C library under PyMuPDF, caches parsed content
streams, fonts and images in a process-wide store. Python's garbage collector cannot see
it: ``del page`` and ``gc.collect()`` do not release it. MuPDF evicts from the store only
once it reaches its size limit (256 MB by default), so a loop of this shape

    with pymupdf.open(path) as doc:
        for page in doc:
            page.get_pixmap()      # or any call that parses or renders the page

fills the store and keeps it full until the document closes, separately in EVERY worker
process. Nothing looks wrong in code review: the document is closed properly and no
Python object is retained. On real label files a single process reached 1.2 GB.

``pages_releasing_store`` walks the same pages and empties the store every ``every``
pages. Releasing cannot change any output: the store is a cache, and MuPDF re-parses
whatever it needs again on demand.
"""
from __future__ import annotations

import warnings
from typing import Iterable, Iterator, Optional, Tuple

import pymupdf

# 10 was the measured knee on a 1,681-page label file (text extraction): 60 MB peak,
# against 54 MB when releasing after every page (slightly slower) and 1,192 MB without.
DEFAULT_EVERY = 10


def pages_releasing_store(
    doc: pymupdf.Document,
    indices: Optional[Iterable[int]] = None,
    every: int = DEFAULT_EVERY,
) -> Iterator[Tuple[int, pymupdf.Page]]:
    """Yield ``(index, page)`` for ``indices`` (default: every page), emptying MuPDF's
    store every ``every`` pages. ``every=0`` turns the release off (a baseline).

    The store is emptied only BETWEEN pages, when the caller asks for the next one, so
    the caller's work on a page is never interrupted. The store is shared by the whole
    process, so other open documents lose their cached data too (they re-parse on
    demand).
    """
    if isinstance(every, bool) or not isinstance(every, int) or every < 0:
        raise ValueError(f"every must be an int >= 0, got {every!r}")
    if indices is None:
        indices = range(doc.page_count)
    return _walk(doc, indices, every)


def _walk(doc, indices, every):
    since_shrink = 0
    warned = False
    for i in indices:
        yield i, doc[i]
        since_shrink += 1
        if every and since_shrink >= every:
            since_shrink = 0
            try:
                pymupdf.TOOLS.store_shrink(100)  # 100 = free 100% of the store
            except Exception as exc:
                # A cache hint, not a correctness step, so the walk goes on. But say so
                # once: a silently disabled release would bring the memory problem back.
                if not warned:
                    warned = True
                    warnings.warn(
                        f"pymupdf.TOOLS.store_shrink failed ({exc!r}); "
                        "MuPDF's store is no longer being released",
                        RuntimeWarning,
                        stacklevel=2,
                    )
