/* SPDX-License-Identifier: GPL-3.0-or-later
 * Offline ad hoc library lifecycle. No transport, socket or GameMode objects can
 * be created by this slice; their upstream handlers remain controlled refusals.
 * Semantics reference: PPSSPP 4392fe67d06f8a88c317641daa71595f8c540de8,
 * Core/HLE/sceNetAdhoc.cpp sceNetAdhocInit / NetAdhoc_Term, ErrorCodes.h.
 * These are source-based semantics, not a new measurement on physical hardware.
 * If transports are added, Term/reset MUST retire their resources here too.
 */
#ifndef MOJIN_OFFLINE_ADHOC_H
#define MOJIN_OFFLINE_ADHOC_H
#include <stdint.h>
#include <stdio.h>

static int mojin_adhoc_initialized;

static void mojin_adhoc_reset(void) {
    mojin_adhoc_initialized = 0;
}

static uint32_t h_NetAdhocInit(CpuState *s) {
    (void)s;
    if (mojin_adhoc_initialized) return 0x80410713u;
    mojin_adhoc_initialized = 1;
    fprintf(stderr, "MOJIN_SERVICE sceNetAdhocInit initialized offline lifecycle; transport unsupported\n");
    return 0u;
}

static uint32_t h_NetAdhocTerm(CpuState *s) {
    (void)s;
    mojin_adhoc_reset();
    return 0u;
}
#endif
