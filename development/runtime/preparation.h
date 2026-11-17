/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MOJIN_PREPARATION_H
#define MOJIN_PREPARATION_H
/* Host-only progress. Returns 0 after close/error; never executes guest code. */
int mojin_preparation_frame(unsigned done, unsigned total, unsigned failures);
void mojin_preparation_end(void);
/* 0 normal, 1 user closed, 2 presentation failure. Read before starting guest. */
int mojin_preparation_stop_reason(void);
#endif
