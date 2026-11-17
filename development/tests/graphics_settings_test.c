/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "graphics_settings.h"
#include "overlay_host.h"
#include <SDL3/SDL.h>
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#define CHECK(x) do { if(!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); return 1; } } while(0)
static NkOverlayHost *host;
static SDL_Surface *surface;
static SDL_Renderer *renderer;
static NkOverlayModel model;
static int last_action;
static float display_scale=1.5f;
static int draw(void) {
    SDL_Delay(17); /* Advance the host at a normal UI frame interval. */
    NkOverlayAction a;
    SDL_FillSurfaceRect(surface,NULL,SDL_MapSurfaceRGBA(surface,25,35,48,255));
    if(!nk_overlay_host_draw(host,renderer,display_scale,1,&model,&a)) return 0;
    SDL_RenderPresent(renderer);
    last_action=(int)a.kind;
    (void)mojin_graphics_action((int)a.kind,a.value);
    return 1;
}
static int key(SDL_Keycode code) {
    SDL_Event event; SDL_zero(event);
    event.type=SDL_EVENT_KEY_DOWN; event.key.key=code; event.key.down=true;
    bool changed=nk_overlay_host_event(host,&event);
    event.type=SDL_EVENT_KEY_UP; event.key.down=false; nk_overlay_host_event(host,&event);
    if(!changed) { fprintf(stderr,"No UI event for key %u\n",(unsigned)code); return 0; }
    for(int i=0;i<3;i++) { if(!draw()) return 0; if(last_action) return 1; }
    return 1;
}

int main(int argc,char **argv) {
    CHECK(argc==3);
    char path[4096],bmp[4096],error[512]; wchar_t wide[4096],backup[4096];
    snprintf(path,sizeof(path),"%s/设置验证.ini",argv[1]);
    CHECK(MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,wide,4096));
    FILE *f=_wfopen(wide,L"wb"); CHECK(f);
    CHECK(fputs("; keep me\n[Graphics]\nRenderScale=4\nSSAA=2\nWindowWidth=960\nWindowHeight=544\nFullscreen=0\nFutureOption=42\n[Audio]\nVolume=77\n",f)>=0); CHECK(!fclose(f));
    MojinGraphicsOptions initial={4,2,960,544,0,60};
    mojin_graphics_configure(path,&initial);
    mojin_graphics_observe(1,4,2,960,544);
    CHECK(mojin_graphics_view()->scene_width==3840);
    CHECK(mojin_graphics_view()->composition_height==1088);
    CHECK(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_GAMEPAD));
    SDL_SetHint("SDL_RENDER_DRIVER","software");
    host=nk_overlay_host_create(argv[2],error,sizeof(error));
    if(!host) fprintf(stderr,"host: %s\n",error);
    CHECK(host);
    surface=SDL_CreateSurface(960,544,SDL_PIXELFORMAT_RGBA32); CHECK(surface);
    renderer=SDL_CreateSoftwareRenderer(surface); CHECK(renderer);
    nk_overlay_host_open(host,NK_OVERLAY_OPEN_USER);
    CHECK(nk_overlay_host_screen(host)==NK_OVERLAY_SCREEN_SETTINGS);
    for(int i=0;i<3;i++) CHECK(draw());
    CHECK(model.logical_width>=959.9f && model.logical_height>=543.9f);
    snprintf(bmp,sizeof(bmp),"%s/settings-960x544.bmp",argv[1]); CHECK(SDL_SaveBMP(surface,bmp));
    CHECK(key(SDLK_RIGHT));
    CHECK(last_action==MOJIN_GRAPHICS_ACTION_BASE+MOJIN_GRAPHICS_SCALE);
    CHECK(mojin_graphics_view()->pending.scale==6);
    CHECK(mojin_graphics_view()->composition_width==1920); /* Pending is not active. */
    CHECK(key(SDLK_RIGHT)); CHECK(mojin_graphics_view()->pending.scale==8);
    CHECK(key(SDLK_DOWN)); CHECK(key(SDLK_RIGHT)); CHECK(mojin_graphics_view()->pending.ssaa==4);
    CHECK(key(SDLK_DOWN));
    for(int i=0;i<4;i++) CHECK(key(SDLK_RIGHT));
    CHECK(mojin_graphics_view()->pending.width==3840);
    CHECK(key(SDLK_DOWN)); CHECK(key(SDLK_RIGHT)); CHECK(mojin_graphics_view()->pending.fullscreen==1);
    CHECK(key(SDLK_DOWN)); CHECK(key(SDLK_RIGHT)); CHECK(mojin_graphics_view()->pending.fps==120);
    CHECK(key(SDLK_DOWN)); CHECK(key(SDLK_LEFT)); CHECK(key(SDLK_LEFT)); CHECK(key(SDLK_RETURN));
    fprintf(stderr,"button action=%d status=%s\n",last_action,mojin_graphics_view()->status);
    snprintf(bmp,sizeof(bmp),"%s/settings-button.bmp",argv[1]); CHECK(SDL_SaveBMP(surface,bmp));
    CHECK(last_action==MOJIN_GRAPHICS_ACTION_SAVE);
    fprintf(stderr,"save status: %s\n",mojin_graphics_view()->status);
    CHECK(!mojin_graphics_view()->dirty);
    CHECK(GetPrivateProfileIntW(L"Graphics",L"RenderScale",0,wide)==8);
    CHECK(GetPrivateProfileIntW(L"Graphics",L"SSAA",0,wide)==4);
    CHECK(GetPrivateProfileIntW(L"Graphics",L"WindowWidth",0,wide)==3840);
    CHECK(GetPrivateProfileIntW(L"Graphics",L"FPS",0,wide)==120);
    CHECK(GetPrivateProfileIntW(L"Graphics",L"FutureOption",0,wide)==42);
    CHECK(GetPrivateProfileIntW(L"Audio",L"Volume",0,wide)==77);
    swprintf(backup,4096,L"%ls.previous",wide);
    CHECK(GetPrivateProfileIntW(L"Graphics",L"RenderScale",0,backup)==4);
    CHECK(draw()); snprintf(bmp,sizeof(bmp),"%s/settings-saved.bmp",argv[1]); CHECK(SDL_SaveBMP(surface,bmp));
    mojin_graphics_step(MOJIN_GRAPHICS_SCALE,-1);
    HANDLE locked=CreateFileW(wide,GENERIC_READ,0,NULL,OPEN_EXISTING,0,NULL); CHECK(locked!=INVALID_HANDLE_VALUE);
    CHECK(!mojin_graphics_save()); CHECK(mojin_graphics_view()->dirty);
    CHECK(mojin_graphics_view()->saved.scale==8); CloseHandle(locked);
    CHECK(GetPrivateProfileIntW(L"Graphics",L"RenderScale",0,wide)==8);
    mojin_graphics_reset(); CHECK(!mojin_graphics_view()->dirty);
    /* A reload uses the public launch reader, independent of the pending state. */
    MojinGraphicsOptions loaded={(int)GetPrivateProfileIntW(L"Graphics",L"RenderScale",0,wide),
        (int)GetPrivateProfileIntW(L"Graphics",L"SSAA",0,wide),
        (int)GetPrivateProfileIntW(L"Graphics",L"WindowWidth",0,wide),
        (int)GetPrivateProfileIntW(L"Graphics",L"WindowHeight",0,wide),
        (int)GetPrivateProfileIntW(L"Graphics",L"Fullscreen",0,wide),
        (int)GetPrivateProfileIntW(L"Graphics",L"FPS",60,wide)};
    CHECK(mojin_graphics_valid(&loaded));
    mojin_graphics_configure(path,&loaded); CHECK(mojin_graphics_view()->pending.scale==8);
    mojin_graphics_observe(1,8,1,2560,1600); /* Actual SSAA downgrade and constrained output. */
    CHECK(mojin_graphics_view()->active_ssaa==1 && mojin_graphics_view()->scene_width==3840);
    nk_overlay_host_unbind(host); SDL_DestroyRenderer(renderer); SDL_DestroySurface(surface);
    surface=SDL_CreateSurface(1280,720,SDL_PIXELFORMAT_RGBA32); CHECK(surface);
    renderer=SDL_CreateSoftwareRenderer(surface); CHECK(renderer);
    display_scale=2.0f;
    for(int i=0;i<3;i++) CHECK(draw());
    CHECK(model.logical_width>=959.9f && model.logical_height>=543.9f);
    snprintf(bmp,sizeof(bmp),"%s/settings-1280x720.bmp",argv[1]); CHECK(SDL_SaveBMP(surface,bmp));
    CHECK(key(SDLK_ESCAPE)); CHECK(nk_overlay_host_screen(host)==NK_OVERLAY_SCREEN_MENU);
    CHECK(draw()); CHECK(key(SDLK_ESCAPE)); CHECK(last_action==NK_OVERLAY_ACT_RESUME);
    nk_overlay_host_unbind(host); SDL_DestroyRenderer(renderer); SDL_DestroySurface(surface);
    nk_overlay_host_destroy(host); SDL_Quit();
    puts("PASS: settings navigation, 150/200% DPI fit, Unicode persistence, unrelated keys, previous copy, failed-write preservation, actual/pending distinction, back/resume");
    return 0;
}
