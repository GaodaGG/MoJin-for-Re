/* SPDX-License-Identifier: GPL-3.0-or-later
 * Matching library before any context exists. Context/transport operations
 * retain controlled refusals; this does not implement multiplayer.
 * Reference: hrydgard/pspautotests@70e72391 tests/net/adhoc/matching.{c,expected}
 * (Init/duplicate/Term, initial pool capacity=size-32, maximum=0, free=capacity),
 * PPSSPP@4392fe67 Core/HLE/sceNetAdhocMatching.cpp (pre-init stat error).
 * We reserve the requested pool using the runtime user-partition allocator.
 * Physical partition placement and arbitrary pool sizes remain unmeasured.
 */
#ifndef MOJIN_OFFLINE_MATCHING_H
#define MOJIN_OFFLINE_MATCHING_H

static struct {
    int initialized;
    uint32_t pool_uid, capacity;
} mojin_matching;

/* LoadExec resets the allocator itself; do not free its obsolete handles. */
static void mojin_matching_reset(void) {
    mojin_matching.initialized = 0;
    mojin_matching.pool_uid = 0xffffffffu;
    mojin_matching.capacity = 0;
}

static uint32_t h_NetAdhocMatchingInit(CpuState *s) {
    if (mojin_matching.initialized) return 0x80410812u;
    const uint32_t requested = s->r[4];
    if (requested < 32u || requested > 0x02000000u)
        return hle_unmodelled_stop("sceNetAdhocMatchingInit", "unvalidated pool size 0x%08x", requested);
    const uint32_t uid = alloc_block(requested);
    if (uid == 0xffffffffu)
        return hle_unmodelled_stop("sceNetAdhocMatchingInit", "pool allocation failed; PSP error not measured");
    mojin_matching.pool_uid = uid;
    mojin_matching.capacity = requested - 32u;
    mojin_matching.initialized = 1;
    fprintf(stderr, "MOJIN_SERVICE sceNetAdhocMatchingInit reserved=0x%x capacity=0x%x; contexts unsupported\n",
            requested, mojin_matching.capacity);
    return 0;
}

static uint32_t h_NetAdhocMatchingTerm(CpuState *s) {
    (void)s;
    if (mojin_matching.initialized) free_block(mojin_matching.pool_uid);
    mojin_matching_reset();
    return 0;
}

static uint32_t h_NetAdhocMatchingGetPoolStat(CpuState *s) {
    if (!mojin_matching.initialized) return 0x80410813u;
    const uint32_t output = s->r[4];
    if (!output || !sr_guest_span_writable(output, 12u)) return 0x80410806u;
    MEM_W32(output, mojin_matching.capacity);
    MEM_W32(output + 4u, 0u); /* No context can exist in this implementation. */
    MEM_W32(output + 8u, mojin_matching.capacity);
    return 0;
}
#endif
