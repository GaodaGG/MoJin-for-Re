/* SPDX-License-Identifier: GPL-3.0-or-later
 * Project-local diagnostic boundary. The upstream interpreter objects are
 * replaced, not linked. No guest opcode is fetched, decoded, or executed here.
 */
#include <stdio.h>
#include <stdlib.h>
#include "guest_interp.h"

static _Noreturn void aot_required(const CpuState *s, uint32_t target, const char *kind) {
    fprintf(stderr, "MOJIN_AOT_REQUIRED kind=%s pc=0x%08x target=0x%08x ra=0x%08x\n",
            kind, s->pc, target, s->r[31]);
    fflush(stderr);
    exit(86);
}

#ifdef MOJIN_GUEST_GUARD
SrGuestInterpResult sr_guest_interp_run(CpuState *s, uint32_t entry, SrGuestInterpFault *fault) {
    (void)fault;
    aot_required(s, entry, "dispatch");
}
SrGuestInterpResult sr_guest_interp_run_tail_step(CpuState *s, uint32_t entry, SrGuestInterpFault *fault) {
    (void)fault;
    aot_required(s, entry, "tail");
}
SrGuestInterpResult sr_guest_interp_run_with_boundary(CpuState *s, uint32_t entry,
        const SrGuestInterpCallBoundary *boundary, SrGuestInterpFault *fault) {
    (void)boundary; (void)fault;
    aot_required(s, entry, "call");
}
const char *sr_guest_interp_result_name(SrGuestInterpResult result) {
    (void)result;
    return "interpreter-not-linked";
}
#endif

#ifdef MOJIN_VFPU_GUARD
int sr_vfpu_interp(CpuState *s, uint32_t word) {
    aot_required(s, word, "vfpu-needs-static-lowering");
}
#endif
