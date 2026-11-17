/* SPDX-License-Identifier: GPL-3.0-or-later
 * Opt-in, bounded observations of the pinned title's main frame loop.
 * No guest writes, scheduling, clock refresh or I/O in the sampled loop.
 * Guest fibers execute these sites on the scheduler's one owning thread.
 * Timing includes diagnostic overhead; these are not display FPS samples.
 */
#include "recomp.h"
#include <SDL3/SDL.h>

typedef struct {
    uint64_t host_ns, guest_us;
    uint32_t vcount, pc, callback, state, engine_frame, uid;
    uint32_t scene_callback, update_count, step_i, step_f_bits, step_frame_bits;
    uint32_t time_s_bits, tick_remainder, whole_ticks;
    uint32_t battle_object, battle_valid, battle_state, battle_ticks, battle_calls, battle_handler;
    uint32_t input_buttons, input_pressed, stick_direction, stick_pressed, input_history_index;
    uint64_t engine_time_us;
    int32_t speed_factor;
    uint32_t step_override_bits;
} MojinLoopRow;
static MojinLoopRow rows[131072];
static unsigned count, dropped;
static int enabled = -1;
static FILE *output;

static void finish(void) {
    if (!output) return;
    fputs("seq,host_ns,guest_us,vcount,pc,callback,state,engine_frame,uid,scene_callback,update_count,step_i,step_f_bits,step_frame_bits,time_s_bits,tick_remainder,whole_ticks,battle_object,battle_valid,battle_state,battle_ticks,battle_calls,battle_handler,input_buttons,input_pressed,stick_direction,stick_pressed,input_history_index,engine_time_us,speed_factor,step_override_bits\n", output);
    for (unsigned i = 0; i < count; ++i) {
        const MojinLoopRow *r = &rows[i];
        fprintf(output, "%u,%llu,%llu,%u,%08x,%08x,%u,%u,%x,%08x,%u,%u,%08x,%08x,%08x,%u,%u", i,
                (unsigned long long)r->host_ns, (unsigned long long)r->guest_us,
                r->vcount, r->pc, r->callback, r->state, r->engine_frame, r->uid,
                r->scene_callback, r->update_count, r->step_i, r->step_f_bits,
                r->step_frame_bits, r->time_s_bits, r->tick_remainder, r->whole_ticks);
        fprintf(output, ",%08x,%u,%u,%u,%u,%08x", r->battle_object, r->battle_valid,
                r->battle_state, r->battle_ticks, r->battle_calls, r->battle_handler);
        fprintf(output, ",%u,%u,%u,%u,%u", r->input_buttons, r->input_pressed,
                r->stick_direction, r->stick_pressed, r->input_history_index);
        fprintf(output, ",%llu,%d,%08x\n", (unsigned long long)r->engine_time_us,
                r->speed_factor, r->step_override_bits);
    }
    int failed = ferror(output);
    failed |= fclose(output) != 0;
    output = NULL;
    fprintf(stderr, "MOJIN_LOOP_TRACE rows=%u dropped=%u write_error=%d\n", count, dropped, failed);
}

void mojin_loop_trace(const CpuState *s, uint32_t pc) {
    (void)s;
    if (enabled < 0) {
        const char *path = getenv("SR_MOJIN_LOOP_TRACE");
        enabled = 0;
        if (path && path[0]) {
            output = fopen(path, "wb");
            if (output) {
                if (atexit(finish) == 0) enabled = 1;
                else { fclose(output); output = NULL; }
            }
            if (!enabled) fprintf(stderr, "MOJIN_LOOP_TRACE: cannot initialize diagnostic output\n");
        }
    }
    if (!enabled) return;
    if (count == sizeof(rows) / sizeof(rows[0])) { ++dropped; return; }
    MojinLoopRow *r = &rows[count++];
    r->host_ns = SDL_GetTicksNS();
    r->guest_us = sched_vtime_us(); /* snapshot getter; deliberately no refresh */
    r->vcount = sr_display_vcount();
    r->pc = pc;
    r->callback = MEM_R32(0x08a3d104u);
    r->state = MEM_R32(0x08a3d108u);
    r->engine_frame = MEM_R32(0x08a65f88u); /* 0x08a64680 + 0x1908 */
    r->uid = sched_current_uid();
    r->scene_callback = MEM_R32(0x08a3d294u);
    /* Exact fields consumed/written by f_08907c44, base 0x08a543ec.
     * Keep raw float bits in the evidence; descriptive names are provisional
     * until each consumer's gameplay semantics has been checked. */
    r->update_count = MEM_R32(0x08a54488u); /* +0x9c */
    r->step_i = MEM_R32(0x08a54494u); /* +0xa8 */
    r->step_f_bits = MEM_R32(0x08a54498u); /* +0xac */
    r->step_frame_bits = MEM_R32(0x08a5449cu); /* +0xb0 */
    r->time_s_bits = MEM_R32(0x08a54490u); /* +0xa4 */
    r->tick_remainder = MEM_R16(0x08a544a4u); /* +0xb8 */
    r->whole_ticks = MEM_R8(0x08a544a6u); /* +0xba */
    /* f_089098cc: held buttons, newly pressed mask, stick direction/edge,
     * and the 64-slot history cursor. Diagnostic names follow inspected stores. */
    r->input_buttons = MEM_R16(0x08a545ccu); /* base + 0x1e0 */
    r->input_pressed = MEM_R16(0x08a545ceu); /* + 0x1e2 */
    r->stick_direction = MEM_R16(0x08a545d6u); /* + 0x1ea */
    r->stick_pressed = MEM_R16(0x08a545d8u); /* + 0x1ec */
    r->input_history_index = MEM_R32(0x08a545e4u); /* + 0x1f8 */
    /* f_0891bf14 stores its 64-bit system-time sample at engine +0x18f0.
     * The next common update consumes the step derived from consecutive samples.
     * The signed +0x0a field participates in the stock two-stage integer division. */
    r->engine_time_us = (uint64_t)MEM_R32(0x08a65f70u) |
                       ((uint64_t)MEM_R32(0x08a65f74u) << 32);
    r->speed_factor = (int16_t)MEM_R16(0x08a543f6u);
    r->step_override_bits = MEM_R32(0x08a544a0u);
    /* f_08857878 passes this object's +8 pointer to f_088258c4, whose
     * counters and state-handler dispatch were inspected from the static code.
     * Restrict reads to the mapped 32 MiB PSP RAM and the observed class table. */
    if (MEM_R32(0x08a46580u) == 0x08a131f0u) {
        uint32_t p = MEM_R32(0x08a46588u);
        r->battle_object = p;
        if (p >= 0x08804000u && p <= 0x09ffffecu && !(p & 3u)) {
            r->battle_valid = 1;
            r->battle_state = MEM_R32(p + 4u);
            r->battle_ticks = MEM_R32(p + 12u);
            r->battle_calls = MEM_R32(p + 16u);
            uint32_t table = MEM_R32(p);
            if (r->battle_state < 256u && table >= 0x08804000u &&
                table <= 0x09fffbffu && !(table & 3u))
                r->battle_handler = MEM_R32(table + r->battle_state * 4u);
        }
    }
}

/* Denser call-boundary observations only in the controlled training interval.
 * Record the real instruction address; no opcode, return value or wait changes.
 * Most sites are before the call; d3e8/d420 are after the normal return checks. */
void mojin_frame_trace(const CpuState *s, uint32_t pc) {
    if (enabled == 0) return;
    uint32_t v = sr_display_vcount();
    if (v < 7400u || v >= 9000u || MEM_R32(0x08a3d294u) != 0x0885f978u) return;
    mojin_loop_trace(s, pc);
}
