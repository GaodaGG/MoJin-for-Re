/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static float (*volatile original_minf)(float,float)=fminf;
static float (*volatile original_maxf)(float,float)=fmaxf;
static double (*volatile original_mind)(double,double)=fmin;
static double (*volatile original_maxd)(double,double)=fmax;
#include "graphics_math.h"
static uint64_t state=329;
static uint64_t next(void) {
    state^=state<<13;state^=state>>7;state^=state<<17;return state;
}
#define CHECK_BITS(expected,actual,n,name,x,y) do { if(memcmp(&(expected),&(actual),(n))) { \
    fprintf(stderr,"FAIL %s x=%llx y=%llx\n",(name),(unsigned long long)(x),(unsigned long long)(y)); exit(1); } } while(0)
static void pair(uint64_t x,uint64_t y) {
    uint32_t fx=(uint32_t)x,fy=(uint32_t)y;
    float a,b,expected,actual;
    memcpy(&a,&fx,4);memcpy(&b,&fy,4);
    expected=original_minf(a,b);actual=mojin_minf(a,b);CHECK_BITS(expected,actual,4,"minf",x,y);
    expected=original_maxf(a,b);actual=mojin_maxf(a,b);CHECK_BITS(expected,actual,4,"maxf",x,y);
    double c,d,de,da;
    memcpy(&c,&x,8);memcpy(&d,&y,8);
    de=original_mind(c,d);da=mojin_mind(c,d);CHECK_BITS(de,da,8,"mind",x,y);
    de=original_maxd(c,d);da=mojin_maxd(c,d);CHECK_BITS(de,da,8,"maxd",x,y);
}
int main(void) {
    const uint64_t special[]={0,UINT64_C(0x8000000000000000),1,UINT64_C(0x8000000000000001),
        UINT64_C(0x7ff0000000000000),UINT64_C(0xfff0000000000000),
        UINT64_C(0x7ff0000000000001),UINT64_C(0x7ff8000000000329),
        UINT64_C(0x80000000),UINT64_C(0x7f800000),UINT64_C(0xff800000),
        UINT64_C(0x7f800001),UINT64_C(0x7fc00329),UINT64_C(0x00800000),UINT64_C(0x007fffff)};
    unsigned boundaries=0;
    for(unsigned i=0;i<sizeof(special)/sizeof(*special);i++)
        for(unsigned j=0;j<sizeof(special)/sizeof(*special);j++) {pair(special[i],special[j]);++boundaries;}
    for(unsigned i=0;i<1000000;i++) {uint64_t a=next(),b=next();pair(a,b);}
    printf("PASS random_pairs=1000000 boundary_pairs=%u comparisons=4000900 bit_exact=1\n",boundaries);
    return 0;
}
