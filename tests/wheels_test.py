#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The wheels go to a track (firmware/src/wheel_route.h), end to end: each track's bend and vibrato and every sounding
voice's pitch (host "wheels") through K3 turns mid-bend, the next bend, the mod wheel following K3, a MIDI bend with
its own owner, two sources at once, MIDI channels B-D; a voice's pitch moves only on the track bent, and comes back
to exactly where it was. tests/wheels/*.txt; smk_tracks on the SMK-37, midi_channels on both boards. Exit 1 on a failure."""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "host"
IDS = {"fm1": {"GLOBE": "7", "MIDICH": "4"}, "smk37": {"GLOBE": "10", "MIDICH": "2"}}
UP2, UP1 = 2 ** (2 / 12), 2 ** (1 / 12)    # full bend (BEND 2), half bend
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("  ok    " if ok else "  FAIL  ") + name + ("" if ok else f"  ({detail})"))
    fails += not ok


def run(board, script):
    defs = ["-DBOARD_SMK37=1"] if board == "smk37" else []
    b = OUT / f"wheels-{board}"
    subprocess.run([os.environ.get("CC", "cc"), "-O2", "-w", "-DOBV_HOST", *defs, '-DAPP_VER="test"', "-I" + str(ROOT / "firmware/src"),
                    "-I" + str(ROOT / "firmware/gen"), "-o", str(b), str(ROOT / "firmware/src/obervave.c")], check=True)
    text = (ROOT / "tests/wheels" / script).read_text()
    for k, v in IDS[board].items():
        text = text.replace(f"btn {k}", f"btn {v}").replace(f"enc {k}", f"enc {v}")
    p = OUT / f"wheels-{board}-{script}"
    p.write_text(text)
    out = subprocess.run([str(b), str(OUT / f"wheels-{board}"), str(p)], capture_output=True, text=True).stdout
    snaps = {}
    for m in re.finditer(r"(\d+) ms  WHEELS sel=(\d) bend=([-\d,]+) vib=([-\d,]+) voices=(.*)", out):
        voices = {}
        for v in m[5].split():
            part, note, inc = map(int, v.split(":"))
            voices.setdefault(part, []).append(inc)
        snaps[int(m[1])] = (int(m[2]), list(map(int, m[3].split(","))), list(map(int, m[4].split(","))),
                            {k: sorted(x) for k, x in voices.items()})
    return snaps


def ratios(s, base):
    """each track's pitch now over its pitch at base (the mean over its voices)"""
    return {t: sum(a / b for a, b in zip(s[3][t], base[3][t])) / len(s[3][t]) for t in s[3] if t in base[3] and len(s[3][t]) == len(base[3][t])}


def pitch_ok(s, base, want, tol=0.004):
    r = ratios(s, base)
    return len(r) == 4 and all(abs(r[t] - want[t]) < tol for t in want), {t: round(x, 4) for t, x in r.items()}   # (all four sounding)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = run("smk37", "smk_tracks.txt")
    b0 = s[4000]
    print("== SMK-37: a note held on each track, the wheels across K3 turns")
    check("four tracks sounding, nothing bent, B picked", len(b0[3]) == 4 and b0[1] == [0, 0, 0, 0] and b0[0] == 1, b0)
    ok, r = pitch_ok(s[4300], b0, {0: 1, 1: UP2, 2: 1, 3: 1})
    check("the wheel up on B: B's voices up 2 semitones, A C D not moved", s[4300][1] == [0, 8191, 0, 0] and ok, (s[4300][1], r))
    ok, r = pitch_ok(s[4700], b0, {0: 1, 2: 1, 3: 1}) if s[4700][0] == 2 else (False, None)
    check("K3 to C mid-bend, the wheel moved on: still B's bend (less now), C untouched",
          s[4700][1][0] == s[4700][1][2] == s[4700][1][3] == 0 and 0 < s[4700][1][1] < 8191 and ok and 1 < ratios(s[4700], b0)[1] < UP2, (s[4700][:2], r))
    ok, r = pitch_ok(s[5000], b0, {0: 1, 1: 1, 2: 1, 3: 1})
    check("back at rest: every track exactly where it was", s[5000][1] == [0, 0, 0, 0] and ok, r)
    ok, r = pitch_ok(s[5300], b0, {0: 1, 1: 1, 2: UP2, 3: 1})
    check("the next bend: C (picked now), B not", s[5300][1] == [0, 0, 8191, 0] and ok, r)
    check("rest again: all straight", s[5600][1] == [0, 0, 0, 0] and pitch_ok(s[5600], b0, {0: 1, 1: 1, 2: 1, 3: 1})[0], s[5600][1])
    check("the mod wheel up on C: vibrato on C only", s[5900][2] == [0, 0, 127, 0], s[5900][2])
    check("K3 to B, the wheel left up: the vibrato moves to B, C has none", s[6200][0] == 1 and s[6200][2] == [0, 127, 0, 0], s[6200][:3])
    check("the mod wheel down: no vibrato anywhere", s[6500][2] == [0, 0, 0, 0], s[6500][2])
    ok, r = pitch_ok(s[6800], b0, {0: 1, 1: UP1, 2: 1, 3: 1})
    check("a MIDI bend (OMNI, half up) on B: B a semitone up, the others not", s[6800][1] == [0, 4096, 0, 0] and ok, r)
    check("K3 to C mid-bend, the MIDI bend moves on: still B, C untouched", s[7200][0] == 2 and s[7200][1] == [0, 4608, 0, 0], s[7200][:2])
    check("the MIDI bend centred: all straight", s[7500][1] == [0, 0, 0, 0] and pitch_ok(s[7500], b0, {0: 1, 1: 1, 2: 1, 3: 1})[0], s[7500][1])
    ok, r = pitch_ok(s[8000], b0, {0: 1, 1: 1, 2: UP2, 3: 1 / UP1})
    check("two sources: the wheel bends C, a MIDI bend (K3 on D) bends D down; A B untouched",
          s[8000][1] == [0, 0, 8191, -4096] and ok, (s[8000][1], r))
    ok, r = pitch_ok(s[8300], b0, {0: 1, 1: 1, 2: 1, 3: 1})
    check("both at rest: every track exactly where it was", s[8300][1] == [0, 0, 0, 0] and ok, r)

    for board in ("fm1", "smk37"):
        print(f"== {board}: MIDI channel 1 set: channels 2-4 bend their own tracks, channel 1 the picked one")
        s = run(board, "midi_channels.txt")
        b0 = s[3800]
        check(f"{board}: four tracks sounding from channels 1-4, nothing bent", len(b0[3]) == 4 and b0[1] == [0, 0, 0, 0], b0[:2])
        ok, r = pitch_ok(s[4100], b0, {0: 1, 1: 1, 2: UP1, 3: 1})
        check(f"{board}: a bend on channel 3: track C only (channel B-D bends were ignored)", s[4100][1] == [0, 0, 4096, 0] and ok, (s[4100][1], r))
        ok, r = pitch_ok(s[4500], b0, {0: 1 / UP1, 1: 1, 2: 1, 3: 1})
        check(f"{board}: channel 3 centred, a bend on channel 1: the picked track (A)", s[4500][1] == [-4096, 0, 0, 0] and ok, (s[4500][1], r))
        check(f"{board}: centred: all straight", s[4800][1] == [0, 0, 0, 0] and pitch_ok(s[4800], b0, {0: 1, 1: 1, 2: 1, 3: 1})[0], s[4800][1])
    print("wheels: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
