#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The filter TYPE steps low-pass to high-pass: LP 24, LP 12, BP 12, NOTCH, HP 12, then SEM (obv_params.h FT_ORDER;
the stored values stay, so a saved sound keeps its filter). The FILTER page's knob 4 turned up one detent at a time
from the far left, and down again; CC 34 swept 0..127; the stored value read back after each (host "patches":
LIVE). FM-1 host build. Exit 1 on a failure."""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "host" / "ftype"
WANT = ["LP 24", "LP 12", "BP 12", "NOTCH", "HP 12", "SEM"]
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("  ok    " if ok else "  FAIL  ") + name + ("" if ok else f"  ({detail})"))
    fails += not ok


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = (ROOT / "firmware/src/obv_params.h").read_text()
    e = src[src.index("P_O1_WAVE"):]
    pidx = re.findall(r"P_[A-Z0-9_]+", e[:e.index("}")]).index("P_FTYPE")
    fe = src[src.index("enum { F_LP12"):]
    fnum = re.findall(r"F_[A-Z0-9]+", fe[:fe.index("}")])
    names = dict(zip(fnum, re.findall(r'"([^"]+)"', src[src.index("FTYPE_NAME[NFTYPE]"):].split("}")[0])))
    b = OUT / "host"
    subprocess.run([os.environ.get("CC", "cc"), "-O2", "-w", "-DOBV_HOST", '-DAPP_VER="test"', "-I" + str(ROOT / "firmware/src"),
                    "-I" + str(ROOT / "firmware/gen"), "-o", str(b), str(ROOT / "firmware/src/obervave.c")], check=True)

    def run(name, lines):
        p = OUT / f"{name}.txt"
        p.write_text("\n".join(lines) + "\n")
        out = subprocess.run([str(b), str(OUT / name), str(p)], capture_output=True, text=True).stdout
        return [names[fnum[int(m[1][2 * pidx:2 * pidx + 2], 16)]] for m in re.finditer(r"LIVE 0 ([0-9a-f]+)", out)]

    lines = ["3000 midi 0xC0 98 0"] + [f"{3100 + 150 * i} btn 6" for i in range(5)]   # EDIT x5: the FILTER page
    t = 4000
    lines += [f"{t} enc 5 -10", f"{t + 100} patches"]
    for i in range(7):
        t += 200; lines += [f"{t} enc 5 1", f"{t + 100} patches"]
    for i in range(7):
        t += 200; lines += [f"{t} enc 5 -1", f"{t + 100} patches"]
    seen = run("knob", lines + [f"{t + 500} end"])
    up, down = seen[:8], seen[8:]               # (the far left, 7 detents up; 7 down)
    check(f"the knob from the left, up: {', '.join(up)}", up == WANT + ["SEM", "SEM"], up)
    check(f"... and back down: {', '.join(down)}", down == ["HP 12", "NOTCH", "BP 12", "LP 12", "LP 24", "LP 24", "LP 24"], down)
    lines = ["3000 midi 0xC0 98 0"]
    for i, v in enumerate(range(0, 128, 4)):
        lines += [f"{3100 + 50 * i} midi 0xB0 34 {v}", f"{3120 + 50 * i} patches"]
    seen = run("cc", lines + ["6000 end"])
    order = [n for i, n in enumerate(seen) if i == 0 or n != seen[i - 1]]
    check(f"CC 34 swept up: {', '.join(order)}", order == WANT, order)
    seen = run("factory", ["3000 midi 0xC0 0 0", "3100 patches", "3200 midi 0xC0 70 0", "3300 patches", "3400 end"])
    check(f"saved sounds keep theirs (01 DARK ARP {seen[0]}, 71 BREATH PAD {seen[1]})", seen == ["LP 24", "LP 12"], seen)
    print("filter order: " + ("all passed" if not fails else f"{fails} FAILED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
