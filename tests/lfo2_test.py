#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""LFO 2 does what each destination says. A note held 3 s on INIT (VINTAGE 0: no drift), LFO 2 at full on one
destination, measured against the same note with LFO 2 off: pitch moves both oscillators, OSC 2 only the second, PWM /
cutoff / resonance / morph / cross-mod / noise change the tone over time, amp the level, pan the balance, L1 RATE and
L1 DEPTH LFO 1's vibrato. Two slots on one destination add up; DELAY holds it back at the note's start. FM-1 host
build, MIDI CC (LFO 2: CC 82-88). Exit 1 on a failure."""
import math, os, re, subprocess, sys, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "host" / "lfo2"
CC = {"SHAPE": 82, "RATE": 83, "DELAY": 84, "DEST1": 85, "AMT1": 86, "DEST2": 87, "AMT2": 88,
      "VINTAGE": 57, "FENV": 32, "O2FINE": 31, "O1WAVE": 20, "O2WAVE": 24, "FTYPE": 34, "RESO": 71, "CUTOFF": 74, "LFOPITCH": 48, "LFORATE": 45}
DEST = ["OFF", "PITCH", "OSC2", "PWM", "CUTOFF", "RESO", "AMP", "PAN", "MORPH", "XMOD", "NOISE", "L1RATE", "L1DEPTH"]
BIN = OUT / "host"
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("  ok    " if ok else "  FAIL  ") + name + ("" if ok else f"  ({detail})"))
    fails += not ok


def cc_for(value, maximum):                       # the CC that lands on value (obervave.c: v * max + 63) / 127)
    return next(v for v in range(128) if (v * maximum + 63) // 127 == value)


def render(name, setup, dest1="OFF", dest2="OFF", amt1=127, amt2=64, delay=0, note_ms=4500):
    lines = ["3000 midi 0xC0 70 0", f"3050 midi 0xB0 {CC['VINTAGE']} 0", f"3050 midi 0xB0 {CC['RATE']} 95",
             f"3050 midi 0xB0 {CC['FENV']} 64"]   # (no drift, no filter envelope: the baseline holds still)
    lines += [f"3050 midi 0xB0 {CC[k]} {v}" for k, v in setup]
    lines += [f"3060 midi 0xB0 {CC['DEST1']} {cc_for(DEST.index(dest1), 12)}", f"3060 midi 0xB0 {CC['AMT1']} {amt1}",
              f"3060 midi 0xB0 {CC['DEST2']} {cc_for(DEST.index(dest2), 12)}", f"3060 midi 0xB0 {CC['AMT2']} {amt2}",
              f"3060 midi 0xB0 {CC['DELAY']} {delay}", "3500 midi 0x90 48 100"]
    lines += [f"{t} wheels" for t in range(3540, 3500 + note_ms, 20)]
    lines += [f"{3500 + note_ms} midi 0x80 48 0", f"{4500 + note_ms} end"]
    p = OUT / f"{name}.txt"
    p.write_text("\n".join(lines) + "\n")
    out = subprocess.run([str(BIN), str(OUT / name), str(p)], capture_output=True, text=True).stdout
    inc = [tuple(int(x) for x in m[1].split(":")[2:]) for m in re.finditer(r"voices=(\S+)", out)]   # (OSC 1, OSC 2, PW, ...)
    w = wave.open(str(OUT / f"{name}.wav"))
    sr = w.getframerate()
    raw = memoryview(w.readframes(w.getnframes())).cast("h")
    a, b = int(5.0 * sr), int((3.5 + note_ms / 1000 - 0.05) * sr)   # (from 1.5 s in: the envelopes have settled)
    return inc, [raw[2 * i] for i in range(a, b)], [raw[2 * i + 1] for i in range(a, b)], sr


def sd(x):
    m = sum(x) / len(x)
    return (sum((v - m) ** 2 for v in x) / len(x)) ** 0.5


def frames(x, n):
    return [x[i:i + n] for i in range(0, len(x) - n, n)]


def rms_db(x):
    return 10 * math.log10(sum(v * v for v in x) / len(x) + 1)


def brightness(x):                                # high frequencies over all (the 2nd difference's RMS / the signal's): tone colour
    d = sum((x[i] - 2 * x[i - 1] + x[i - 2]) ** 2 for i in range(2, len(x)))
    return (d / (sum(v * v for v in x) + 1)) ** 0.5


def cents(inc, k):
    base = inc[0][k]
    return [1200 * math.log2(v[k] / base) for v in inc]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([os.environ.get("CC", "cc"), "-O2", "-w", "-DOBV_HOST", '-DAPP_VER="test"', "-I" + str(ROOT / "firmware/src"),
                    "-I" + str(ROOT / "firmware/gen"), "-o", str(BIN), str(ROOT / "firmware/src/obervave.c")], check=True)
    n = 1323                                       # 30 ms frames
    # pitch: both oscillators / OSC 2 only
    off, _, _, _ = render("off", [])
    on, _, _, _ = render("pitch", [], "PITCH")
    o2, _, _, _ = render("osc2", [], "OSC2")
    check("off: both oscillators hold their pitch", sd(cents(off, 0)) == 0 and sd(cents(off, 1)) == 0, (sd(cents(off, 0)), sd(cents(off, 1))))
    check("PITCH: both oscillators swing (several semitones)", sd(cents(on, 0)) > 200 and sd(cents(on, 1)) > 200, (sd(cents(on, 0)), sd(cents(on, 1))))
    check("OSC2: OSC 2 swings, OSC 1 stays put", sd(cents(o2, 0)) == 0 and sd(cents(o2, 1)) > 200, (sd(cents(o2, 0)), sd(cents(o2, 1))))
    both, _, _, _ = render("both", [], "PITCH", "PITCH", amt2=127)
    check("two slots on one destination add up (twice the swing)", 1.7 < sd(cents(both, 0)) / sd(cents(on, 0)) < 2.3, sd(cents(both, 0)) / sd(cents(on, 0)))
    dl, _, _, _ = render("delay", [], "PITCH", delay=70)
    early, late = cents(dl, 0)[:8], cents(dl, 0)[-40:]                 # (the first 160 ms, the last 800 ms)
    check("DELAY: nothing at the note's start, the swing later", sd(early) < 1 and sd(late) > 100, (sd(early), sd(late)))
    # the rest at the source: each voice's pulse width, cross-mod, noise, morph, pan gains, amp and filter feedback
    # (host "wheels": OSC 1, OSC 2, PW 1, x-mod, noise, morph, gain L, gain R, amp, reso k), LFO 2 off as the baseline
    def field(inc_full, k): return [v[k] for v in inc_full]
    for dest, setup, k, label in (
            ("PWM", [("O1WAVE", 85)], 2, "the pulse width swings"),
            ("XMOD", [], 3, "the cross-mod amount swings"),
            ("NOISE", [], 4, "the noise level swings"),
            ("RESO", [("RESO", 64)], 9, "the filter's resonance swings"),
            ("AMP", [], 8, "the level swings (a tremolo)"),
            ("PAN", [], 6, "the left gain swings (the pan)"),
            ("MORPH", [("FTYPE", 127)], 5, "the SEM morph swings")):
        f0, _, _, _ = render(f"{dest}-off", setup + [("O2FINE", 64)])
        f1, _, _, _ = render(dest.lower(), setup + [("O2FINE", 64)], dest)
        s0, s1 = sd(field(f0, k)[50:]), sd(field(f1, k)[50:])
        check(f"{dest}: {label} (LFO 2 off: still)", s0 == 0 and s1 > 0, (s0, s1))
    _, l0, _, _ = render("cutoff-off", [("CUTOFF", 60), ("O2FINE", 64)])      # the cutoff by ear: the tone over 30 ms frames
    _, l1, _, _ = render("cutoff", [("CUTOFF", 60), ("O2FINE", 64)], "CUTOFF")
    s0, s1 = sd([brightness(f) for f in frames(l0, n)]), sd([brightness(f) for f in frames(l1, n)])
    check(f"CUTOFF: the cutoff moves the tone (x{s1 / (s0 + 1e-9):.0f} the movement with LFO 2 off)", s1 > 5 * s0, (s0, s1))
    # LFO 1 rate / depth: LFO 1 on the pitch, a slow vibrato; LFO 2 on its rate or its depth
    vib = [("LFOPITCH", 60), ("LFORATE", 40)]
    v0, _, _, _ = render("l1-off", vib)
    vr, _, _, _ = render("l1rate", vib, "L1RATE")
    vd, _, _, _ = render("l1depth", vib, "L1DEPTH")
    diff = lambda a, b: sum(abs(x - y) for x, y in zip(cents(a, 0), cents(b, 0))) / len(a)
    check("L1 RATE: LFO 1's vibrato runs at another speed", diff(v0, vr) > 10, diff(v0, vr))
    check("L1 DEPTH: LFO 1's vibrato gets deeper and shallower", diff(v0, vd) > 5 and abs(sd(cents(vd, 0)) - sd(cents(v0, 0))) > 1,
          (diff(v0, vd), sd(cents(v0, 0)), sd(cents(vd, 0))))
    print("LFO 2: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
