#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The triangle (WAVE TRI, both oscillators; obv_dsp.h osc_naive + osc_corner, polyBLAMP at its corners). One
oscillator, the filter wide open, VINTAGE 0, measured in the WAV: odd harmonics only, falling as 1/n^2 (the 3rd
-19.1 dB, the 5th -28 dB); a high note's aliases (the harmonics past Nyquist folded back) far under a naive
triangle's (C7: under 12 kHz -68 dB, a naive one -48); as loud as the saw; synced (OSC 2 TRI on OSC 1) it stays bounded and still changes the
tone. FM-1 host build, MIDI CC. Exit 1 on a failure."""
import math, os, re, subprocess, sys, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "host" / "tri"
BIN = OUT / "host"
SR = 44100
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("  ok    " if ok else "  FAIL  ") + name + ("" if ok else f"  ({detail})"))
    fails += not ok


def cc_for(value, maximum):
    return next(v for v in range(128) if (v * maximum + 63) // 127 == value)


def render(name, note, o1, o2=0, sync=0, semi=0):
    cc = [(57, 0), (74, 127), (71, 0), (32, 64), (34, 0), (20, cc_for(o1, 4)), (24, cc_for(o2, 4)), (22, 0 if sync else 90),
          (26, 90 if o2 else 0), (27, cc_for(24 + semi, 48)), (28, 127 if sync else 0), (31, 64)]
    lines = ["3000 midi 0xC0 98 0"] + [f"3050 midi 0xB0 {c} {v}" for c, v in cc]
    lines += [f"3500 midi 0x90 {note} 100", "4000 wheels", "5600 midi 0x80 {} 0".format(note), "6000 end"]
    p = OUT / f"{name}.txt"
    p.write_text("\n".join(lines) + "\n")
    out = subprocess.run([str(BIN), str(OUT / name), str(p)], capture_output=True, text=True).stdout
    m = re.search(r"voices=\d+:\d+:(\d+):(\d+)", out)
    w = wave.open(str(OUT / f"{name}.wav"))
    raw = memoryview(w.readframes(w.getnframes())).cast("h")
    x = [raw[2 * i] for i in range(int(4.0 * SR), int(5.0 * SR))]
    return x, int(m[1]) * SR / 2 ** 32, int(m[2]) * SR / 2 ** 32


def amp(x, f):                                    # Hann-windowed Goertzel: the level at f
    n = len(x)
    w = 2 * math.cos(2 * math.pi * f / SR)
    s1 = s2 = 0.0
    for i, v in enumerate(x):
        s = v * (0.5 - 0.5 * math.cos(2 * math.pi * i / n)) + w * s1 - s2
        s2, s1 = s1, s
    return math.sqrt(max(s1 * s1 + s2 * s2 - w * s1 * s2, 0.0)) / n


def db(a, ref):
    return 20 * math.log10(a / ref + 1e-12)


def rms(x):
    return math.sqrt(sum(v * v for v in x) / len(x))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([os.environ.get("CC", "cc"), "-O2", "-w", "-DOBV_HOST", '-DAPP_VER="test"', "-I" + str(ROOT / "firmware/src"),
                    "-I" + str(ROOT / "firmware/gen"), "-o", str(BIN), str(ROOT / "firmware/src/obervave.c")], check=True)
    x, f, _ = render("tri-c4", 60, 4)
    h = [amp(x, k * f) for k in range(1, 7)]
    check(f"even harmonics absent (2nd {db(h[1], h[0]):.0f} dB, 4th {db(h[3], h[0]):.0f} dB; under -40)", db(h[1], h[0]) < -40 and db(h[3], h[0]) < -40)
    check(f"3rd harmonic {db(h[2], h[0]):.1f} dB (1/9: -19.1)", abs(db(h[2], h[0]) + 19.1) < 1.0)
    check(f"5th harmonic {db(h[4], h[0]):.1f} dB (1/25: -28.0)", abs(db(h[4], h[0]) + 28.0) < 1.5)
    s, _, _ = render("saw-c4", 60, 1)
    check(f"as loud as the saw ({20 * math.log10(rms(x) / rms(s)):+.1f} dB)", abs(20 * math.log10(rms(x) / rms(s))) < 1.0)
    x, f, _ = render("tri-c7", 96, 4)
    a1 = amp(x, f)
    fold = lambda fk: min(fk % SR, SR - fk % SR)  # where a harmonic past Nyquist lands
    al = [fold(k * f) for k in range(11, 42, 2) if k * f > SR / 2]
    al = [a for a in al if min(abs(a - j * f) for j in range(1, 11)) > 60]   # (not on a real harmonic)
    lo = max(db(amp(x, a), a1) for a in al if a < 12000)
    hi = max(db(amp(x, a), a1) for a in al)
    check(f"C7: the aliases under 12 kHz at most {lo:.0f} dB (a naive triangle: -48; under -65)", lo < -65, lo)
    check(f"... and up to Nyquist {hi:.0f} dB (naive: -45; under -55: polyBLAMP's two points are weakest there)", hi < -55, hi)
    x, f1, f2 = render("tri-sync", 48, 0, o2=4, sync=1, semi=7)
    y, _, _ = render("tri-nosync", 48, 0, o2=4, sync=0, semi=7)
    pk = max(abs(v) for v in x)
    check(f"synced: bounded (peak {db(pk, 32768):.1f} dBFS) and periodic at OSC 1 ({f1:.0f} Hz) not OSC 2 ({f2:.0f} Hz)",
          pk < 32000 and amp(x, f1) > 10 * amp(x, f2) and amp(y, f2) > 10 * amp(y, f1), (pk, amp(x, f1), amp(x, f2)))
    print("triangle: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
