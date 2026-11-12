#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""OSC 2 has its own vintage walk: the two oscillators of a voice drift apart and beat, as a VCO pair, by VINTAGE.
tests/drift/vintage_*.txt hold a note 12 s and read both oscillators' pitch every 200 ms (host "wheels"): VINTAGE 0
locked exactly; 30 a gentle wander; 127 a wide one; no lasting pull either way (the walks are alike, their bias
cancels). Exit 1 on a failure."""
import math, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "host"


def cents(script):
    b = OUT / "drift-fm1"
    out = subprocess.run([str(b), str(OUT / "drift"), str(ROOT / "tests/drift" / script)], capture_output=True, text=True).stdout
    c = [1200 * math.log2(int(m[2]) / int(m[1])) for m in re.finditer(r"voices=\d+:\d+:(\d+):(\d+)", out)]
    mean = sum(c) / len(c)
    return len(c), mean, (sum((x - mean) ** 2 for x in c) / len(c)) ** 0.5


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([os.environ.get("CC", "cc"), "-O2", "-w", "-DOBV_HOST", '-DAPP_VER="test"', "-I" + str(ROOT / "firmware/src"),
                    "-I" + str(ROOT / "firmware/gen"), "-o", str(OUT / "drift-fm1"), str(ROOT / "firmware/src/obervave.c")], check=True)
    fails = 0
    for script, ok_of, what in (
            ("vintage_0.txt", lambda n, m, s: s == 0 and m == 0, "VINTAGE 0: the two oscillators locked, exactly"),
            ("vintage_30.txt", lambda n, m, s: 0.5 < s < 4 and abs(m) < 3, "VINTAGE 30 (the default): a gentle wander (0.5-4 cents), no pull"),
            ("vintage_127.txt", lambda n, m, s: s > 4 and abs(m) < 6, "VINTAGE 127: a wide wander (over 4 cents), no lasting pull")):
        n, m, s = cents(script)
        ok = n >= 50 and ok_of(n, m, s)
        print(("  ok    " if ok else "  FAIL  ") + what + f"  ({n} readings, mean {m:+.2f}, sd {s:.2f} cents)")
        fails += not ok
    print("OSC 2 drift: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
