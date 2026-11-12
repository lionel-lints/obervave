#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The wheels glide (obv_engine.h block_globals: bend_sm, vib_sm): the pitch wheel reads in ~3-cent counts about once a
main-loop pass, and a slow bend was a staircase of those. Traced every audio block (16 samples, OBV_PITCH_TRACE):
a slow bend moves in steps no bigger than the engine's finest (1/256 semitone); a flick still arrives within
~60 ms; the rest brings the pitch back exactly; the mod wheel's vibrato depth glides too. SMK-37 host build.
Exit 1 on a failure."""
import math, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "host"
BLOCK_MS = 16 / 44.1
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("  ok    " if ok else "  FAIL  ") + name + ("" if ok else f"  ({detail})"))
    fails += not ok


def trace(b, script):
    r = subprocess.run([str(b), str(OUT / "bend"), str(ROOT / "tests/bend" / script)], capture_output=True, text=True,
                       env={**os.environ, "OBV_PITCH_TRACE": "1"})
    p = [int(l.split()[1]) for l in r.stderr.splitlines() if l.startswith("P ")]
    v = [int(l.split()[1]) for l in r.stderr.splitlines() if l.startswith("V ")]
    return [1200 * math.log2(x / p[0]) for x in p], v


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = OUT / "bend-smk37"
    subprocess.run([os.environ.get("CC", "cc"), "-O2", "-w", "-DOBV_HOST", "-DBOARD_SMK37=1", '-DAPP_VER="test"', "-I" + str(ROOT / "firmware/src"),
                    "-I" + str(ROOT / "firmware/gen"), "-o", str(b), str(ROOT / "firmware/src/obervave.c")], check=True)
    c, _ = trace(b, "slow_up.txt")
    i0 = next(i for i in range(1, len(c)) if c[i] != c[0])
    i1 = max(i for i in range(1, len(c)) if c[i] != c[i - 1])
    steps = [abs(c[i] - c[i - 1]) for i in range(i0, i1 + 1)]
    check(f"a slow bend: no step over 0.5 cents (largest {max(steps):.2f}; it was 3.1, a ~3-cent count each)", max(steps) < 0.5, max(steps))
    check(f"... all the way: +{c[-1]:.0f} cents (2 semitones)", abs(c[-1] - 200) < 1, c[-1])
    c, v = trace(b, "flick.txt")
    peak = max(c)
    k_up = next(i for i in range(len(c)) if c[i] > 0.5)
    k_there = next(i for i in range(k_up, len(c)) if c[i] > peak - 2)
    check(f"a flick up: there (within 2 cents) {(k_there - k_up) * BLOCK_MS:.0f} ms after it starts moving (under 60)",
          (k_there - k_up) * BLOCK_MS < 60 and abs(peak - 200) < 1, ((k_there - k_up) * BLOCK_MS, peak))
    k_peak = c.index(peak)
    k_down = next(i for i in range(k_peak, len(c)) if c[i] < peak - 0.5)
    rest = c[k_down + int(150 / BLOCK_MS)]
    check(f"released: back exactly to the note's pitch ({rest:+.2f} cents, 150 ms later)", rest == 0, rest)
    first = next(i for i in range(len(v)) if v[i] > 0)
    top = max(v)
    check("the mod wheel thrown up: the vibrato depth glides (no jump: under a tenth in its first block)", 0 < v[first] < top / 10, (v[first], top))
    k = next(i for i in range(first, len(v)) if v[i] >= top * 0.98)
    check(f"... and arrives ({(k - first) * BLOCK_MS:.0f} ms to 98%, under 60)", (k - first) * BLOCK_MS < 60 and top == 127 * 256, ((k - first) * BLOCK_MS, top))
    check("the mod wheel back down: no vibrato left", v[-1] == 0, v[-1])
    print("the wheels glide: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
