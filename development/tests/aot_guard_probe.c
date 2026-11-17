#include <stdlib.h>
#include "guest_interp.h"

int main(int argc, char **argv) {
    CpuState state = {0};
    state.pc = 0x08804114u;
    state.r[31] = 0x08804500u;
    if (argc != 2) return 2;
    switch (atoi(argv[1])) {
    case 0: sr_guest_interp_run(&state, 0x08805000u, NULL); break;
    case 1: sr_guest_interp_run_tail_step(&state, 0x08805000u, NULL); break;
    case 2: sr_guest_interp_run_with_boundary(&state, 0x08805000u, NULL, NULL); break;
    case 3: sr_vfpu_interp(&state, 0xd0468000u); break;
    default: return 2;
    }
    return 99; /* No fallback may return, report success, or execute guest code. */
}
