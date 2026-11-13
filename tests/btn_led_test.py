#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""A page button stays lit on every page it cycles through: each of HOME (PERFORM, then the MIXER and its rows; the
SMK-37's PATCH went dark there), EDIT, ENV, LFO (five pages with LFO 2), FX and GLO tapped 9 times, its LED checked in
every frame (the host film's log). The LED logic is shared; the FM-1 build, whose button ids fit the log. Exit 1 on a
failure."""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "host" / "btnled"
BTN = {"HOME": 8, "EDIT": 6, "ENV": 4, "LFO": 5, "FX": 2, "GLO": 7}   # platform.c, the FM-1's ids
TAPS, GAP = 9, 400


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = OUT / "host"
    subprocess.run([os.environ.get("CC", "cc"), "-O2", "-w", "-DOBV_HOST", '-DAPP_VER="test"', "-I" + str(ROOT / "firmware/src"),
                    "-I" + str(ROOT / "firmware/gen"), "-o", str(b), str(ROOT / "firmware/src/obervave.c")], check=True)
    fails = 0
    for name, bid in BTN.items():
        t0 = 3000
        lines = [f"{t0 + i * GAP} btn {bid}" for i in range(TAPS)] + [f"{t0 + TAPS * GAP + 300} end"]
        p = OUT / f"{name}.txt"
        p.write_text("\n".join(lines) + "\n")
        subprocess.run([str(b), str(OUT / name), str(p), "20"], capture_output=True, check=True)
        dark = [int(l.split()[0]) for l in (OUT / f"{name}-log.txt").read_text().splitlines()
                if int(l.split()[0]) > t0 + 100 and not int(l.split()[3]) >> bid & 1]
        ok = not dark
        print(("  ok    " if ok else "  FAIL  ") + f"{name}: lit through {TAPS} taps" + ("" if ok else f"  (dark at {dark[0]} ms .. {len(dark)} frames)"))
        fails += not ok
    print("button LEDs: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
