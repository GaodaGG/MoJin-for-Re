/* SPDX-License-Identifier: GPL-3.0-or-later
 * Service tests use a bounded fake partition to check ownership/failed calls.
 * They do not validate the upstream guest memory mapper or physical PSP timing.
 */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "guest_interp.h"

static uint32_t memory[5], live_pool, allocation_size;
static int allocations, frees, refuse_allocation, stopped;
static uint32_t alloc_block(uint32_t size) {
    if (refuse_allocation) return 0xffffffffu;
    if (live_pool) return 0xffffffffu;
    allocations++;
    allocation_size = size;
    return live_pool = 0x123;
}
static uint32_t free_block(uint32_t uid) {
    if (uid != live_pool || !live_pool) return 0xffffffffu;
    frees++;
    live_pool = 0;
    return 0;
}
static uint32_t hle_unmodelled_stop(const char *name, const char *format, ...) {
    (void)name; (void)format; stopped++;
    return 0x80010086u; /* Test sentinel; production stops the diagnostic run. */
}
#undef sr_guest_span_writable
#define sr_guest_span_writable(addr, size) ((addr) == 4u && (size) == 12u)
#undef MEM_W32
#define MEM_W32(addr, value) (memory[(addr) / 4u] = (value))
#include "../runtime/offline_matching.h"
#define CHECK(test) do { if (!(test)) { fprintf(stderr, "FAIL line %d\n", __LINE__); return 1; } } while (0)

int main(void) {
    CpuState state = {0};
    for (int i=0; i<5; i++) memory[i] = 0xdeadbeefu;
    mojin_matching_reset();
    state.r[4] = 4;
    CHECK(h_NetAdhocMatchingGetPoolStat(&state) == 0x80410813u);
    CHECK(memory[1] == 0xdeadbeefu);
    CHECK(h_NetAdhocMatchingTerm(&state) == 0u && frees == 0);
    state.r[4] = 0x20000;
    CHECK(h_NetAdhocMatchingInit(&state) == 0u && allocation_size == 0x20000);
    CHECK(h_NetAdhocMatchingInit(&state) == 0x80410812u && allocations == 1);
    state.r[4] = 0;
    CHECK(h_NetAdhocMatchingGetPoolStat(&state) == 0x80410806u && memory[1] == 0xdeadbeefu);
    state.r[4] = 8; /* Non-null buffer without a full writable span. */
    CHECK(h_NetAdhocMatchingGetPoolStat(&state) == 0x80410806u && memory[2] == 0xdeadbeefu);
    state.r[4] = 4;
    CHECK(h_NetAdhocMatchingGetPoolStat(&state) == 0u);
    CHECK(memory[0] == 0xdeadbeefu && memory[4] == 0xdeadbeefu);
    CHECK(memory[1] == 0x1ffe0u && memory[2] == 0u && memory[3] == 0x1ffe0u);
    CHECK(h_NetAdhocMatchingTerm(&state) == 0u && frees == 1 && !live_pool);
    CHECK(h_NetAdhocMatchingTerm(&state) == 0u && frees == 1);
    state.r[4] = 0x3000;
    refuse_allocation = 1;
    CHECK(h_NetAdhocMatchingInit(&state) == 0x80010086u && stopped == 1);
    state.r[4] = 4;
    CHECK(h_NetAdhocMatchingGetPoolStat(&state) == 0x80410813u);
    refuse_allocation = 0;
    state.r[4] = 0x3000;
    CHECK(h_NetAdhocMatchingInit(&state) == 0u && allocation_size == 0x3000);
    mojin_matching_reset(); /* Mirrors allocator reset at LoadExec. */
    live_pool = 0;
    CHECK(h_NetAdhocMatchingTerm(&state) == 0u && frees == 1);
    CHECK(h_NetAdhocMatchingInit(&state) == 0u && allocations == 3);
    CHECK(h_NetAdhocMatchingTerm(&state) == 0u && frees == 2);
    puts("PASS: matching lifecycle, recorded initial statistics, ownership and invalid-buffer atomicity");
    return 0;
}
