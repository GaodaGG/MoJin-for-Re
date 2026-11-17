/* SPDX-License-Identifier: GPL-3.0-or-later */
#define SDL_MAIN_HANDLED
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../runtime/window_pump.h"

int main(int argc, char **argv) {
    const int cooperative = argc > 1 && strcmp(argv[1], "cooperative") == 0;
    const int seconds = argc > 2 ? atoi(argv[2]) : 45;
    if (seconds < 1 || seconds > 120) return 2;
    SDL_SetMainReady();
    if (!SDL_Init(SDL_INIT_VIDEO)) return 3;
    SDL_Window *window = SDL_CreateWindow(cooperative ? "MoJin window test - cooperative" : "MoJin window test - baseline",
                                          640, 320, SDL_WINDOW_RESIZABLE);
    if (!window) return 4;
    SDL_Renderer *renderer = SDL_CreateRenderer(window, "software");
    if (!renderer) return 5;
    _putenv_s("SR_MOJIN_WINDOW_PUMP", cooperative ? "cooperative" : "legacy");
    if (!mojin_pump_configure(window)) return 6;
    Uint64 start = SDL_GetTicksNS(), last = start, last_report = start, max_gap = 0;
    unsigned long frames = 0, last_frames = 0;
    int quit = 0;
    fprintf(stderr, "BEGIN mode=%s SDL=%d\n", cooperative ? "cooperative" : "baseline", SDL_GetVersion());
    fflush(stderr);
    while (!quit && SDL_GetTicksNS() - start < (Uint64)seconds * 1000000000ull) {
        if (cooperative) mojin_pump_cycle();
        SDL_Event event;
        while (mojin_pump_next(&event)) if (event.type == SDL_EVENT_QUIT) quit = 1;
        Uint64 now = SDL_GetTicksNS(), gap = now - last;
        last = now;
        if (gap > max_gap) max_gap = gap;
        if (gap > 100000000ull) fprintf(stderr, "STALL frame=%lu elapsed_ms=%llu gap_ms=%.3f\n", frames,
            (unsigned long long)((now-start)/1000000ull), (double)gap/1000000.0);
        SDL_SetRenderDrawColor(renderer, 18, 27, 42, 255);
        SDL_RenderClear(renderer);
        SDL_SetRenderDrawColor(renderer, cooperative ? 70 : 240, cooperative ? 210 : 150, 110, 255);
        SDL_FRect box = {30.0f + (float)(frames % 260) * 2.0f, 155, 50, 50};
        SDL_RenderFillRect(renderer, &box);
        char label[160];
        snprintf(label, sizeof(label), "%s | frame %lu | max gap %.1f ms", cooperative ? "COOPERATIVE" : "BASELINE", frames, (double)max_gap/1000000.0);
        SDL_RenderDebugText(renderer, 20, 30, label);
        SDL_RenderDebugText(renderer, 20, 65, "Drag / resize this test window. No game data is loaded.");
        SDL_RenderDebugText(renderer, 20, 90, "The square and frame counter should keep advancing.");
        SDL_RenderPresent(renderer);
        frames++;
        if (now-last_report >= 1000000000ull) {
            fprintf(stderr, "TICK elapsed_ms=%llu frames=%lu delta=%lu yields=%lu\n", (unsigned long long)((now-start)/1000000ull),
                    frames, frames-last_frames, mojin_pump.yields);
            fflush(stderr);
            last_report=now; last_frames=frames;
        }
        SDL_Delay(16);
    }
    mojin_pump_stop();
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    fprintf(stderr, "END frames=%lu max_gap_ms=%.3f quit=%d\n", frames, (double)max_gap/1000000.0, quit);
    return 0;
}
