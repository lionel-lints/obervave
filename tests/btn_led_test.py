#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""A page button stays lit on every page it cycles through: each of HOME (PERFORM, then the MIXER and its rows; the
SMK-37's PATCH went dark there), EDIT, ENV, LFO (five pages with LFO 2), FX and GLO tapped 9 times, its LED checked in
every frame (the host film's log); HOME tapped round comes back to PERFORM after the mixer's rows. The LED logic is shared; the FM-1 build, whose button ids fit the log. Exit 1 on a
failure."""
import os, re, subprocess, sys
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
    # HOME round: PERFORM, the MIXER's 7 rows, PERFORM again (it wrapped to the mixer's LEVEL row for good). KNOB 1
    # turned after n taps: on PERFORM it is the CUTOFF (the live sound's byte moves), on the mixer a track's level
    src = (ROOT / "firmware/src/obv_params.h").read_text()
    e = src[src.index("P_O1_WAVE"):]
    cut = re.findall(r"P_[A-Z0-9_]+", e[:e.index("}")]).index("P_CUTOFF")
    for taps, perform in ((1, True), (2, False), (8, False), (9, True), (10, False)):
        lines = [f"2600 btn {BTN['EDIT']}"] + [f"{3000 + i * GAP} btn {BTN['HOME']}" for i in range(taps)]   # (from another page)
        t = 3000 + taps * GAP
        lines += [f"{t} patches", f"{t + 100} enc 2 5", f"{t + 300} patches", f"{t + 500} end"]
        p = OUT / f"round{taps}.txt"
        p.write_text("\n".join(lines) + "\n")
        out = subprocess.run([str(b), str(OUT / f"round{taps}"), str(p)], capture_output=True, text=True).stdout
        cv = [int(m[1][2 * cut:2 * cut + 2], 16) for m in re.finditer(r"LIVE 0 ([0-9a-f]+)", out)]
        ok = (cv[1] != cv[0]) == perform
        print(("  ok    " if ok else "  FAIL  ") + f"HOME x{taps}: {'PERFORM (KNOB 1 the cutoff)' if perform else 'the mixer'}"
              + ("" if ok else f"  (cutoff {cv})"))
        fails += not ok
    print("button LEDs: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
