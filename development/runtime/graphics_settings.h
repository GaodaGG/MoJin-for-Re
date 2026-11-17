/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef MOJIN_GRAPHICS_SETTINGS_H
#define MOJIN_GRAPHICS_SETTINGS_H
#include <stddef.h>

typedef struct {
    int scale, ssaa, width, height, fullscreen, fps;
} MojinGraphicsOptions;

typedef struct {
    MojinGraphicsOptions saved, pending;
    int composition_width, composition_height, scene_width, scene_height;
    int output_width, output_height, active_ssaa, renderer_ready;
    int writable, dirty;
    char status[256];
} MojinGraphicsView;

enum { MOJIN_GRAPHICS_SCALE, MOJIN_GRAPHICS_AA, MOJIN_GRAPHICS_WINDOW,
       MOJIN_GRAPHICS_FULLSCREEN, MOJIN_GRAPHICS_FPS, MOJIN_GRAPHICS_FIELD_COUNT };
#define MOJIN_GRAPHICS_ACTION_BASE 100
#define MOJIN_GRAPHICS_ACTION_SAVE 110
#define MOJIN_GRAPHICS_ACTION_RESET 111

int mojin_graphics_valid(const MojinGraphicsOptions *options);
void mojin_graphics_configure(const char *utf8_path, const MojinGraphicsOptions *options);
const MojinGraphicsView *mojin_graphics_view(void);
void mojin_graphics_observe(int ready, int scale, int ssaa, int width, int height);
void mojin_graphics_step(int field, int direction);
void mojin_graphics_reset(void);
int mojin_graphics_save(void);
int mojin_graphics_action(int kind, int value);
void mojin_graphics_choice(int field, char *out, size_t capacity);
/* The Vulkan implementation reports allocated settings, never just the request. */
int mojin_ge_settings(int *scale, int *ssaa);
#endif
