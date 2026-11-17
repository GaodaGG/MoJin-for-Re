/* SPDX-License-Identifier: GPL-3.0-or-later */
static void mojin_trace_media(CpuState *s, const char *api, uint32_t result, uint32_t au) {
    if (!getenv("SR_MPEGLOG")) return;
    uint32_t pts_hi = 0, pts_lo = 0, length = 0;
    if (au && sr_guest_span_readable(au, 24u)) {
        /* SceMpegAu stores the high 32-bit half first, even on little-endian PSP. */
        pts_hi = MEM_R32(au);
        pts_lo = MEM_R32(au + 4u);
        length = MEM_R32(au + 20u);
    }
    fprintf(stderr, "MOJIN_MEDIA api=%s result=%08x ra=%08x v=%u mpeg=%08x "
                    "a1=%08x a2=%08x a3=%08x au=%08x pts=%08x%08x len=%u\n",
            api, result, s->r[31], sr_display_vcount(), s->r[4], s->r[5], s->r[6],
            s->r[7], au, pts_hi, pts_lo, length);
}
