# pymupdf-bounded-memory

[![tests](https://github.com/khuntyash/pymupdf-bounded-memory/actions/workflows/tests.yml/badge.svg)](https://github.com/khuntyash/pymupdf-bounded-memory/actions/workflows/tests.yml)

Keep PyMuPDF's hidden C-level memory small while walking large PDFs.

## The problem

PyMuPDF wraps MuPDF, a C library. MuPDF caches parsed content streams, fonts and images in a store that Python's garbage collector cannot see, so `del page` and `gc.collect()` do not free it. A plain page loop fills that store and keeps it full until the document closes, separately in every worker process:

```python
with pymupdf.open(path) as doc:
    for page in doc:
        page.get_pixmap()   # each rendered page adds to MuPDF's store
```

Nothing looks wrong in code review. The document is closed properly and no Python object is kept.

I hit this in production in a live SaaS I co-founded that crops and sorts e-commerce shipping-label PDFs (Python/FastAPI on Google Cloud Run):

- **The failure.** A 4,000-page crop job peaked at **11,794 MB**, 96% of the service's 12 GiB limit. An 8 GiB instance had already been killed for running out of memory.
- **Why it hid.** Per-process logging showed only 694 MB for the same job. The job fans out to worker processes, and the memory was in *their* MuPDF stores, not the parent's. The first investigation was measuring the wrong process.
- **After the fix**, measured over the whole process tree on a 1,681-page file: peak **4,230 MB → 746 MB**. It also got faster: **23.0 s → 18.3 s**.
- **On the text-extraction path**, on a 1,681-page file: **1,201 MB → 78 MB**, with identical extracted records.

## The fix

```python
from bounded_pages import pages_releasing_store

with pymupdf.open(path) as doc:
    for i, page in pages_releasing_store(doc):          # every=10 by default
        page.get_pixmap()
```

[`pages_releasing_store()`](bounded_pages.py) yields the same pages and calls `pymupdf.TOOLS.store_shrink(100)` every 10 pages, always *between* pages, never in the middle of the caller's work on one.

**Releasing cannot change the output.** The store is only a cache, and MuPDF re-parses whatever it needs again. Two tests check this: one compares text and rendering with and without releasing, and the other releases while a page is still in use.

**Why every 10 pages:** on that 1,681-page file, 10 was the knee. Peak memory was 60 MB, against 54 MB when releasing after every page (which ran slightly slower) and 1,192 MB without releasing.

## Proving the output did not change

Comparing the output files byte for byte does not work. PyMuPDF writes a new random `/ID` into the PDF trailer on every save, so two saves of the *same* document differ; a test shows this, too. [`parity.same_output()`](parity.py) compares what users of the output depend on instead: page count, and for every page its crop box, its text and a low-resolution render. Labels are mostly images and barcodes, which have no text, so a text check alone would miss a changed image.

## Benchmark (synthetic data)

From the repository root:

```bash
python -m bench.run_benchmark --pages 1500
```

This generates a fake 1,500-page label PDF; every name, order number and address in it is made up. It then crops every page the way a label job does: read the text, render a preview, copy the label area into a new PDF. The PDF generation and each setting run in separate processes, because peak memory lasts for the whole process.

Median of 3 runs on Windows 10, Python 3.14, PyMuPDF 1.28.0 (MB = MiB):

| Release the store every | Peak memory | Time | Output vs. baseline |
|---|---|---|---|
| off (plain loop) | 243 MB | 6.4 s | baseline |
| 1 page | 62 MB | 11.4 s | identical |
| **10 pages (default)** | **62 MB** | **6.5 s** | identical |
| 50 pages | 67 MB | 6.1 s | identical |

Without releasing, this synthetic file fills MuPDF's store to its default limit (256 MB per process) and stays there. Real label files went much further: one process reached 1.2 GB, and production runs several worker processes, each with its own store. On this small file the release at every 10 pages costs about 0.1 s. Releasing after every single page saves no extra memory and nearly doubles the time.

## Run it

From the repository root:

```bash
pip install -r requirements.txt
pytest
python -m bench.run_benchmark
```

## How I work

I build with Claude Code as my coding agent. I plan the change, let the agent write it, review every diff, and measure before I ship. This repository is a cleaned-up extract of the production helper (the original fix shipped in August 2026), rebuilt around synthetic data so it can be public.

## License

MIT, for the code in this repository. PyMuPDF itself is licensed separately (AGPL-3.0 or a commercial licence from Artifex).
