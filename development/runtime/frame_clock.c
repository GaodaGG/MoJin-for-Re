/* SPDX-License-Identifier: GPL-3.0-or-later
 * Title-specific optional battle pacing. No global PSP clock multiplier.
 * One statically selected frame-end call can wait on a host deadline through
 * the existing callback-aware kernel delay service. PSP scanout/vcount, system
 * time, RTC and audio stay stock. A separate opt-in
 * changes one title input call from blocking Read to existing Peek service.
 * The original bounded diagnostic remains reproducible. The persisted 120 FPS
 * choice uses scene/lifecycle gates instead of a test's vblank interval.
 * Normal launches clear inherited SR_* flags and set only their own INI choice.
 */
#include "recomp.h"
#include <SDL3/SDL.h>
#include "step_clock.h"

static int rate = -1;
static int game_mode;
static uint64_t deadline;
static uint32_t deadline_remainder, calls, late, errors;
static int active;
static int input_peek = -1;
static uint32_t input_calls, input_repeats, input_errors, input_stamp;
static int step_carry = -1;
static MojinStepClock step_clock;
static uint32_t step_uid, step_calls, step_applied, step_bypassed, step_errors;
static uint64_t step_original_ticks, step_corrected_ticks;

static void finish(void) {
    if (rate > 0)
        fprintf(stderr, "MOJIN_FRAME_CLOCK target=%d calls=%u late=%u errors=%u window=%s clocks=stock\n",
                rate, calls, late, errors, game_mode ? "battle" : "7400:9000");
    if (input_peek == 1)
        fprintf(stderr, "MOJIN_FRAME_INPUT mode=peek calls=%u repeated_samples=%u errors=%u window=%s sample_clock=stock\n",
                input_calls, input_repeats, input_errors, game_mode ? "battle" : "7400:9000");
    if (step_carry == 1)
        fprintf(stderr, "MOJIN_STEP_CARRY calls=%u applied=%u bypassed=%u errors=%u original_ticks=%llu corrected_ticks=%llu denominator=%u window=%s\n",
                step_calls, step_applied, step_bypassed, step_errors,
                (unsigned long long)step_original_ticks, (unsigned long long)step_corrected_ticks,
                MOJIN_STEP_DENOMINATOR, game_mode ? "battle" : "7400:9000");
}

static void configure(void) {
    if (rate < 0) {
        const char *choice = getenv("SR_MOJIN_GAME_FPS");
        game_mode = choice && strcmp(choice, "120") == 0;
        const char *value = getenv("SR_MOJIN_EXPERIMENTAL_UPDATE_RATE");
        rate = game_mode ? 120 : value && strcmp(value, "90") == 0 ? 90 :
               value && strcmp(value, "120") == 0 ? 120 : 0;
        if (game_mode) { input_peek = 1; step_carry = 1; }
        if (rate) atexit(finish);
    }
}

static int experiment_enabled(void) {
    configure();
    if (!rate) return 0;
    uint32_t v = sr_display_vcount();
    return (game_mode || (v >= 7400 && v < 9000)) && MEM_R32(0x08a3d294u) == 0x0885f978u &&
           MEM_R32(0x08a3d108u) == 3u && sched_wait_permitted() && sched_current_uid();
}

/* Called only by two opcode-checked static generation sites, before SLTI and
 * the original stores/fallback/clamp. Read-only observation hooks remain read-only.
 * Only v0 is changed; original generated instructions propagate the step normally.
 */
void mojin_experimental_step(CpuState *s, uint32_t pc) {
    configure();
    if (step_carry < 0) {
        const char *value = getenv("SR_MOJIN_EXPERIMENTAL_STEP_CARRY");
        step_carry = value && strcmp(value, "1") == 0;
    }
    if (!step_carry) return;
    if (!experiment_enabled() || input_peek != 1) {
        mojin_step_clock_reset(&step_clock);
        return;
    }
    ++step_calls;
    if ((pc != 0x0891c0c4u && pc != 0x0891c1c8u) || s->r[16] != 0x08a543ecu) {
        ++step_errors;
        mojin_step_clock_reset(&step_clock);
        return;
    }
    uint32_t uid = sched_current_uid();
    if (step_uid != uid) mojin_step_clock_reset(&step_clock);
    step_uid = uid;
    uint64_t previous = (uint64_t)s->r[18] | ((uint64_t)s->r[19] << 32);
    uint64_t now = (uint64_t)s->r[20] | ((uint64_t)s->r[21] << 32);
    int32_t speed = (int16_t)MEM_R16(0x08a543f6u);
    uint32_t override_bits = MEM_R32(0x08a544a0u);
    float override;
    memcpy(&override, &override_bits, sizeof(override));
    uint32_t corrected;
    int result = mojin_step_clock_update(&step_clock, previous, now, speed, s->r[2],
                                         override <= 0.0f, &corrected);
    if (result > 0) {
        ++step_applied;
        step_original_ticks += s->r[2];
        step_corrected_ticks += corrected;
        s->r[2] = corrected;
    } else if (result < 0) ++step_errors;
    else ++step_bypassed;
}

uint32_t mojin_experimental_step_fraction(void) {
    return step_clock.active ? step_clock.remainder : UINT32_MAX;
}

int mojin_experimental_input_poll(CpuState *s) {
    configure();
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
        mojin_step_clock_reset(&step_clock);
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
