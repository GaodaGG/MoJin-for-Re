/* SPDX-License-Identifier: GPL-3.0-or-later
 * No-argument entry for the native AOT game. No child process or interpreter.
 * Explicit developer command lines keep their existing diagnostic behavior.
 */
#include "graphics_settings.h"
#include "preparation.h"
#include "iso.h"
#ifdef _WIN32
#include <wchar.h>
#include <direct.h>

static int mojin_start_error(const wchar_t *message) {
    MessageBoxW(NULL, message, L"魔法禁书目录", MB_OK | MB_ICONERROR);
    return 0;
}

static int mojin_set_wide_env(const char *name, const wchar_t *value) {
    wchar_t wide_name[128];
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1,
                             wide_name, 128)) return 0;
    /* The runtime deliberately reads Windows paths with _wgetenv. Writing a
     * UTF-8 narrow environment value corrupts its wide copy on a GBK machine. */
    return _wputenv_s(wide_name, value) == 0;
}

static int mojin_standalone_prepare(int *argc, char ***argv) {
    if (*argc != 1) return 1;
    wchar_t directory[32768], probe[32768], settings[32768];
    DWORD n = GetModuleFileNameW(NULL, directory, 32768);
    if (!n || n >= 32768) return mojin_start_error(L"Cannot resolve the game folder.");
    wchar_t *slash = wcsrchr(directory, L'\\');
    if (!slash) return mojin_start_error(L"Invalid game folder.");
    *slash = 0;
    if (_wchdir(directory)) return mojin_start_error(L"Cannot open the game folder.");
    if (GetFileAttributesW(L"data\\mojin_image.bin") == INVALID_FILE_ATTRIBUTES ||
        GetFileAttributesW(L"data\\module-abi-init.txt") == INVALID_FILE_ATTRIBUTES)
        return mojin_start_error(L"Game data is missing. Restore the complete play folder.");
    /* OS-held lock: two sessions cannot write one save folder. A crash releases
     * it too; there is no stale lock for the player to remove. */
    HANDLE lock = CreateFileW(L".session.lock", GENERIC_READ | GENERIC_WRITE, 0, NULL,
        OPEN_ALWAYS, FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, NULL);
    if (lock == INVALID_HANDLE_VALUE)
        return mojin_start_error(L"The game is already running, or its folder is not writable.");
    if (!CreateDirectoryW(L"logs", NULL) && GetLastError() != ERROR_ALREADY_EXISTS)
        return mojin_start_error(L"Cannot create the game log folder.");
    SYSTEMTIME utc; GetSystemTime(&utc);
    char logbase[128], path[160];
    snprintf(logbase, sizeof(logbase), "logs/%04u%02u%02uT%02u%02u%02u-%lu",
        utc.wYear, utc.wMonth, utc.wDay, utc.wHour, utc.wMinute, utc.wSecond,
        (unsigned long)GetCurrentProcessId());
    snprintf(path, sizeof(path), "%s.log", logbase);
    if (!freopen(path, "w", stderr)) return mojin_start_error(L"Cannot write the game log.");
    snprintf(path, sizeof(path), "%s-output.log", logbase);
    if (!freopen(path, "w", stdout)) return mojin_start_error(L"Cannot write the game output log.");
    /* A double click uses settings.ini, not inherited diagnostic flags. Copy
     * names first because _putenv_s can relocate _environ. */
    char *keys[512]; unsigned count = 0;
    for (char **e = _environ; e && *e; e++) {
        if (strncmp(*e, "SR_", 3) && strncmp(*e, "PSP_", 4)) continue;
        if (count == 512) return mojin_start_error(L"Too many game environment variables.");
        char *eq = strchr(*e, '=');
        if (!eq) continue;
        keys[count] = _strdup(*e);
        if (!keys[count]) return mojin_start_error(L"Out of memory.");
        keys[count++][eq - *e] = 0;
    }
    for (unsigned i = 0; i < count; i++) { _putenv_s(keys[i], ""); free(keys[i]); }
    if (!GetFullPathNameW(L"data\\game", 32768, probe, NULL) ||
        !mojin_set_wide_env("SR_MOJIN_GAME_DATA", probe))
        return mojin_start_error(L"Cannot resolve game resources.");
    if (iso_init()) return mojin_start_error(L"游戏资源缺失或大小错误，请恢复完整运行目录中的 data/game。详细文件名见 logs。");
    GetFullPathNameW(L"saves", 32768, probe, NULL);
    if (!mojin_set_wide_env("SR_MEMSTICK", probe)) return mojin_start_error(L"Cannot set save folder.");
    GetFullPathNameW(L"userdata", 32768, probe, NULL);
    if (!mojin_set_wide_env("SR_USER_DATA_ROOT", probe)) return mojin_start_error(L"Cannot set cache folder.");
    GetFullPathNameW(L"data\\vfpu", 32768, probe, NULL);
    if (!mojin_set_wide_env("PSP_VFPU_TABLES", probe)) return mojin_start_error(L"Cannot set VFPU folder.");
    _putenv_s("SR_BOOT_PATH", "disc0:/PSP_GAME/SYSDIR/EBOOT.BIN");
    _putenv_s("SR_GAME_TITLE", "魔法禁书目录");
    _putenv_s("SR_HEADLESS", "0"); _putenv_s("SR_NOINPUT", "1");
    _putenv_s("SR_VIDEO", "vulkan"); _putenv_s("SR_GPU_GE", "1");
    _putenv_s("SR_AUDIO_BACKEND", "sdl");
    _putenv_s("SR_MOJIN_WINDOW_PUMP", "cooperative");
    _putenv_s("SR_MOJIN_CJK_FONT", "assets/fonts/ui/noto-sans-sc/NotoSansCJKsc-Regular.otf");
    _putenv_s("SR_DEBUG", "0"); _putenv_s("SR_DLGLOG", "1");
    snprintf(path, sizeof(path), "%s-execution.json", logbase);
    _putenv_s("SR_EXEC_SHARE_JSON", path);
    if (!GetFullPathNameW(L"settings.ini", 32768, settings, NULL))
        return mojin_start_error(L"Cannot resolve settings.ini.");
    unsigned scale = GetPrivateProfileIntW(L"Graphics", L"RenderScale", 4, settings);
    unsigned aa = GetPrivateProfileIntW(L"Graphics", L"SSAA", 2, settings);
    unsigned width = GetPrivateProfileIntW(L"Graphics", L"WindowWidth", 960, settings);
    unsigned height = GetPrivateProfileIntW(L"Graphics", L"WindowHeight", 544, settings);
    unsigned fps = GetPrivateProfileIntW(L"Graphics", L"FPS", 60, settings);
    if (fps != 60 && fps != 120) return mojin_start_error(L"Invalid Graphics FPS: choose 60 or 120.");
    snprintf(path, sizeof(path), "%u", fps); _putenv_s("SR_MOJIN_GAME_FPS", path);
    _putenv_s("SR_FPS_CAP", fps == 120 ? "120" : "60");
    if (scale < 1 || scale > 8 || (aa != 1 && aa != 2 && aa != 4) ||
        width < 480 || width > 3840 || height < 272 || height > 2176)
        return mojin_start_error(L"Invalid Graphics settings. RenderScale=1..8, SSAA=1/2/4; window=480x272..3840x2176.");
    snprintf(path, sizeof(path), "%u", scale); _putenv_s("SR_RESOLUTION_SCALE", path);
    snprintf(path, sizeof(path), "%ux%u", width, height); _putenv_s("SR_MOJIN_WINDOW_SIZE", path);
    char ace[256];
    snprintf(ace, sizeof(ace), "v1;tier=enhanced;af=0;text=off;readout=off;notice=off;wide=off;"
             "smooth=off;sas=off;tess=off;twin=off;ssaa=%u", aa);
    if (aa > 1) _putenv_s("SR_ACE", ace);
    unsigned fs = GetPrivateProfileIntW(L"Graphics", L"Fullscreen", 0, settings);
    _putenv_s("SR_FULLSCREEN", fs ? "1" : "0");
    char settings_utf8[32768];
    if (!WideCharToMultiByte(CP_UTF8,0,settings,-1,settings_utf8,sizeof(settings_utf8),NULL,NULL))
        return mojin_start_error(L"Cannot encode settings path.");
    MojinGraphicsOptions graphics = {(int)scale,(int)aa,(int)width,(int)height,fs?1:0,(int)fps};
    mojin_graphics_configure(settings_utf8,&graphics);
    fprintf(stderr, "MOJIN_STANDALONE version=0.1.3-dev pid=%lu render=%u ssaa=%u output_request=%ux%u fps=%u\n",
        (unsigned long)GetCurrentProcessId(), scale, aa, width, height, fps);
    static char *args[] = {"MoJin.exe", "--image", "data/mojin_image.bin", "0x08804000", "0x08804114",
                          "data/module-abi-init.txt", "none", "--sched", "--gui", NULL};
    *argc = 9; *argv = args;
    return 1;
}
#else
static int mojin_standalone_prepare(int *argc, char ***argv) {
    (void)argc; (void)argv;
    return 1; /* Portable diagnostic CLI unchanged; GUI packaging is Windows-first. */
}
#endif
