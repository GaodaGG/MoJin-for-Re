/* SPDX-License-Identifier: GPL-3.0-or-later
 * Inline finite comparisons for the native graphics pipeline. No fast-math:
 * NaNs, infinities and pairs of signed zeros retain the C library path.
 * The wrappers are defined before the aliases so fallback calls stay original.
 */
#ifndef MOJIN_GRAPHICS_MATH_H
#define MOJIN_GRAPHICS_MATH_H
#include <stdint.h>
#include <string.h>
#include <math.h>
/* Prevent the compiler from substituting a different NaN-payload convention
 * for the exceptional fallback. These pointers are used only on that path. */
static float (*volatile mojin_lib_minf)(float,float)=fminf;
static float (*volatile mojin_lib_maxf)(float,float)=fmaxf;
static double (*volatile mojin_lib_mind)(double,double)=fmin;
static double (*volatile mojin_lib_maxd)(double,double)=fmax;
static inline int mojin_regular_float_pair(float a, float b) {
    uint32_t x,y;
    memcpy(&x,&a,sizeof(x)); memcpy(&y,&b,sizeof(y));
    x &= UINT32_C(0x7fffffff); y &= UINT32_C(0x7fffffff);
    return x < UINT32_C(0x7f800000) && y < UINT32_C(0x7f800000) && (x|y);
}
static inline int mojin_regular_double_pair(double a, double b) {
    uint64_t x,y;
    memcpy(&x,&a,sizeof(x)); memcpy(&y,&b,sizeof(y));
    x &= UINT64_C(0x7fffffffffffffff); y &= UINT64_C(0x7fffffffffffffff);
    return x < UINT64_C(0x7ff0000000000000) && y < UINT64_C(0x7ff0000000000000) && (x|y);
}
static inline float mojin_minf(float a,float b) {
    return mojin_regular_float_pair(a,b) ? (a<b?a:b) : mojin_lib_minf(a,b);
}
static inline float mojin_maxf(float a,float b) {
    return mojin_regular_float_pair(a,b) ? (a>b?a:b) : mojin_lib_maxf(a,b);
}
static inline double mojin_mind(double a,double b) {
    return mojin_regular_double_pair(a,b) ? (a<b?a:b) : mojin_lib_mind(a,b);
}
static inline double mojin_maxd(double a,double b) {
    return mojin_regular_double_pair(a,b) ? (a>b?a:b) : mojin_lib_maxd(a,b);
}
#define fminf mojin_minf
#define fmaxf mojin_maxf
#define fmin mojin_mind
#define fmax mojin_maxd
#endif
