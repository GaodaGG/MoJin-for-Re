/* SPDX-License-Identifier: GPL-3.0-or-later
 * Bounded experiment: retain fractional title ticks, not a global time multiplier.
 * The inspected positive-speed ratio simplifies to delta_us * speed / 66668.
 * The original generated clamp/fallback still executes after this calculation.
 */
#ifndef MOJIN_STEP_CLOCK_H
#define MOJIN_STEP_CLOCK_H
#include <stdint.h>

#define MOJIN_STEP_DENOMINATOR 66668u
typedef struct {
    uint64_t last_time;
    uint32_t remainder;
    int32_t speed;
    int active;
} MojinStepClock;

static inline void mojin_step_clock_reset(MojinStepClock *clock) {
    clock->last_time = 0;
    clock->remainder = 0;
    clock->speed = 0;
    clock->active = 0;
}

/* 1: applied; 0: preserve stock boundaries/inactive path; -1: wrong hook inputs.
 * stock is the original quotient BEFORE its fallback/clamp. Never substitute a
 * carried result when the original zero-step fallback or long-frame clamp applies.
 */
static inline int mojin_step_clock_update(MojinStepClock *clock,
        uint64_t previous, uint64_t now, int32_t speed, uint32_t stock,
        int enabled, uint32_t *result) {
    *result = stock;
    if (!enabled || now <= previous || speed <= 0 || speed > 32767 ||
        now - previous > 1000000u) {
        mojin_step_clock_reset(clock);
        return 0;
    }
    uint64_t delta = now - previous;
    uint64_t expected = ((delta * 100u) / 16667u) * ((uint64_t)speed * 32u) / 12800u;
    if (expected != stock) {
        mojin_step_clock_reset(clock);
        return -1;
    }
    uint64_t numerator = delta * (uint32_t)speed;
    if (!stock || stock >= 128u || numerator < MOJIN_STEP_DENOMINATOR ||
        numerator >= 128ull * MOJIN_STEP_DENOMINATOR) {
        mojin_step_clock_reset(clock);
        return 0;
    }
    if (!clock->active || clock->last_time != previous || clock->speed != speed)
        clock->remainder = 0;
    uint64_t total = numerator + clock->remainder;
    *result = (uint32_t)(total / MOJIN_STEP_DENOMINATOR);
    clock->remainder = (uint32_t)(total % MOJIN_STEP_DENOMINATOR);
    clock->last_time = now;
    clock->speed = speed;
    clock->active = 1;
    return 1;
}
#endif
