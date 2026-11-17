/* SPDX-License-Identifier: GPL-3.0-or-later
 * Included after normal cache lookup functions; prewarm uses those same owners.
 * Only describes known states. No draw suppression or stub pipeline on a miss.
 */
#include "preparation.h"
#include "../generated/runtime/pipeline_catalog.h"

static void mojin_prepare_pipelines(void) {
    const char *enabled=getenv("SR_MOJIN_PREPARE");
    if(enabled && !strcmp(enabled,"0")) {
        fprintf(stderr,"MOJIN_PREPARATION skipped=disabled\n"); return;
    }
    if(pcache_shader_set()!=MOJIN_CATALOG_SHADER_SET) {
        fprintf(stderr,"MOJIN_PREPARATION skipped=shader_set_mismatch normal_misses_retained=1\n"); return;
    }
    unsigned count=sizeof(mojin_pipeline_catalog)/sizeof(mojin_pipeline_catalog[0]);
    const char *limit=getenv("SR_MOJIN_PREP_LIMIT");
    if(limit && limit[0]) {
        unsigned n=(unsigned)strtoul(limit,NULL,10);
        if(n<count) count=n;
    }
    unsigned eligible=0,done=0,failures=0;
    for(unsigned i=0;i<count;i++) {
        const PipeKey *k=&mojin_pipeline_catalog[i].key;
        int rmw=mojin_pipeline_catalog[i].rmw;
        if((rmw && (!s_dst_interlock || !s_fs_rmw)) || (k->tnl && !s_vs_tnl)) continue;
        eligible++;
    }
    uint64_t started=SDL_GetTicksNS();
    fprintf(stderr,"MOJIN_PREPARATION begin total=%u shader_set=%016llx\n",eligible,(unsigned long long)pcache_shader_set());
    mojin_pipeline_preparing=1;
    if(mojin_preparation_frame(0,eligible,0)) {
        for(unsigned i=0;i<count;i++) {
            const PipeKey *k=&mojin_pipeline_catalog[i].key;
            int rmw=mojin_pipeline_catalog[i].rmw;
            if((rmw && (!s_dst_interlock || !s_fs_rmw)) || (k->tnl && !s_vs_tnl)) continue;
            VkPipeline p=rmw?pipe_get_rmw(k,rmw==2):pipe_get(k);
            if(!p) failures++;
            done++;
            if(!mojin_preparation_frame(done,eligible,failures)) break;
        }
    }
    mojin_pipeline_preparing=0;
    mojin_preparation_end();
    fprintf(stderr,"MOJIN_PREPARATION end completed=%u total=%u failures=%u stop=%d elapsed_ms=%.3f normal_misses_retained=1\n",
        done,eligible,failures,mojin_preparation_stop_reason(),(double)(SDL_GetTicksNS()-started)/1e6);
}
