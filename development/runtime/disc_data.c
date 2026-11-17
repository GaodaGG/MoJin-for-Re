/* SPDX-License-Identifier: GPL-3.0-or-later
 * Title-owned loose-file backend for the existing disc ABI. No ISO parser or
 * container is opened. LBA addresses identify ranges of ordinary asset files.
 * Unmapped sectors are an explicit unsupported request, never fabricated data.
 */
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <limits.h>
#include "iso.h"
#include "perf.h"
#include "../generated/runtime/disc_manifest.h"
#ifdef _WIN32
#include <windows.h>
#include <wchar.h>
static SRWLOCK s_lock = SRWLOCK_INIT;
#define LOCK() AcquireSRWLockExclusive(&s_lock)
#define UNLOCK() ReleaseSRWLockExclusive(&s_lock)
#else
#include <pthread.h>
static pthread_mutex_t s_lock = PTHREAD_MUTEX_INITIALIZER;
#define LOCK() pthread_mutex_lock(&s_lock)
#define UNLOCK() pthread_mutex_unlock(&s_lock)
#endif
static FILE *s_handles[MOJIN_DISC_COUNT];
static int s_state; /* root is immutable after successful initialization */
static uint64_t s_reads, s_bytes, s_errors;

static void close_data(void) {
    for (size_t i=0;i<MOJIN_DISC_COUNT;i++) if (s_handles[i]) { fclose(s_handles[i]); s_handles[i]=NULL; }
}
static void report_data(void) {
    fprintf(stderr,"MOJIN_GAME_DATA reads=%llu bytes=%llu errors=%llu backend=files\n",
        (unsigned long long)s_reads,(unsigned long long)s_bytes,(unsigned long long)s_errors);
    close_data();
}
static int init_locked(void) {
    if (s_state) return s_state > 0 ? 0 : -1;
    s_state=-1;
#ifdef _WIN32
    const wchar_t *root=_wgetenv(L"SR_MOJIN_GAME_DATA");
#else
    const char *root=getenv("SR_MOJIN_GAME_DATA");
#endif
    if (!root || !*root) { fprintf(stderr,"MOJIN_GAME_DATA missing resource root; ISO fallback is unavailable\n"); return -1; }
    unsigned count=0;
    for (size_t i=0;i<MOJIN_DISC_COUNT;i++) {
        if (s_files[i].directory) continue;
#ifdef _WIN32
        wchar_t path[32768], relative[512];
        if (!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s_files[i].path,-1,relative,512) ||
            swprintf(path,32768,L"%ls/%ls",root,relative)<0) goto failed;
        FILE *f=_wfopen(path,L"rb");
#else
        char path[4096];
        int n=snprintf(path,sizeof(path),"%s/%s",root,s_files[i].path);
        if (n<0 || (size_t)n>=sizeof(path)) goto failed;
        FILE *f=fopen(path,"rb");
#endif
        s_handles[i]=f;
        if (!f || fseek(f,0,SEEK_END) || ftell(f)!=(long)s_files[i].size || fseek(f,0,SEEK_SET)) {
            fprintf(stderr,"MOJIN_GAME_DATA missing or wrong-size file: %s\n",s_files[i].path);
            goto failed;
        }
        count++;
    }
    s_state=1;
    atexit(report_data);
    fprintf(stderr,"MOJIN_GAME_DATA backend=files files=%u manifest=%s iso_reader=absent\n",count,MOJIN_DISC_MANIFEST_SHA);
    return 0;
failed:
    close_data();
    return -1;
}

/* Normalize only guest paths. Host filenames always come from the fixed table. */
static int normalize(const char *p,char out[512]) {
    if (!p) return 0;
    const char *colon=strchr(p,':');
    if (colon) p=colon+1;
    size_t used=0;
    while (*p) {
        while (*p=='/' || *p=='\\') p++;
        const char *first=p;
        while (*p && *p!='/' && *p!='\\') p++;
        size_t n=(size_t)(p-first);
        if (!n || (n==1 && *first=='.')) continue;
        if ((n==2 && first[0]=='.' && first[1]=='.') || used+n+1>=512) return 0;
        if (used) out[used++]='/';
        for (size_t i=0;i<n;i++) {
            unsigned char c=(unsigned char)first[i];
            if (c<32 || c>=127 || c==':') return 0;
            out[used++]=(c>='a' && c<='z')?(char)(c-32):(char)c;
        }
    }
    out[used]=0;
    return 1;
}
static int hex(const char **cursor,uint32_t *value) {
    const char *p=*cursor;
    if (p[0]=='0' && p[1]=='X') p+=2;
    uint32_t v=0; unsigned n=0;
    while ((*p>='0' && *p<='9') || (*p>='A' && *p<='F')) {
        if (++n>8) return 0;
        v=(v<<4)+(uint32_t)(*p<='9'?*p-'0':*p-'A'+10); p++;
    }
    if (!n) return 0;
    *cursor=p; *value=v; return 1;
}
static int extent(const char *p,uint32_t *lba,uint32_t *size) {
    if (strncmp(p,"SCE_LBN",7)) return 0;
    p+=7;
    if (!hex(&p,lba) || strncmp(p,"_SIZE",5)) return 0;
    p+=5;
    return hex(&p,size) && !*p && *size;
}
static int range_file(uint64_t pos,uint32_t bytes) {
    for (size_t i=0;i<MOJIN_DISC_COUNT;i++) {
        const MojinDiscFile *e=&s_files[i];
        uint64_t start=(uint64_t)e->lba*2048u;
        if (!e->directory && pos>=start && pos-start<=e->size && bytes<=e->size-(pos-start)) return (int)i;
    }
    return -1;
}
int iso_init(void) { LOCK(); int rc=init_locked(); UNLOCK(); return rc; }
int iso_lookup(const char *path,uint32_t *lba,uint32_t *size) {
    char norm[512];
    if (!lba || !size || !normalize(path,norm) || !*norm) return -1;
    size_t len=strlen(path);
    if (len && (path[len-1]=='/' || path[len-1]=='\\')) return -1;
    if (iso_init()) return -1;
    uint32_t a,b;
    if (extent(norm,&a,&b)) {
        if (range_file((uint64_t)a*2048u,b)<0) return -1;
        *lba=a; *size=b; return 0;
    }
    for (size_t i=0;i<MOJIN_DISC_COUNT;i++) if (!s_files[i].directory && !strcmp(norm,s_files[i].path)) {
        *lba=s_files[i].lba; *size=s_files[i].size; return 0;
    }
    return -1;
}
int iso_sector_extent_path(const char *path,char *out,size_t cap) {
    char norm[512]; uint32_t a,b;
    if (!path || !out || (strncmp(path,"disc0:",6) && strncmp(path,"umd0:",5)) ||
        !normalize(path,norm) || !extent(norm,&a,&b)) return 0;
    int n=snprintf(out,cap,"disc0:/sce_lbn0x%x_size0x%x",a,b);
    return n>0 && (size_t)n<cap;
}
int iso_read(uint32_t lba,uint32_t offset,void *dst,uint32_t bytes) {
    if (!dst || bytes>INT_MAX) return -1;
    if (!bytes) return 0;
    uint64_t started=sr_perf_now_ns(), pos=(uint64_t)lba*2048u+offset;
    int rc=-1;
    LOCK();
    int i=range_file(pos,bytes);
    if (!init_locked() && i>=0) {
        FILE *f=s_handles[i];
        uint64_t off=pos-(uint64_t)s_files[i].lba*2048u;
        if (!fseek(f,(long)off,SEEK_SET)) {
            size_t got=fread(dst,1,bytes,f);
            if (got==bytes) { rc=(int)got; s_reads++; s_bytes+=got; }
        }
    }
    if (rc<0) {
        if (s_errors++<16) fprintf(stderr,"MOJIN_GAME_DATA read failed lba=%u offset=%u bytes=%u mapped=%d\n",lba,offset,bytes,i>=0);
    }
    UNLOCK();
    if (started) sr_perf_storage_read(SR_PERF_STORAGE_ISO,bytes,started,rc>=0);
    return rc;
}
int iso_sector_count(uint32_t *out) {
    if (!out || iso_init()) return -1;
    *out=MOJIN_DISC_SECTORS; return 0;
}
uint32_t iso_physical_lba(uint32_t lba) { return lba; }
int iso_list(const char *path,uint32_t index,IsoDirEntry *out) {
    char norm[512];
    if (!out || !normalize(path,norm) || iso_init()) return -1;
    size_t n=strlen(norm); int directory=!n;
    for (size_t i=0;i<MOJIN_DISC_COUNT;i++) if (s_files[i].directory && !strcmp(norm,s_files[i].path)) directory=1;
    if (!directory) return -1;
    for (size_t i=0;i<MOJIN_DISC_COUNT;i++) {
        const MojinDiscFile *e=&s_files[i]; const char *name=e->path;
        if (n) { if (strncmp(name,norm,n) || name[n]!='/') continue; name+=n+1; }
        if (strchr(name,'/')) continue;
        if (index--) continue;
        memset(out,0,sizeof(*out));
        snprintf(out->name,sizeof(out->name),"%s",name);
        out->lba=e->lba; out->size=e->directory?0:e->size; out->is_dir=e->directory;
        return 1;
    }
    return 0;
}
