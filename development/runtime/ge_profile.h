/* SPDX-License-Identifier: GPL-3.0-or-later
 * Two read-only graphics profile snapshots; no per-frame output or resets.
 * Included by the opt-in loop observer. Profiling overhead is diagnostic only.
 */
#include "ge_shared.h"
#include "gpu_sdl3vk/ge_gpu.h"
static GeCpuProfileStats mojin_ge_samples[2];
static GeGpuCpuProfileStats mojin_gpu_samples[2];
static uint32_t mojin_ge_v[2];
static uint64_t mojin_ge_ns[2];
static unsigned mojin_ge_count;
static int mojin_ge_enabled = -1;
static void mojin_ge_profile_sample(uint32_t v, uint32_t pc) {
    if (mojin_ge_enabled < 0) {
        const char *flag = getenv("SR_GPU_CPU_PROFILE");
        mojin_ge_enabled = flag && strcmp(flag,"1") == 0;
    }
    if (!mojin_ge_enabled || mojin_ge_count == 2 || pc != 0x0891d3e8u ||
        v < (mojin_ge_count ? 8800u : 7600u)) return;
    unsigned i = mojin_ge_count++;
    mojin_ge_v[i] = v;
    mojin_ge_ns[i] = SDL_GetTicksNS();
    ge_cpu_profile_get(&mojin_ge_samples[i]);
    gegpu_cpu_profile_stats_get(&mojin_gpu_samples[i]);
}
static void mojin_ge_profile_finish(void) {
    if (!mojin_ge_enabled || !mojin_ge_count) return;
    fprintf(stderr,"MOJIN_GE_PROFILE samples=%u from=%u to=%u wall_ns=%llu\n",
        mojin_ge_count,mojin_ge_v[0],mojin_ge_v[1],
        (unsigned long long)(mojin_ge_ns[1]-mojin_ge_ns[0]));
    if (mojin_ge_count != 2) return;
    static const char *ge_names[] = {"list_total","command_dispatch","primitive","gpu_hook","block_transfer","clut_load","flush"};
    static const char *gpu_names[] = {"state_prep","state_key","pipeline_lookup","pipeline_create","descriptor_alloc","descriptor_update","bind_record","object_lookup","texture_decode","texture_shadow","vertex_prep","snapshot_target","snapshot_decision","snapshot_region","snapshot_metadata","command_record","memcpy","heap"};
    for (unsigned i=0;i<GE_CPU_PHASE_COUNT;i++)
        fprintf(stderr,"MOJIN_GE_CPU phase=%s calls=%llu ns=%llu\n",ge_names[i],
            (unsigned long long)(mojin_ge_samples[1].phase[i].calls-mojin_ge_samples[0].phase[i].calls),
            (unsigned long long)(mojin_ge_samples[1].phase[i].ns-mojin_ge_samples[0].phase[i].ns));
    for (unsigned i=0;i<GEGPU_CPU_PHASE_COUNT;i++)
        fprintf(stderr,"MOJIN_GPU_CPU phase=%s calls=%llu ns=%llu\n",gpu_names[i],
            mojin_gpu_samples[1].phase[i].calls-mojin_gpu_samples[0].phase[i].calls,
            mojin_gpu_samples[1].phase[i].ns-mojin_gpu_samples[0].phase[i].ns);
}
