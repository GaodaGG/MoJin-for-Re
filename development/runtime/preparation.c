/* SPDX-License-Identifier: GPL-3.0-or-later
 * Portable SDL presentation before the guest starts. No game frames, fake work,
 * timing multipliers, desktop automation, or mandatory extra DLL link dependency.
 */
#include "preparation.h"
#include "../third_party/nakagawa/src/rt/gpu_sdl3vk/sdl3vk.h"
#include <SDL3/SDL.h>
#include <SDL3_ttf/SDL_ttf.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <wchar.h>
#endif

static struct {
    SDL_Surface *canvas;
    SDL_SharedObject *library;
    bool (SDLCALL *init)(void);
    TTF_Font *(SDLCALL *open_font)(const char *, float);
    SDL_Surface *(SDLCALL *text)(TTF_Font *, const char *, size_t, SDL_Color);
    void (SDLCALL *close_font)(TTF_Font *);
    void (SDLCALL *quit)(void);
    TTF_Font *font;
    int attempted, initialized, stop, rgba;
    float scale;
} prep;

static void canvas_close(void) {
    if(prep.font) prep.close_font(prep.font);
    prep.font=NULL;
    SDL_DestroySurface(prep.canvas); prep.canvas=NULL;
}

static SDL_SharedObject *load_font_library(const char *path) {
#ifdef _WIN32
    /* Same temporary dependency-directory scope as pinned nk_ui_ttf.c. The
     * runtime intentionally excludes PATH from its Windows DLL search. */
    wchar_t folder[32768];
    DLL_DIRECTORY_COOKIE cookie=NULL;
    if(MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,folder,32768)>0) {
        for(wchar_t *p=folder;*p;p++) if(*p==L'/') *p=L'\\';
        wchar_t *slash=wcsrchr(folder,L'\\');
        if(slash) { *slash=0; cookie=AddDllDirectory(folder); }
    }
    SDL_SharedObject *library=SDL_LoadObject(path);
    if(cookie) RemoveDllDirectory(cookie);
    return library;
#else
    return SDL_LoadObject(path);
#endif
}

static void fonts_open(void) {
    if(prep.attempted) return;
    prep.attempted=1;
    const char *lib=getenv("SR_MOJIN_TTF_LIBRARY");
#ifdef _WIN32
    if(!lib || !lib[0]) lib="SDL3_ttf.dll";
#elif defined(__APPLE__)
    if(!lib || !lib[0]) lib="libSDL3_ttf.0.dylib";
#else
    if(!lib || !lib[0]) lib="libSDL3_ttf.so.0";
#endif
    prep.library=load_font_library(lib);
    if(!prep.library) goto missing;
#define LOAD(member,symbol) *(SDL_FunctionPointer *)&prep.member=SDL_LoadFunction(prep.library,symbol)
    LOAD(init,"TTF_Init"); LOAD(open_font,"TTF_OpenFont");
    LOAD(text,"TTF_RenderText_Blended"); LOAD(close_font,"TTF_CloseFont"); LOAD(quit,"TTF_Quit");
#undef LOAD
    if(!prep.init || !prep.open_font || !prep.text || !prep.close_font || !prep.quit || !prep.init()) goto missing;
    prep.initialized=1;
    return;
missing:
    fprintf(stderr,"MOJIN_PREPARATION font library unavailable (%s); using built-in English text and progress bar\n",SDL_GetError());
}

static void rect(int x,int y,int w,int h,Uint8 r,Uint8 g,Uint8 b) {
    SDL_Rect area={x,y,w,h};
    SDL_FillSurfaceRect(prep.canvas,&area,SDL_MapSurfaceRGBA(prep.canvas,r,g,b,255));
}

static void label(int x,int y,const char *text,SDL_Color color) {
    SDL_Surface *line=prep.text(prep.font,text,0,color);
    if(!line) return;
    SDL_Rect dest={x,y,line->w,line->h};
    SDL_BlitSurface(line,NULL,prep.canvas,&dest);
    SDL_DestroySurface(line);
}

static int paint(unsigned done,unsigned total,unsigned failures) {
    int width=0,height=0,rgba=0;
    if(!sdl3vk_overlay_extent(&width,&height,&rgba)) return 1; /* minimized: still do useful preparation */
    if(!prep.canvas || prep.canvas->w!=width || prep.canvas->h!=height || prep.rgba!=rgba) {
        canvas_close();
        prep.rgba=rgba;
        prep.canvas=SDL_CreateSurface(width,height,rgba?SDL_PIXELFORMAT_RGBA32:SDL_PIXELFORMAT_BGRA32);
        if(!prep.canvas) { prep.stop=2; return 0; }
        prep.scale=SDL_min(width/960.0f,height/544.0f);
        fonts_open();
        const char *font=getenv("SR_MOJIN_CJK_FONT");
        if(!font || !font[0]) font="assets/fonts/ui/noto-sans-sc/NotoSansCJKsc-Regular.otf";
        if(prep.initialized) prep.font=prep.open_font(font,24.0f*prep.scale);
        if(!prep.font) fprintf(stderr,"MOJIN_PREPARATION CJK face unavailable; built-in text active\n");
        else fprintf(stderr,"MOJIN_PREPARATION CJK face ready pixel_size=%.1f\n",24.0f*prep.scale);
    }
    const float scale=prep.scale;
    const int x=(int)(width/2-400*scale), y=(int)(height/2-110*scale);
    rect(0,0,width,height,10,17,27);
    rect(x,y,(int)(800*scale),(int)(220*scale),18,28,42);
    rect(x+(int)(32*scale),y+(int)(110*scale),(int)(736*scale),(int)(12*scale),40,55,73);
    rect(x+(int)(32*scale),y+(int)(110*scale),(int)(736*scale*(total?(double)done/total:1)),(int)(12*scale),91,195,226);
    char progress[128];
    if(prep.font) {
        label(x+(int)(32*scale),y+(int)(28*scale),"准备图形效果",(SDL_Color){237,242,247,255});
        snprintf(progress,sizeof(progress),"%u / %u    ·    %u%%",done,total,total?100*done/total:100);
        label(x+(int)(32*scale),y+(int)(65*scale),progress,(SDL_Color){160,180,200,255});
        label(x+(int)(32*scale),y+(int)(148*scale),failures?"部分效果将在使用时继续准备":"准备完成后将自动进入游戏",(SDL_Color){160,180,200,255});
    } else {
        SDL_Renderer *renderer=SDL_CreateSoftwareRenderer(prep.canvas);
        if(renderer) {
            SDL_SetRenderScale(renderer,2*scale,2*scale);
            SDL_SetRenderDrawColor(renderer,237,242,247,255);
            snprintf(progress,sizeof(progress),"Preparing graphics  %u / %u",done,total);
            SDL_RenderDebugText(renderer,x/(2*scale)+16,y/(2*scale)+20,progress);
            SDL_RenderPresent(renderer); SDL_DestroyRenderer(renderer);
        }
    }
    int result=sdl3vk_present_overlay(prep.canvas->pixels,prep.canvas->pitch);
    if(result==0) prep.stop=1;
    else if(result<0) prep.stop=2;
    const char *capture=getenv("SR_MOJIN_PREP_CAPTURE");
    if(result==1 && capture && capture[0] && (done==0 || done==total)) {
        char path[4096];
        int n=snprintf(path,sizeof(path),"%s-%03u.bmp",capture,done);
        if(n>0 && (size_t)n<sizeof(path))
            fprintf(stderr,"MOJIN_PREPARATION capture=%u saved=%d\n",done,(int)SDL_SaveBMP(prep.canvas,path));
    }
    return result==2?2:!prep.stop;
}

int mojin_preparation_frame(unsigned done,unsigned total,unsigned failures) {
    if(prep.stop) return 0;
    /* Explicit own-process test hook, cleared in no-argument startup. */
    const char *cancel=getenv("SR_MOJIN_PREP_CANCEL_AT");
    if(cancel && cancel[0] && (unsigned)strtoul(cancel,NULL,10)==done) {
        SDL_Event event; SDL_zero(event); event.type=SDL_EVENT_QUIT; SDL_PushEvent(&event);
    }
    if(!sdl3vk_poll()) { prep.stop=1; return 0; }
    for(int attempt=0;attempt<2;attempt++) {
        int result=paint(done,total,failures);
        if(result!=2) return result;
    }
    return 1; /* a resize will redraw at the next item */
}

void mojin_preparation_end(void) {
    sdl3vk_overlay_release();
    canvas_close();
    if(prep.initialized) prep.quit();
    if(prep.library) SDL_UnloadObject(prep.library);
    prep.initialized=0; prep.library=NULL; prep.attempted=0;
}

int mojin_preparation_stop_reason(void) { return prep.stop; }
