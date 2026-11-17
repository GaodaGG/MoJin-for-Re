/* SPDX-License-Identifier: GPL-3.0-or-later
 * Windows modal-loop scheduling; enabled only by SR_MOJIN_WINDOW_PUMP=cooperative.
 * SDL's documented WINDOW_EXPOSED callback supplies opportunities to return to
 * the caller while PumpEvents is inside the OS move/resize loop. All work stays
 * on one OS thread; the guest scheduler is never recursively invoked.
 */
#include <SDL3/SDL.h>
#include "sr_coro.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>

static struct {
    SrCoro *pump, *caller;
    SDL_Window *window;
    SDL_ThreadID owner;
    unsigned long yields, cycles;
    int inside;
} mojin_pump;

static bool SDLCALL mojin_pump_watch(void *unused, SDL_Event *event) {
    (void)unused;
    /* Watches can run on other threads. Only this pump's own stack may yield. */
    if (event->type == SDL_EVENT_WINDOW_EXPOSED && mojin_pump.pump &&
        SDL_GetCurrentThreadID() == mojin_pump.owner &&
        sr_coro_current() == mojin_pump.pump && mojin_pump.caller &&
        event->window.windowID == SDL_GetWindowID(mojin_pump.window)) {
        mojin_pump.yields++;
        sr_coro_switch(mojin_pump.caller);
    }
    return true;
}

static void mojin_pump_body(void *unused) {
    (void)unused;
    for (;;) {
        mojin_pump.inside = 1;
        SDL_PumpEvents();
        mojin_pump.inside = 0;
        mojin_pump.cycles++;
        sr_coro_switch(mojin_pump.caller);
    }
}

static int mojin_pump_start(SDL_Window *window) {
    if (mojin_pump.pump) return mojin_pump.window == window;
    if (!sr_coro_current() && !sr_coro_main()) return 0;
    mojin_pump.yields = mojin_pump.cycles = 0;
    mojin_pump.inside = 0;
    mojin_pump.caller = NULL;
    mojin_pump.window = window;
    mojin_pump.owner = SDL_GetCurrentThreadID();
    mojin_pump.pump = sr_coro_create(mojin_pump_body, NULL, 2u << 20);
    if (!mojin_pump.pump) return 0;
    if (!SDL_AddEventWatch(mojin_pump_watch, NULL)) {
        sr_coro_destroy(mojin_pump.pump);
        mojin_pump.pump = NULL;
        return 0;
    }
    return 1;
}

static int mojin_pump_configure(SDL_Window *window) {
    const char *mode = getenv("SR_MOJIN_WINDOW_PUMP");
    if (!mode || !mode[0] || strcmp(mode, "legacy") == 0) return 1;
    if (strcmp(mode, "cooperative") != 0) {
        fprintf(stderr, "MOJIN_WINDOW_PUMP invalid mode: %s\n", mode);
        return 0;
    }
    const int ok = mojin_pump_start(window);
    fprintf(stderr, "MOJIN_WINDOW_PUMP cooperative %s (same OS thread, separate event stack)\n", ok ? "enabled" : "failed");
    return ok;
}

static void mojin_pump_cycle(void) {
    if (!mojin_pump.pump) return;
    if (SDL_GetCurrentThreadID() != mojin_pump.owner || sr_coro_current() == mojin_pump.pump) {
        fprintf(stderr, "MOJIN_WINDOW_PUMP invariant: wrong thread or recursive pump\n");
        abort();
    }
    mojin_pump.caller = sr_coro_current();
    sr_coro_switch(mojin_pump.pump);
}

static int mojin_pump_next(SDL_Event *event) {
    if (!mojin_pump.pump) return SDL_PollEvent(event);
    int result;
    do {
        result = SDL_PeepEvents(event, 1, SDL_GETEVENT, SDL_EVENT_FIRST, SDL_EVENT_LAST);
    } while (result > 0 && event->type == SDL_EVENT_POLL_SENTINEL);
    if (result < 0) {
        fprintf(stderr, "MOJIN_WINDOW_PUMP queue failure: %s\n", SDL_GetError());
        abort();
    }
    return result;
}

static void mojin_pump_stop(void) {
    if (!mojin_pump.pump) return;
    if (mojin_pump.inside) {
        /* Unwind a live OS modal loop before freeing the suspended pump stack. */
        HWND hwnd = (HWND)SDL_GetPointerProperty(SDL_GetWindowProperties(mojin_pump.window),
                                                SDL_PROP_WINDOW_WIN32_HWND_POINTER, NULL);
        if (!hwnd || !PostMessageW(hwnd, WM_CANCELMODE, 0, 0)) {
            fprintf(stderr, "MOJIN_WINDOW_PUMP could not cancel modal loop\n");
            abort();
        }
        while (mojin_pump.inside) mojin_pump_cycle();
    }
    SDL_RemoveEventWatch(mojin_pump_watch, NULL);
    sr_coro_destroy(mojin_pump.pump);
    mojin_pump.pump = NULL;
    mojin_pump.caller = NULL;
    fprintf(stderr, "MOJIN_WINDOW_PUMP cycles=%lu exposed_yields=%lu\n", mojin_pump.cycles, mojin_pump.yields);
}
#else
static int mojin_pump_configure(SDL_Window *window) {
    (void)window;
    const char *mode = getenv("SR_MOJIN_WINDOW_PUMP");
    if (mode && mode[0] && strcmp(mode, "legacy") != 0) {
        fprintf(stderr, "MOJIN_WINDOW_PUMP cooperative backend is only validated on Windows\n");
        return 0;
    }
    return 1;
}
static void mojin_pump_cycle(void) {}
static int mojin_pump_next(SDL_Event *event) { return SDL_PollEvent(event); }
static void mojin_pump_stop(void) {}
#endif
