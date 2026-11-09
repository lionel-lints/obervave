/* SPDX-License-Identifier: GPL-3.0-only */
/* The wheels go to a track, not to the whole song: pitch bend and the mod wheel's vibrato are per track (the engine's
 * ctl_bend_p / ctl_vib_p), as the keys play, the knobs edit and REC records the track K3 has picked.
 *
 *  - wheel_mask: the one place that says which tracks a wheel moves. Per track now; `global` (all four at once) is
 *    there for a setting to come, and the rules below hold for it as they are.
 *  - the pitch wheel springs back: the track picked when it leaves the rest owns the bend until it is back at rest, so a
 *    K3 turn in the middle of a bend never leaves a track bent nor makes one jump; the next bend goes to the track
 *    picked then. The tracks it moves are fixed as it begins too: the scope changed mid-bend strands none. A MIDI bend in on OMNI is the same, with its own owner (wheel_route_t each).
 *  - the mod wheel stays where it is put: it follows the picked track; the one left goes back to no vibrato, the new
 *    one takes the wheel as it stands.
 * Pure: no engine, no hardware (tests/wheel_route_test.c). */
#pragma once
#include <stdint.h>

#ifndef WR_NTRK
#define WR_NTRK 4u
#endif

typedef struct { int8_t owner; uint8_t mask; } wheel_route_t;   /* the track bending (-1: the wheel is at rest) and the
                                                 * tracks it moves, fixed when the bend began; init {-1, 0} */

static uint32_t wheel_mask(uint32_t t, int global)
{
    return global ? (1u << WR_NTRK) - 1u : 1u << (t % WR_NTRK);
}

/* a new bend b (-8192..8191, 0 = rest) from a springing source; sel: the track picked now */
static void wheel_bend(wheel_route_t *w, int32_t b, uint32_t sel, int global, volatile int32_t *bend_p)
{
    uint32_t m, t;
    if (w->owner < 0) {
        if (!b) return;                         /* (at rest and nothing bent: nothing to do) */
        w->owner = (int8_t)(sel % WR_NTRK);
        w->mask = (uint8_t)wheel_mask(sel, global);   /* (the scope as the bend began: a scope change mid-bend strands none) */
    }
    m = w->mask;
    for (t = 0; t < WR_NTRK; t++)
        if (m >> t & 1u) bend_p[t] = b;
    if (!b) w->owner = -1;                      /* back at rest: the next bend goes to the track picked then */
}

/* a bend from a source tied to one track (MIDI channel B-D): no owner, that track (or all, global) */
static void wheel_bend_to(uint32_t t, int32_t b, int global, volatile int32_t *bend_p)
{
    uint32_t m = wheel_mask(t, global), k;
    for (k = 0; k < WR_NTRK; k++)
        if (m >> k & 1u) bend_p[k] = b;
}

/* the mod wheel as it stands (0..127), every pass: on the picked track(s), none elsewhere */
static void wheel_vib(int32_t v, uint32_t sel, int global, volatile int32_t *vib_p)
{
    uint32_t m = wheel_mask(sel, global), t;
    for (t = 0; t < WR_NTRK; t++) {
        int32_t want = m >> t & 1u ? v : 0;
        if (vib_p[t] != want) vib_p[t] = want;
    }
}
