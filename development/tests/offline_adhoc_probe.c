/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "guest_interp.h"
#include "../runtime/offline_adhoc.h"

int main(void) {
    CpuState state = {0};
    /* The expected return sequence comes from the pinned PPSSPP lifecycle, not
     * the implementation's private state. Exercise Term before Init, duplicate
     * Init, Term/Init, and a LoadExec-style reset without an explicit Term. */
    printf("%08x\n", h_NetAdhocTerm(&state));
    printf("%08x\n", h_NetAdhocInit(&state));
    printf("%08x\n", h_NetAdhocInit(&state));
    printf("%08x\n", h_NetAdhocTerm(&state));
    printf("%08x\n", h_NetAdhocTerm(&state));
    printf("%08x\n", h_NetAdhocInit(&state));
    mojin_adhoc_reset();
    printf("%08x\n", h_NetAdhocInit(&state));
    return 0;
}
