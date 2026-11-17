/* SPDX-License-Identifier: GPL-3.0-or-later
 * BOUNDED DEVELOPMENT EXPERIMENT, not a supported high-FPS mode.
 * One statically selected frame-end call can wait on a host deadline through
 * the existing callback-aware kernel delay service. PSP scanout/vcount, system
 * time, RTC, audio and game time-step arithmetic stay stock. A separate opt-in
 * changes one title input call from blocking Read to existing Peek service.
 * The known Training input route is required by probe.py. Gate again on the
 * observed battle callback and the finished auxiliary loading thread, and only
 * in vblank [7400,9000). Normal launches clear SR_* and always take stock code.
 */
#include "recomp.h"
#include <SDL3/SDL.h>

static int rate = -1;
static uint64_t deadline;
static uint32_t deadline_remainder, calls, late, errors;
static int active;
static int input_peek = -1;
static uint32_t input_calls, input_repeats, input_errors, input_stamp;

static void finish(void) {
    if (rate > 0)
        fprintf(stderr, "MOJIN_FRAME_CLOCK target=%d calls=%u late=%u errors=%u window=7400:9000 clocks=stock\n",
                rate, calls, late, errors);
    if (input_peek == 1)
        fprintf(stderr, "MOJIN_FRAME_INPUT mode=peek calls=%u repeated_samples=%u errors=%u window=7400:9000 sample_clock=stock\n",
                input_calls, input_repeats, input_errors);
}

static int experiment_enabled(void) {
    if (rate < 0) {
        const char *value = getenv("SR_MOJIN_EXPERIMENTAL_UPDATE_RATE");
        rate = value && strcmp(value, "90") == 0 ? 90 :
               value && strcmp(value, "120") == 0 ? 120 : 0;
        if (rate) atexit(finish);
    }
    if (!rate) return 0;
    uint32_t v = sr_display_vcount();
    return v >= 7400 && v < 9000 && MEM_R32(0x08a3d294u) == 0x0885f978u &&
           MEM_R32(0x08a3d108u) == 3u && sched_wait_permitted() && sched_current_uid();
}

int mojin_experimental_input_poll(CpuState *s) {
    if (input_peek < 0) {
        const char *value = getenv("SR_MOJIN_EXPERIMENTAL_INPUT_PEEK");
        input_peek = value && strcmp(value, "1") == 0;
    }
    if (!input_peek || !experiment_enabled() || s->r[5] != 1u) return 0;
    uint32_t buf = s->r[4];
    sr_syscall(s, 0x3a622550u); /* existing sceCtrlPeekBufferPositive */
    if (s->r[2] == 1u) {
        /* The service has validated/written this sample. Keep its return code,
         * timestamp, buttons and both analog bytes; never synthesize input. */
        uint32_t stamp = MEM_R32(buf);
        if (input_calls && stamp == input_stamp) ++input_repeats;
        input_stamp = stamp;
    } else ++input_errors;
    ++input_calls;
    return 1;
}

int mojin_experimental_frame_wait(CpuState *s) {
    if (!experiment_enabled()) {
        uint32_t v = sr_display_vcount();
        if (active) fprintf(stderr, "MOJIN_FRAME_CLOCK leave v=%u calls=%u\n", v, calls);
        active = 0;
        deadline = 0;
        deadline_remainder = 0;
        return 0;
    }
    uint64_t now = SDL_GetTicksNS();
    if (!active) {
        fprintf(stderr, "MOJIN_FRAME_CLOCK enter target=%d v=%u uid=%x\n", rate, sr_display_vcount(), sched_current_uid());
        active = 1;
        deadline = now;
    }
    /* Rational deadline carry, without a catch-up burst after a slow frame. */
    deadline += 1000000000ull / (uint32_t)rate;
    deadline_remainder += 1000000000u % (uint32_t)rate;
    if (deadline_remainder >= (uint32_t)rate) { ++deadline; deadline_remainder -= (uint32_t)rate; }
    uint32_t usec;
    if (now >= deadline) {
        ++late;
        deadline = now;
        deadline_remainder = 0;
        usec = 1;
    } else usec = (uint32_t)((deadline - now + 999u) / 1000u);
    ++calls;
    uint32_t a0 = s->r[4];
    s->r[4] = usec;
    /* Use the normal callback-aware service, with its existing wait-context,
     * fiber scheduling and pending-callback semantics. Do not sleep the host
     * thread or synthesize a VBLANK. Preserve the caller's argument register. */
    sr_syscall(s, 0x68da9e36u); /* sceKernelDelayThreadCB */
    s->r[4] = a0;
    if ((int32_t)s->r[2] < 0) ++errors;
    return 1;
}
