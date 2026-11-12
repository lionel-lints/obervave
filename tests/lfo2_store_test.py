#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Saved before LFO 2, loaded with it: tests/lfo2_store/store_v3.bin is a simulated flash written by the firmware before
LFO 2 (make_old.txt: a user program over 07, pattern 1 with steps and its four sounds); old_play.log its dump and
old_play.md5 the sound of that pattern played on it by the firmware just before LFO 2 (b68a1c5, OSC 2's drift in). The firmware now boots on it (OBV_STORE): every program and
pattern sound comes through, its 63 parameters and its name, LFO 2 off (patch_from_v3); the pattern plays bit for bit
as it did; it writes the store back in the new layout, and a second boot on that loads the same again. Exit 1 on a failure."""
import hashlib, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "host"
D = ROOT / "tests" / "lfo2_store"
NP_OLD, NAME, BYTES = 63, 10, 80
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("  ok    " if ok else "  FAIL  ") + name + ("" if ok else f"  ({detail})"))
    fails += not ok


def dumps(log):
    return {m[1]: bytes.fromhex(m[2]) for m in re.finditer(r"(PROG \d+|PSND \d+ \d+) ([0-9a-f]{160})", log)}


def convert(old, defaults):
    """the old layout -> the new: 63 parameters, LFO 2's seven at their defaults, the name behind them"""
    return old[:NP_OLD] + bytes(defaults) + old[NP_OLD:NP_OLD + NAME]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = OUT / "lfo2-smk37"
    subprocess.run([os.environ.get("CC", "cc"), "-O2", "-w", "-DOBV_HOST", "-DBOARD_SMK37=1", '-DAPP_VER="test"', "-I" + str(ROOT / "firmware/src"),
                    "-I" + str(ROOT / "firmware/gen"), "-o", str(b), str(ROOT / "firmware/src/obervave.c")], check=True)
    src = (ROOT / "firmware/src/obv_params.h").read_text()
    lfo2 = re.findall(r"\[P_L2_\w+\] = \{\"[^\"]*\", [^,]+, (\w+),", src)
    names = {"L_TRI": 0, "L2_OFF": 0}
    defaults = [int(x) if x.isdigit() else names[x] for x in lfo2]
    old = dumps((D / "old_play.log").read_text())
    store = OUT / "lfo2_store.bin"
    shutil.copy(D / "store_v3.bin", store)
    env = {**os.environ, "OBV_STORE": str(store)}
    for boot in (1, 2):
        r = subprocess.run([str(b), str(OUT / f"lfo2-play{boot}"), str(D / "play.txt")], capture_output=True, text=True, env=env)
        new = dumps(r.stdout)
        what = "on the old store" if boot == 1 else "again, on the store it wrote back"
        check(f"boot {boot} ({what}): every saved program and pattern sound is there", sorted(new) == sorted(old) and len(old) >= 5,
              (sorted(old), sorted(new)))
        check(f"boot {boot}: each one's 63 parameters and name as saved, LFO 2 off (its defaults)",
              all(new.get(k) == convert(v, defaults) for k, v in old.items()), [k for k, v in old.items() if new.get(k) != convert(v, defaults)])
        md5 = hashlib.md5((OUT / f"lfo2-play{boot}.wav").read_bytes()).hexdigest()
        check(f"boot {boot}: the pattern plays bit for bit as on the firmware before LFO 2", md5 == (D / "old_play.md5").read_text().strip(), md5)
        if boot == 1:
            check("boot 1 writes the programs back (the new layout)", "programs 0 saved" in r.stdout, r.stdout[-300:])
    print("LFO 2 and the patches saved before it: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
