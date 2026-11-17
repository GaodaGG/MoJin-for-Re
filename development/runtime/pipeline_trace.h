/* SPDX-License-Identifier: GPL-3.0-or-later
 * Explicit diagnostics only. Record exact Vulkan pipeline descriptions; never
 * alter state, draw counts or fallback behavior while collecting a catalog.
 */
static int mojin_pipeline_preparing;
static void mojin_pipeline_trace(const PipeKey *k,int rmw,VkResult result,uint64_t elapsed) {
    static int checked;
    static FILE *file;
    if(!checked) {
        checked=1;
        const char *path=getenv("SR_MOJIN_PIPELINE_TRACE");
        if(path && path[0]) {
            file=fopen(path,"w");
            if(!file) fprintf(stderr,"MOJIN_PIPELINE_TRACE cannot open diagnostic output\n");
        }
    }
    if(!file) return;
    fprintf(file,"{\"shader_set\":\"%016llx\",\"key\":[%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u],"
        "\"rmw\":%d,\"result\":%d,\"elapsed_ns\":%llu,\"sdl_time_ns\":%llu,\"phase\":\"%s\"}\n",
        (unsigned long long)pcache_shader_set(),k->blend_on,k->srcf,k->dstf,k->eq,k->cull,k->ztest,k->zwrite,
        k->zfunc,k->cmask,k->tnl,k->azero,k->zbias,rmw,(int)result,(unsigned long long)elapsed,
        (unsigned long long)SDL_GetTicksNS(),mojin_pipeline_preparing?"preparation":"draw");
    fflush(file);
}
