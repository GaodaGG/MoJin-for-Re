/* SPDX-License-Identifier: GPL-3.0-or-later
 * Settings state is independent of SDL and the game's CPU. The Windows writer
 * stages a copy, preserves unrelated INI entries, and replaces only on success.
 */
#include "graphics_settings.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <wchar.h>
#endif

static MojinGraphicsView view;
static int initialized;
static char settings_path[32768];
static const int scales[] = {1, 2, 3, 4, 6, 8};
static const int aa_levels[] = {1, 2, 4};
static const int sizes[][2] = {{960,544},{1280,720},{1920,1080},{2560,1440},{3840,2160}};

static int equal(const MojinGraphicsOptions *a, const MojinGraphicsOptions *b) {
    return a->scale == b->scale && a->ssaa == b->ssaa && a->width == b->width &&
           a->height == b->height && a->fullscreen == b->fullscreen && a->fps == b->fps;
}

int mojin_graphics_valid(const MojinGraphicsOptions *o) {
    return o && o->scale >= 1 && o->scale <= 8 &&
        (o->ssaa == 1 || o->ssaa == 2 || o->ssaa == 4) &&
        o->width >= 480 && o->width <= 3840 && o->height >= 272 && o->height <= 2176 &&
        (o->fullscreen == 0 || o->fullscreen == 1) && (o->fps == 60 || o->fps == 120);
}

void mojin_graphics_configure(const char *path, const MojinGraphicsOptions *o) {
    memset(&view, 0, sizeof(view));
    settings_path[0] = 0;
    initialized = 1;
    if (mojin_graphics_valid(o)) view.saved = view.pending = *o;
    else view.saved = view.pending = (MojinGraphicsOptions){1,1,960,544,0,60};
    if (path && path[0] && strlen(path) < sizeof(settings_path)) {
        memcpy(settings_path, path, strlen(path) + 1);
        view.writable = 1;
    }
    snprintf(view.status, sizeof(view.status), "%s", view.writable ?
        "选择后保存，下次启动生效。" : "诊断运行未指定设置文件，不能保存。 ");
}

const MojinGraphicsView *mojin_graphics_view(void) {
    if (!initialized) {
        /* Explicit development CLI only. Double-click startup configures this
         * directly after validating its own INI and clearing diagnostics. */
        const char *r = getenv("SR_RESOLUTION_SCALE"), *a = getenv("SR_MOJIN_SETTINGS_SSAA");
        const char *w = getenv("SR_MOJIN_WINDOW_SIZE");
        const char *fps = getenv("SR_MOJIN_GAME_FPS");
        MojinGraphicsOptions o = {r ? atoi(r) : 1, a ? atoi(a) : 1,960,544,0,fps ? atoi(fps) : 60};
        if (w) (void)sscanf(w, "%dx%d", &o.width, &o.height);
        mojin_graphics_configure(getenv("SR_MOJIN_SETTINGS_FILE"), &o);
    }
    return &view;
}

void mojin_graphics_observe(int ready, int scale, int ssaa, int width, int height) {
    (void)mojin_graphics_view();
    view.renderer_ready = ready;
    view.composition_width = ready ? 480 * scale : 480;
    view.composition_height = ready ? 272 * scale : 272;
    view.active_ssaa = ready ? ssaa : 1;
    view.scene_width = view.composition_width * view.active_ssaa;
    view.scene_height = view.composition_height * view.active_ssaa;
    view.output_width = width; view.output_height = height;
}

static int step_index(int current, int count, int direction) {
    if (current < 0) return direction < 0 ? count - 1 : 0;
    return (current + (direction < 0 ? count - 1 : 1)) % count;
}

void mojin_graphics_step(int field, int direction) {
    (void)mojin_graphics_view();
    int i = -1;
    switch (field) {
    case MOJIN_GRAPHICS_SCALE:
        for (int n=0;n<6;n++) if (scales[n] == view.pending.scale) i=n;
        view.pending.scale = scales[step_index(i,6,direction)]; break;
    case MOJIN_GRAPHICS_AA:
        for (int n=0;n<3;n++) if (aa_levels[n] == view.pending.ssaa) i=n;
        view.pending.ssaa = aa_levels[step_index(i,3,direction)]; break;
    case MOJIN_GRAPHICS_WINDOW:
        for (int n=0;n<5;n++) if (sizes[n][0] == view.pending.width && sizes[n][1] == view.pending.height) i=n;
        i=step_index(i,5,direction); view.pending.width=sizes[i][0]; view.pending.height=sizes[i][1]; break;
    case MOJIN_GRAPHICS_FULLSCREEN: view.pending.fullscreen = !view.pending.fullscreen; break;
    case MOJIN_GRAPHICS_FPS: view.pending.fps = view.pending.fps == 60 ? 120 : 60; break;
    default: return;
    }
    view.dirty = !equal(&view.pending,&view.saved);
    snprintf(view.status,sizeof(view.status),"%s",view.dirty ? "尚未保存；当前画质不变。" : "选择与已保存设置相同。");
}

void mojin_graphics_reset(void) {
    (void)mojin_graphics_view(); view.pending = view.saved; view.dirty = 0;
    snprintf(view.status,sizeof(view.status),"%s","已恢复已保存的选择。");
}

void mojin_graphics_choice(int field, char *out, size_t capacity) {
    const MojinGraphicsOptions *o = &mojin_graphics_view()->pending;
    switch (field) {
    case MOJIN_GRAPHICS_SCALE: snprintf(out,capacity,"%d × %d%s",480*o->scale,272*o->scale,o->scale>4?" [实验]":""); break;
    case MOJIN_GRAPHICS_AA: snprintf(out,capacity,"%s",o->ssaa==1?"关闭":o->ssaa==2?"每轴 2 倍 SSAA":"每轴 4 倍 [实验]"); break;
    case MOJIN_GRAPHICS_WINDOW: snprintf(out,capacity,"%d × %d",o->width,o->height); break;
    case MOJIN_GRAPHICS_FULLSCREEN: snprintf(out,capacity,"%s",o->fullscreen?"桌面全屏":"窗口"); break;
    case MOJIN_GRAPHICS_FPS: snprintf(out,capacity,"%s",o->fps == 120 ? "120 FPS [实验]" : "原速（60 FPS）"); break;
    default: if(capacity) out[0]=0; break;
    }
}

int mojin_graphics_save(void) {
    (void)mojin_graphics_view();
    if (!view.writable || !mojin_graphics_valid(&view.pending)) {
        snprintf(view.status,sizeof(view.status),"没有可写设置文件，未保存。"); return 0;
    }
#ifdef _WIN32
    wchar_t path[32768], temp[32768], backup[32768];
    DWORD error=0;
    if (!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,settings_path,-1,path,32700)) goto failed;
    /* Require an absolute target: never write next to an unrelated working dir. */
    if (!(path[0] && path[1]==L':' && (path[2]==L'\\'||path[2]==L'/')) &&
        !(path[0]==L'\\' && path[1]==L'\\')) { SetLastError(ERROR_BAD_PATHNAME); goto failed; }
    swprintf(temp,32768,L"%ls.%lu.tmp",path,(unsigned long)GetCurrentProcessId());
    swprintf(backup,32768,L"%ls.previous",path);
    if (!CopyFileW(path,temp,TRUE)) {
        if (GetLastError()!=ERROR_FILE_NOT_FOUND) goto failed;
        HANDLE f=CreateFileW(temp,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
        if(f==INVALID_HANDLE_VALUE) goto failed;
        CloseHandle(f);
    }
    const wchar_t *keys[]={L"RenderScale",L"SSAA",L"WindowWidth",L"WindowHeight",L"Fullscreen",L"FPS"};
    const int values[]={view.pending.scale,view.pending.ssaa,view.pending.width,view.pending.height,view.pending.fullscreen,view.pending.fps};
    for(int n=0;n<6;n++) {
        wchar_t number[32]; swprintf(number,32,L"%d",values[n]);
        if(!WritePrivateProfileStringW(L"Graphics",keys[n],number,temp)) goto staged_failure;
    }
    HANDLE staged=CreateFileW(temp,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);
    if(staged==INVALID_HANDLE_VALUE) goto staged_failure;
    BOOL flushed=FlushFileBuffers(staged); error=GetLastError(); CloseHandle(staged);
    if(!flushed) { SetLastError(error); goto staged_failure; }
    /* Keep the previous settings on disk before the atomic replacement. */
    if(GetFileAttributesW(path)!=INVALID_FILE_ATTRIBUTES) {
        if(!CopyFileW(path,backup,FALSE)) goto staged_failure;
    }
    if(!MoveFileExW(temp,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)) goto staged_failure;
    view.saved=view.pending; view.dirty=0;
    snprintf(view.status,sizeof(view.status),"%s","已保存，下次启动生效；当前画质不变。");
    fprintf(stderr,"MOJIN_SETTINGS saved scale=%d ssaa=%d window=%dx%d fullscreen=%d fps=%d\n",
        view.saved.scale,view.saved.ssaa,view.saved.width,view.saved.height,view.saved.fullscreen,view.saved.fps);
    return 1;
staged_failure:
    error=GetLastError(); DeleteFileW(temp); SetLastError(error);
failed:
    snprintf(view.status,sizeof(view.status),"保存失败（系统错误 %lu），原设置保留。",(unsigned long)GetLastError());
#else
    snprintf(view.status,sizeof(view.status),"当前平台的设置保存尚未实现。");
#endif
    return 0;
}

int mojin_graphics_action(int kind, int value) {
    if(kind >= MOJIN_GRAPHICS_ACTION_BASE && kind < MOJIN_GRAPHICS_ACTION_BASE + MOJIN_GRAPHICS_FIELD_COUNT) {
        mojin_graphics_step(kind - MOJIN_GRAPHICS_ACTION_BASE, value); return 1;
    }
    if(kind == MOJIN_GRAPHICS_ACTION_SAVE) { (void)mojin_graphics_save(); return 1; }
    if(kind == MOJIN_GRAPHICS_ACTION_RESET) { mojin_graphics_reset(); return 1; }
    return 0;
}
