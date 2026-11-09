/* SPDX-License-Identifier: GPL-3.0-only */
/* The wheels' routing (firmware/src/wheel_route.h): a bend belongs to the track picked when it leaves the rest, until
 * it is back at rest, whatever K3 does meanwhile; the mod wheel follows the picked track; two sources keep their own
 * owners; a channel's source its track; and the global scope (a setting to come) moves all four under the same rules. */
#include <stdio.h>
#include "../firmware/src/wheel_route.h"

static int fails;
static void check(int ok, const char *what) { printf("wheel_route: %-74s %s\n", what, ok ? "ok" : "FAIL"); fails += !ok; }
static int is(const volatile int32_t *a, int32_t x0, int32_t x1, int32_t x2, int32_t x3)
{
    return a[0] == x0 && a[1] == x1 && a[2] == x2 && a[3] == x3;
}

int main(void)
{
    volatile int32_t bend[4] = {0}, vib[4] = {0};
    wheel_route_t w = {-1, 0}, m = {-1, 0};

    wheel_bend(&w, 0, 1, 0, bend);
    check(is(bend, 0, 0, 0, 0) && w.owner == -1, "at rest, nothing bent: a rest reading changes nothing");
    wheel_bend(&w, 4000, 1, 0, bend);
    check(is(bend, 0, 4000, 0, 0) && w.owner == 1, "bend on B (picked): only B bends");
    wheel_bend(&w, 6000, 2, 0, bend);
    check(is(bend, 0, 6000, 0, 0), "K3 to C mid-bend, the wheel moves on: still B's bend, C untouched");
    wheel_bend(&w, -3000, 3, 0, bend);
    check(is(bend, 0, -3000, 0, 0), "... through centre to a down bend without resting: still B");
    wheel_bend(&w, 0, 3, 0, bend);
    check(is(bend, 0, 0, 0, 0) && w.owner == -1, "back at rest: B straight again, no owner (nothing left bent)");
    wheel_bend(&w, 2000, 3, 0, bend);
    check(is(bend, 0, 0, 0, 2000) && w.owner == 3, "the next bend: the track picked now (D)");
    wheel_bend(&w, 0, 0, 0, bend);

    wheel_bend(&w, 5000, 0, 0, bend);
    wheel_bend(&m, -4000, 2, 0, bend);
    check(is(bend, 5000, 0, -4000, 0), "two sources (the wheel on A, a MIDI bend on C): each its own track");
    wheel_bend(&m, 0, 1, 0, bend);
    check(is(bend, 5000, 0, 0, 0) && w.owner == 0, "the MIDI bend rests: C straight, the wheel's bend on A stays");
    wheel_bend(&w, 0, 1, 0, bend);
    check(is(bend, 0, 0, 0, 0), "the wheel rests: all straight");

    wheel_bend(&w, 3000, 1, 0, bend);
    wheel_bend(&m, 7000, 1, 0, bend);
    check(is(bend, 0, 7000, 0, 0), "both sources on one track: the last one moved wins (as one bend input)");
    wheel_bend(&m, 0, 1, 0, bend);
    wheel_bend(&w, 0, 1, 0, bend);
    check(is(bend, 0, 0, 0, 0) && w.owner == -1 && m.owner == -1, "... both at rest: straight, no owners");

    wheel_bend_to(2, 4096, 0, bend);
    check(is(bend, 0, 0, 4096, 0), "a channel's bend (MIDI channel C): its track, whatever is picked");
    wheel_bend_to(2, 0, 0, bend);

    wheel_vib(90, 0, 0, vib);
    check(is(vib, 90, 0, 0, 0), "mod wheel up on A: vibrato on A only");
    wheel_vib(90, 2, 0, vib);
    check(is(vib, 0, 0, 90, 0), "K3 to C (the wheel stays up): A back to none, C takes it as it stands");
    wheel_vib(40, 2, 0, vib);
    check(is(vib, 0, 0, 40, 0), "the wheel moves: C follows");
    wheel_vib(0, 2, 0, vib);
    check(is(vib, 0, 0, 0, 0), "the wheel down: no vibrato anywhere");

    wheel_bend(&w, 8191, 9, 0, bend);
    check(is(bend, 0, 8191, 0, 0), "a track number past D wraps (9 -> B): no write past the four");
    wheel_bend(&w, 0, 9, 0, bend);
    check(wheel_mask(5, 0) == 2u && wheel_mask(0, 1) == 15u, "wheel_mask: one track (wrapped), or all four (global)");

    /* the global scope, a setting to come: the same rules on all four */
    wheel_bend(&w, 4000, 1, 1, bend);
    check(is(bend, 4000, 4000, 4000, 4000), "global: a bend moves all four tracks");
    wheel_bend(&w, 0, 3, 1, bend);
    check(is(bend, 0, 0, 0, 0) && w.owner == -1, "global: back at rest, all straight");
    wheel_vib(70, 2, 1, vib);
    check(is(vib, 70, 70, 70, 70), "global: the mod wheel on all four");
    wheel_vib(70, 2, 0, vib);
    check(is(vib, 0, 0, 70, 0), "global off again (the setting changed): only the picked track keeps it");
    wheel_bend(&w, 3000, 1, 1, bend);
    wheel_bend(&w, 3500, 1, 0, bend);
    check(is(bend, 3500, 3500, 3500, 3500), "global switched off mid-bend: the bend keeps the tracks it began on");
    wheel_bend(&w, 0, 1, 0, bend);
    check(is(bend, 0, 0, 0, 0) && w.owner == -1, "... and its rest straightens all of them (none stranded)");
    wheel_bend(&w, 2000, 2, 0, bend);
    wheel_bend(&w, 2500, 2, 1, bend);
    check(is(bend, 0, 0, 2500, 0), "global switched on mid-bend: still only the track it began on, until it rests");
    wheel_bend(&w, 0, 2, 1, bend);
    wheel_bend(&w, 1000, 2, 1, bend);
    check(is(bend, 1000, 1000, 1000, 1000), "... the next bend takes the new scope (all four)");
    wheel_bend(&w, 0, 2, 1, bend);
    printf(fails ? "wheel_route: FAILED\n" : "wheel_route: all ok\n");
    return fails != 0;
}
