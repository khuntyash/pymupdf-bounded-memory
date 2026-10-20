"""Generate a large, fully synthetic "shipping label" PDF for the benchmark.

Every name, order number and address here is made up. Each page carries its own image
plus text, so rendering the pages fills MuPDF's store the way real label files do.
"""
from __future__ import annotations

import argparse
import random

import pymupdf


def make_pdf(path: str, pages: int, seed: int = 1) -> None:
    rnd = random.Random(seed)
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)  # A4, like a marketplace label sheet

        # Each page gets its own 400x400 "barcode" image (40 random colour bands) inside the
        # label area; the font is shared. Built from raw bytes: per-pixel calls take ~0.4 s
        # a page.
        bands = (bytes(rnd.randrange(256) for _ in range(3)) * 400 * 10 for _ in range(40))
        pix = pymupdf.Pixmap(pymupdf.csRGB, 400, 400, b"".join(bands), False)
        page.insert_image(pymupdf.Rect(330, 150, 530, 350), pixmap=pix)

        # One insert_text call per block: each call costs milliseconds, so a call per line
        # made generating a 600-page file take minutes.
        header = (
            f"ORDER {i + 1:06d}   SKU-{rnd.randrange(10**6):06d}\n"
            f"Ship to: Test Customer {i + 1:04d}\n"
            f"{rnd.randrange(1, 999)} Example Street, Sample City 000000"
        )
        items = "\n".join(f"item {line + 1}  qty {rnd.randrange(1, 9)}" for line in range(25))
        page.insert_text((60, 70), header, fontsize=12)
        page.insert_text((60, 150), items, fontsize=8)
    doc.save(path, deflate=True)
    doc.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--pages", type=int, default=1500)
    args = ap.parse_args()
    make_pdf(args.path, args.pages)
    print(f"wrote {args.pages} synthetic pages to {args.path}")
