/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 M. Geisler (genkigenki/makkuro); ported to the four tracks of OberVave 3 */
/* Stuck notes: random keys on the four tracks' sounds (as play_note sends them), the arps' modes, sustain / each
 * sound's HOLD, voice modes and program changes; after every audio block each gated voice must be held by a key
 * or by its sound's arp, and after every key up, the pedal and HOLD let go, after 2 s nothing may still hold a note.
 *   cc -O1 -DOBV_HOST [-DBOARD_SMK37=1] -Ifirmware/src -Ifirmware/gen -o build/host/arp_fuzz tests/arp_fuzz.c
 *   arp_fuzz [runs] [one run to trace] */
#define main obv_host_main
#include "../firmware/src/obervave.c"
#undef main

static uint32_t fz = 12345u;
static uint32_t fz_rnd(uint32_t n) { fz ^= fz << 13; fz ^= fz >> 17; fz ^= fz << 5; return fz % n; }
static char lg[600][96]; static uint32_t lgn, want = 0xFFFFFFFFu, bad_now;
#define LOG(...) do { if (lgn < 600u) snprintf(lg[lgn++], 96, __VA_ARGS__); } while (0)
static int32_t buf[2u * HALF_FRAMES];
static void check(void)                         /* every gated voice: a key (or the pedal / HOLD) or its arp holds it */
{
    uint32_t w, q, ok;
    if (bad_now) return;
    for (w = 0; w < NV; w++) {
        uint32_t pp = vc[w].part % NPART;
        if (!vc[w].gate) continue;
        ok = pt[pp].p->v[P_ARP_MODE] != A_OFF ? arp[pp].sounding && arp[pp].note == vc[w].note : 0u;
        for (q = 0; q < nheld[pp] && !ok; q++) ok = held[pp][q].note == vc[w].note;
        if (!ok) { LOG("!! card %u part %u note %u gated, nothing holds it (arp mode %u, sounding %u note %u)", w, pp, vc[w].note,
                       pt[pp].p->v[P_ARP_MODE], arp[pp].sounding, arp[pp].note); bad_now = 1; return; }
    }
}
static void blocks(uint32_t n) { while (n--) { uint32_t i; for (i = 0; i < 2u * HALF_FRAMES; i++) buf[i] = 0; app_audio(buf, HALF_FRAMES); check(); } }

int main(int argc, char **argv)
{
    uint32_t run, runs = argc > 1 ? (uint32_t)atoi(argv[1]) : 2000u, bad = 0, t;
    if (argc > 2) want = (uint32_t)atoi(argv[2]);
    engine_init();
    cc_map_init();
    set.tempo = 120; ctl_tempo = 120;
    load_pattern(0);
    for (run = 0; run < runs; run++) {
        uint8_t down[128] = {0}, part[128] = {0};
        uint32_t step, n, v, p;
        if (want != 0xFFFFFFFFu && run != want) continue;
        fz = 0x9E3779B9u * (run + 1u); lgn = 0; bad_now = 0;
        for (t = 0; t < NTRK; t++) trk_load(t, fz_rnd(NPROG));
        ctl_sustain = ctl_hold = 0;
        ctl_panic = 1; blocks(4);
        for (step = 0; step < 400u; step++) {
            uint32_t r = fz_rnd(100);
            n = 60u + fz_rnd(8);
            p = fz_rnd(NTRK);
            if (r < 40) {                       /* a key, on the track picked when it went down */
                if (!down[n]) { down[n] = 1; part[n] = (uint8_t)p; note_event_p(p, 1, n, 1u + fz_rnd(127)); LOG("on %u p%u", n, p); }
                else { down[n] = 0; note_event_p(part[n], 0, n, 0); LOG("off %u p%u", n, part[n]); }
            } else if (r < 47) { ctl_sustain = !ctl_sustain; LOG("sus %u", ctl_sustain); }
            else if (r < 53) { ctl_hold ^= 1u << p; LOG("hold %u -> %x", p, ctl_hold); }
            else if (r < 63) { live_p[p].v[P_ARP_MODE] = (uint8_t)fz_rnd(PDEF[P_ARP_MODE].max + 1u); LOG("%u arp %u", p, live_p[p].v[P_ARP_MODE]); }
            else if (r < 70) { live_p[p].v[P_MODE] = (uint8_t)fz_rnd(PDEF[P_MODE].max + 1u); LOG("%u mode %u", p, live_p[p].v[P_MODE]); }
            else if (r < 72) { live_p[p].v[P_UNI_N] = (uint8_t)fz_rnd(PDEF[P_UNI_N].max + 1u); LOG("%u voices %u", p, live_p[p].v[P_UNI_N]); }
            else if (r < 75) live_p[p].v[P_ARP_GATE] = (uint8_t)fz_rnd(128);
            else if (r < 80) { trk_load(p, fz_rnd(NPROG)); LOG("%u program", p); }
            blocks(1u + fz_rnd(6));
        }
        for (n = 0; n < 128u; n++) if (down[n]) note_event_p(part[n], 0, n, 0);
        LOG("-- all keys up"); blocks(2); ctl_sustain = 0; ctl_hold = 0; LOG("-- pedal, HOLD up");
        blocks(400);
        for (v = 0; v < NV; v++)
            if (vc[v].gate) break;
        for (t = 0; t < NPART && !nheld[t] && !arp[t].sounding; t++) ;
        if (bad_now || v < NV || t < NPART) {
            if (bad++ < 5)
                printf("run %u: %s: voice %d gated (note %u part %u), held %u/%u/%u/%u, arp sounding %u/%u/%u/%u\n", run,
                       bad_now ? "a voice nothing held" : "stuck at the end", v < NV ? (int)v : -1, v < NV ? vc[v].note : 0u,
                       v < NV ? vc[v].part : 0u, nheld[0], nheld[1], nheld[2], nheld[3], arp[0].sounding, arp[1].sounding,
                       arp[2].sounding, arp[3].sounding);
        }
    }
    if (want != 0xFFFFFFFFu) { uint32_t i; for (i = 0; i < lgn; i++) printf("  %s\n", lg[i]); }
    printf("%u of %u runs left a note held\n", bad, runs);
    return bad != 0;
}
