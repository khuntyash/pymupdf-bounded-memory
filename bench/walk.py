"""One benchmark run: crop every page of a label PDF, in a fresh process.

The workload has the same shape as a real label-cropping job: for each page, read its
text, render a small preview, and copy the label area into a new output PDF. It prints
one JSON line with the peak memory and the time taken.

Run directly:  python -m bench.walk input.pdf output.pdf --every 10
"""
from __future__ import annotations

import argparse
import json
import time

import pymupdf

from bench.peak_memory import peak_rss_mb
from bounded_pages import pages_releasing_store

LABEL_AREA = pymupdf.Rect(0, 0, 595, 430)  # top half of an A4 sheet


def crop_labels(src_path: str, out_path: str, every: int) -> dict:
    start = time.perf_counter()
    with pymupdf.open(src_path) as src, pymupdf.open() as out:
        for i, page in pages_releasing_store(src, every=every):
            page.get_text("text")             # e.g. read the order number
            page.get_pixmap(dpi=36)           # e.g. a preview, or OCR preparation
            target = out.new_page(width=LABEL_AREA.width, height=LABEL_AREA.height)
            target.show_pdf_page(target.rect, src, i, clip=LABEL_AREA)
        pages = src.page_count
        out.save(out_path, garbage=3, deflate=True)
    return {
        "every": every,
        "pages": pages,
        "peak_mb": round(peak_rss_mb()),
        "seconds": round(time.perf_counter() - start, 1),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--every", type=int, default=10)
    args = ap.parse_args()
    print(json.dumps(crop_labels(args.src, args.out, args.every)))
