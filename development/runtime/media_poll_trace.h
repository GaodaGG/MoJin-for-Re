/* SPDX-License-Identifier: GPL-3.0-or-later
 * Bounded, opt-in counters for movie startup. No I/O in the polling loop and
 * no guest state, return value, scheduling or timing changes. One host-clock
 * read per populated vblank bucket, not per import. Flush on normal exit.
 */
#include <SDL3/SDL.h>
enum { MOJIN_MEDIA_AVAILABLE, MOJIN_MEDIA_PUT, MOJIN_MEDIA_AVC_AU,
       MOJIN_MEDIA_ATRAC_AU, MOJIN_MEDIA_AVC_DECODE, MOJIN_MEDIA_ATRAC_DECODE };
typedef struct {
    uint64_t first_ns, count[6], zero_available, put_packets;
    uint32_t last_available, available_ra, available_uid, errors[6];
} MojinMediaPollBucket;
static MojinMediaPollBucket mojin_media_poll[4096];
static FILE *mojin_media_poll_file;
static int mojin_media_poll_enabled = -1;
static void mojin_media_poll_finish(void) {
    FILE *f = mojin_media_poll_file;
    if (!f) return;
    fputs("vcount,first_ns,available_calls,zero_available,last_available,available_ra,available_uid,put_calls,put_packets,avc_au,atrac_au,avc_decode,atrac_decode,available_errors,put_errors,avc_au_errors,atrac_au_errors,avc_decode_errors,atrac_decode_errors\n", f);
    for (unsigned v = 0; v < 4096; ++v) {
        const MojinMediaPollBucket *b = &mojin_media_poll[v];
        if (!b->first_ns) continue;
        fprintf(f, "%u,%llu,%llu,%llu,%u,%08x,%x,%llu,%llu,%llu,%llu,%llu,%llu",
                v, (unsigned long long)b->first_ns,
                (unsigned long long)b->count[0], (unsigned long long)b->zero_available,
                b->last_available, b->available_ra, b->available_uid,
                (unsigned long long)b->count[1], (unsigned long long)b->put_packets,
                (unsigned long long)b->count[2], (unsigned long long)b->count[3],
                (unsigned long long)b->count[4], (unsigned long long)b->count[5]);
        for (unsigned i = 0; i < 6; ++i) fprintf(f, ",%u", b->errors[i]);
        fputc('\n', f);
    }
    if (ferror(f)) fprintf(stderr, "MOJIN_MEDIA_POLL: write failed\n");
    fclose(f);
    mojin_media_poll_file = NULL;
}
static void mojin_media_poll_note(CpuState *s, unsigned kind, uint32_t result) {
    if (mojin_media_poll_enabled < 0) {
        const char *path = getenv("SR_MOJIN_MEDIA_POLL_TRACE");
        mojin_media_poll_enabled = 0;
        if (path && path[0]) {
            mojin_media_poll_file = fopen(path, "wb");
            if (mojin_media_poll_file) {
                mojin_media_poll_enabled = 1;
                atexit(mojin_media_poll_finish);
            } else fprintf(stderr, "MOJIN_MEDIA_POLL: cannot open diagnostic output\n");
        }
    }
    if (!mojin_media_poll_enabled) return;
    uint32_t v = sr_display_vcount();
    if (v >= 4096 || kind >= 6) return;
    MojinMediaPollBucket *b = &mojin_media_poll[v];
    if (!b->first_ns) b->first_ns = SDL_GetTicksNS();
    b->count[kind]++;
    if ((int32_t)result < 0) b->errors[kind]++;
    if (kind == MOJIN_MEDIA_AVAILABLE) {
        b->zero_available += result == 0;
        b->last_available = result;
        b->available_ra = s->r[31];
        b->available_uid = sched_current_uid();
    } else if (kind == MOJIN_MEDIA_PUT && (int32_t)result > 0) {
        b->put_packets += result;
    }
}
