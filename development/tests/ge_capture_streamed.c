/* Capture real read/write ordering: streamed list append and conflicting reread. */
#include "ge_capture.h"
#include "recomp.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint8_t *g_mem;
volatile int g_sr_vram_read_pending;
void sr_ge_vram_read_prepare(uint32_t a, uint32_t b) {(void)a; (void)b;}
void sr_ge_vram_write_prepare(uint32_t a, uint32_t b) {(void)a; (void)b;}
void sr_ge_vram_write_commit(uint32_t a, uint32_t b) {(void)a; (void)b;}
#define CHECK(c, text) do { if (!(c)) { fprintf(stderr, "FAIL: %s\n", text); return 1; } } while (0)
int main(int argc, char **argv) {
    CHECK(argc == 3, "mode and private output path required");
    uint8_t *arena = calloc(0x0c000000u, 1);
    CHECK(arena, "arena allocation");
    g_mem = arena + 0x08000000u;
    GeState state = {0};
    uint16_t *zbuf = calloc(GE_CAPTURE_ZBUF_WORDS, sizeof(uint16_t));
    CHECK(zbuf, "depth allocation");
    state.fbp = 0x04000000u; state.fbw = 512; state.fbfmt = 3;
    const uint32_t list = 0x08001000u;
    SR_HOST(list)[0] = 0x31;
    CHECK(ge_capture_begin(argv[2], 77, list, &state, zbuf), "begin");
    ge_capture_note_memory(list, 4);
    if (!strcmp(argv[1], "mutation")) {
        SR_HOST(list)[0] = 0x99;
        ge_capture_note_memory(list | 0x40000000u, 4);
        CHECK(!ge_capture_active(), "static fixture must refuse two consumed values at one address");
        CHECK(!ge_capture_end(&state), "refused capture must not be finalized");
        CHECK(!ge_capture_begin(argv[2], 77, list + 8u, &state, zbuf), "same-frame retry must not hide an earlier refusal");
        puts("PASS: conflicting reread refused, including uncached alias");
    } else {
        /* CPU fills another command after the GE consumed the first word. */
        SR_HOST(list)[4] = 0x42; SR_HOST(list)[7] = 0x04;
        ge_capture_note_memory((list + 4u) | 0x40000000u, 4);
        ge_capture_note_memory(list + 0xff0u, 4);
        SR_HOST(list)[0xffe] = 0x15; SR_HOST(list)[0xfff] = 0x26;
        SR_HOST(list)[0x1000] = 0x37; SR_HOST(list)[0x1001] = 0x48;
        ge_capture_note_memory(list + 0xffeu, 4);
        ge_capture_note_memory(list, 4); /* unchanged reread is representable */
        CHECK(ge_capture_end(&state), "end");
        GeCaptureFixture fixture;
        CHECK(ge_capture_load(argv[2], &fixture), "load");
        memset(SR_HOST(list), 0, 0x2000);
        CHECK(ge_capture_apply(&fixture, &state, zbuf), "apply");
        CHECK(SR_HOST(list)[0] == 0x31, "original consumed command preserved");
        CHECK(SR_HOST(list)[4] == 0x42 && SR_HOST(list)[7] == 0x04, "late command bytes in an already captured page");
        CHECK(SR_HOST(list)[0xffe] == 0x15 && SR_HOST(list)[0xfff] == 0x26 &&
              SR_HOST(list)[0x1000] == 0x37 && SR_HOST(list)[0x1001] == 0x48,
              "cross-page late write captured at consumption");
        ge_capture_free(&fixture);
        puts("PASS: streamed append, cross-page read, aliases, unchanged reread and roundtrip");
    }
    free(zbuf); free(arena);
    return 0;
}
