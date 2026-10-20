"""Measure peak memory with and without releasing MuPDF's store, then check parity.

Run from the repository root:

    python -m bench.run_benchmark --pages 1500

Everything heavy runs in subprocesses: generating the PDF, and each configuration. Peak
memory is a process-lifetime value, so measuring two configurations in one process would
report the larger peak twice, and a big parent could leak its own peak into the children.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

from parity import same_output

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(*args: str) -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-m", *args], cwd=ROOT, capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, file=sys.stderr)
        raise
    return result.stdout


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pages", type=int, default=1500)
    ap.add_argument("--every", type=int, nargs="+", default=[1, 10, 50],
                    help="settings to compare against the baseline (release off)")
    args = ap.parse_args()
    settings = [0] + [e for e in args.every if e != 0]  # the baseline always runs first

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "labels.pdf")
        _run("bench.make_synthetic_pdf", src, "--pages", str(args.pages))

        runs = []
        for n, every in enumerate(settings):
            out = os.path.join(tmp, f"out_{n}_every_{every}.pdf")
            stats = json.loads(_run("bench.walk", src, out, "--every", str(every)).strip().splitlines()[-1])
            runs.append((every, out, stats))

        # Parity is checked only after every measured run has finished.
        print(f"{args.pages} synthetic pages\n")
        print(f"{'every':>7} {'peak MB':>9} {'seconds':>9}  output vs. baseline")
        baseline_out = runs[0][1]
        for every, out, stats in runs:
            if every == 0:
                verdict = "(baseline)"
            else:
                diffs = same_output(baseline_out, out)
                verdict = "identical" if not diffs else f"{len(diffs)} differences: {diffs[:3]}"
            label = "off" if every == 0 else str(every)
            print(f"{label:>7} {stats['peak_mb']:>9} {stats['seconds']:>9}  {verdict}")


if __name__ == "__main__":
    main()
