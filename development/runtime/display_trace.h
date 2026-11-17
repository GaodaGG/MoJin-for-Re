/* SPDX-License-Identifier: GPL-3.0-or-later
 * Observe display state transitions without changing guest state or return codes.
 * Buffer swaps with identical format/stride/sync are intentionally summarized.
 */
static void mojin_trace_display_request(CpuState *s, uint32_t addr, int32_t stride,
                                       int32_t fmt, uint32_t sync) {
    static int enabled = -1, have_previous;
    static uint32_t previous[10], sequence;
    if (enabled < 0) enabled = getenv("SR_MOJIN_DISPLAY_TRACE") != NULL;
    if (!enabled) return;
    sequence++;
    const uint32_t current[10] = {addr == 0, (uint32_t)stride, (uint32_t)fmt, sync,
        s_display_latched.addr == 0, (uint32_t)s_display_latched.stride,
        (uint32_t)s_display_latched.fmt, (uint32_t)s_display_latched_pending,
        s->r[31], sync == 0u && (stride != s_display_latched.stride || fmt != s_display_latched.fmt)};
    if (have_previous && memcmp(previous, current, sizeof(current)) == 0) return;
    memcpy(previous, current, sizeof(current));
    have_previous = 1;
    fprintf(stderr, "MOJIN_SET_FB seq=%u v=%u pc=%08x ra=%08x req=%08x/%d/%d sync=%u "
                    "latched=%08x/%d/%d pending=%d active=%08x/%d/%d mismatch=%u\n",
            sequence, s_vcount, s->pc, s->r[31], addr, stride, fmt, sync,
            s_display_latched.addr, s_display_latched.stride, s_display_latched.fmt,
            s_display_latched_pending, s_display_active.addr, s_display_active.stride,
            s_display_active.fmt, current[9]);
}
