"""Keep the pinned upstream dispatch/registration support, remove CPU interpreter."""
import hashlib
import os
from pathlib import Path
import re

DEV = Path(__file__).resolve().parents[1]


def prepare():
    upstream = DEV / "third_party/nakagawa/src/rt/guest_interp.c"
    data = upstream.read_bytes()
    # Normalize checkout line endings before pinning this source slice.
    text = data.decode("utf-8").replace("\r\n", "\n")
    expected_raw = "4dd5c56946d1129c56dfae13baeb129f929d4967713270dd9bb578df4635caaa"
    # The current snapshot was checked out with LF; accepting CRLF is harmless only
    # when normalizing it reproduces that exact pinned content digest.
    if hashlib.sha256(data).hexdigest() != expected_raw and hashlib.sha256(text.encode()).hexdigest() != expected_raw:
        raise ValueError("guest_interp.c differs from the audited source; review the split again")
    marker = "static void set_fault(\n"
    assert text.count(marker) == 1
    support = text.split(marker)[0]
    for forbidden in ("static SrGuestInterpResult fetch_instruction(", "execute_noncontrol(",
                      "sr_guest_interp_run_internal(", "classify_control("):
        assert forbidden not in support
    target = DEV / "generated/runtime/aot_dispatch.c"
    target.parent.mkdir(parents=True, exist_ok=True)
    result = (support + "\n/* Project-local split: retain dispatch and module metadata only.\n"
              " * Source: Jstar269/Nakagawa-Recomp@2263985dd8882acbbf1a7313f3752979e7f88e2d\n"
              " * Interpreter fetch, decode and execute bodies are omitted. */\n"
              '#include "../../runtime/aot_guard.c"\n')
    if not target.exists() or target.read_text(encoding="utf-8") != result:
        target.write_text(result, encoding="utf-8", newline="\n")
    prepare_network()
    prepare_rtc()
    prepare_utility_diagnostics()
    prepare_display_diagnostics()
    prepare_media_diagnostics()
    prepare_mpeg_timestamp()
    prepare_script_handoff()
    prepare_window_pump()
    prepare_high_resolution()
    prepare_ge_capture()
    prepare_graphics_settings()
    prepare_standalone()
    prepare_asset_copy()
    return target


def prepare_network():
    upstream = DEV / "third_party/nakagawa/src/rt/hle_network.c"
    source = upstream.read_text(encoding="utf-8")
    expected = "ee8bc19bef106179687cc183ee15049598accdfa6641e0cdf68d1773d7e58218"
    if hashlib.sha256(source.encode()).hexdigest() != expected:
        raise ValueError("hle_network.c changed; review the lifecycle overlay again")
    replacements = {
        '#include "hle_internal.h"': '#include "hle_internal.h"\n#include "../../runtime/offline_adhoc.h"\n#include "../../runtime/offline_matching.h"',
        'void hle_net_reset(void) {': 'void hle_net_reset(void) {\n    mojin_adhoc_reset();\n    mojin_matching_reset();',
        'sr_hle_register_unsupported(0xe1d621d7u, "sceNetAdhocInit", 0x80010086u);':
        'sr_hle_register(0xe1d621d7u, "sceNetAdhocInit", h_NetAdhocInit);',
        'sr_hle_register_unsupported(0xa62c6f57u, "sceNetAdhocTerm", 0x80010086u);':
        'sr_hle_register(0xa62c6f57u, "sceNetAdhocTerm", h_NetAdhocTerm);',
        'sr_hle_register_unsupported(0x2a2a1e07u, "sceNetAdhocMatchingInit", 0x80010086u);':
        'sr_hle_register(0x2a2a1e07u, "sceNetAdhocMatchingInit", h_NetAdhocMatchingInit);',
        'sr_hle_register_unsupported(0x7945ecdau, "sceNetAdhocMatchingTerm", 0x80010086u);':
        'sr_hle_register(0x7945ecdau, "sceNetAdhocMatchingTerm", h_NetAdhocMatchingTerm);',
        'sr_hle_register_unsupported(0x9c5cfb7du, "sceNetAdhocMatchingGetPoolStat", 0x80010086u);':
        'sr_hle_register(0x9c5cfb7du, "sceNetAdhocMatchingGetPoolStat", h_NetAdhocMatchingGetPoolStat);',
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise ValueError(f"Network overlay anchor not unique: {old}")
        source = source.replace(old, new)
    target = DEV / "generated/runtime/hle_network.c"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_rtc():
    source = (DEV / "third_party/nakagawa/src/rt/hle_rtc.c").read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "db203cebf2ce973c05d5d0e79632ccc66798e73ccfeabef95b4b1d7addfd5296":
        raise ValueError("hle_rtc.c changed; review the TickAddTicks binding")
    anchor = "void hle_register_unregistered_import_rtc(void) {"
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + '\n    /* PPSSPP 4392fe67 sceRtc.cpp: both APIs add an a2/a3 64-bit count, modulo 2^64. */\n'
        '    sr_hle_register(0x44f45e05u, "sceRtcTickAddTicks", h_RtcTickAddMicroseconds);')
    target = DEV / "generated/runtime/hle_rtc.c"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_utility_diagnostics():
    source = (DEV / "third_party/nakagawa/src/rt/hle_utility.c").read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "03dc72846be08c5b854b387774d7a5ce08d5644431c04b8c2aa00ae81eb1986d":
        raise ValueError("hle_utility.c changed; review the message diagnostic")
    anchor = "static uint32_t msg_dialog_default_answer(uint32_t param) {"
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + '\n    char mojin_message[513] = {0};\n'
        '    guest_cstr(param + 0x3cu, mojin_message, sizeof(mojin_message));\n'
        '    fprintf(stderr, "MOJIN_DIALOG mode=%u error=0x%08x text=%s\\n",\n'
        '            MEM_R32(param + 0x34u), MEM_R32(param + 0x38u), mojin_message);\n')
    target = DEV / "generated/runtime/hle_utility.c"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_display_diagnostics():
    source = (DEV / "third_party/nakagawa/src/rt/hle_display.c").read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "5a25255ddc46dac85f76396133206c659de18532eaeda0dda11530702c915cbf":
        raise ValueError("hle_display.c changed; review display diagnostics")
    marker = "static uint32_t h_DisplaySetFrameBuf(CpuState *s) {"
    assert source.count(marker) == 1
    source = source.replace(marker, '#include "../../runtime/display_trace.h"\n' + marker)
    marker = "    if (sync > 1u)                           /* SCE_KERNEL_ERROR_INVALID_MODE */"
    assert source.count(marker) == 1
    source = source.replace(marker, "    mojin_trace_display_request(s, addr, stride, fmt, sync);\n" + marker)
    target = DEV / "generated/runtime/hle_display.c"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_media_diagnostics():
    source = (DEV / "third_party/nakagawa/src/rt/hle_mpeg.c").read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "fee9d93f5ea3da52dc957d8431181af8ecde5b829de1865d4292ae4fa5dec078":
        raise ValueError("hle_mpeg.c changed; review media diagnostics")
    marker = "static uint32_t h_MpegRingbufferAvailable(CpuState *s) { return mpeg_ringbuffer_available_size(A0); }"
    assert source.count(marker) == 1
    source = source.replace(marker, '#include "../../runtime/media_poll_trace.h"\n'
        'static uint32_t h_MpegRingbufferAvailable(CpuState *s) { '
        'uint32_t r = mpeg_ringbuffer_available_size(A0); '
        'mojin_media_poll_note(s, MOJIN_MEDIA_AVAILABLE, r); return r; }')
    marker = "static uint32_t h_MpegRingbufferPut(CpuState *s) { return mpeg_ringbuffer_put(s, A0, A1, A2); }"
    assert source.count(marker) == 1
    source = source.replace(marker, 'static uint32_t h_MpegRingbufferPut(CpuState *s) { '
        'uint32_t r = mpeg_ringbuffer_put(s, A0, A1, A2); '
        'mojin_media_poll_note(s, MOJIN_MEDIA_PUT, r); return r; }')
    marker = "static uint32_t h_MpegGetAvcAu(CpuState *s) {"
    assert source.count(marker) == 1
    source = source.replace(marker, '#include "../../runtime/media_trace.h"\n' + marker)
    for api, call, au in [
        ("GetAvcAu", "mpeg_get_avc_au(A0, A1, A2, A3)", "A2"),
        ("GetAtracAu", "mpeg_get_atrac_au(A0, A1, A2, A3)", "A2"),
        ("AvcDecode", "mpeg_avc_decode(A0, A1, A2, A3, stack_arg(s, 0))", "A1"),
        ("AtracDecode", "mpeg_atrac_decode(A0, A1, A2, A3)", "A1"),
    ]:
        marker = f"    uint32_t r = {call};"
        assert source.count(marker) == 1
        kind = {"GetAvcAu": "AVC_AU", "GetAtracAu": "ATRAC_AU", "AvcDecode": "AVC_DECODE", "AtracDecode": "ATRAC_DECODE"}[api]
        source = source.replace(marker, marker + f'\n    mojin_media_poll_note(s, MOJIN_MEDIA_{kind}, r);'
            f'\n    mojin_trace_media(s, "{api}", r, {au});')
    target = DEV / "generated/runtime/hle_mpeg.c"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_mpeg_timestamp():
    """Correct the common sceMpeg PSMF clock parser, not a scene-specific delay."""
    source = (DEV / "third_party/nakagawa/src/rt/mpeg.c").read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "5291e7a4773ef65c178932261fb3e8367af53d61759aee784e1c232cac0dadd9":
        raise ValueError("mpeg.c changed; review the six-byte timestamp fix")
    start = source.index("/* PSMF 6-byte timestamp")
    end = source.index("\n}\n", start) + 3
    replacement = '''/* Six-byte PSMF timestamp. Match PPSSPP@4392fe67 MediaEngine.h:40-42
 * and the runtime's existing psmf_be_timestamp. The previous five-byte read
 * made this ISO's 90000 audio origin become 351, while AVC PES PTS stayed 90000.
 * Preserve reference treatment of the reserved leading bits (shift 36).
 */
static int64_t mpeg_ts(uint32_t a) {
    return ((int64_t)MEM_R8(a) << 36) | ((int64_t)MEM_R8(a+1) << 32) |
           ((int64_t)MEM_R8(a+2) << 24) | ((int64_t)MEM_R8(a+3) << 16) |
           ((int64_t)MEM_R8(a+4) << 8) | (int64_t)MEM_R8(a+5);
}
'''
    source = source[:start] + replacement + source[end:]
    target = DEV / "generated/runtime/mpeg.c"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_script_handoff():
    upstream=DEV / "third_party/nakagawa/src/rt/hle_route.c"
    source=upstream.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest()!="05417cee3d016d169f62f1cf2bdccbd1f6ccddd3e590e62e3bbdb2c30d972576":
        raise ValueError("hle_route.c changed; review completed-script handoff")
    target=DEV / "generated/runtime/hle_route.c"
    def include(match):
        path=(upstream.parent/match.group(1)).resolve()
        return '#include "'+Path(os.path.relpath(path,target.parent)).as_posix()+'"' if path.is_file() else match.group(0)
    source=re.sub(r'^#include "([^"]+)"',include,source,flags=re.MULTILINE)
    anchor='        s_route_legacy_reported = 1;'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+'''
        /* Explicit diagnostic handoff only, after every segment (including the
         * final release) was consumed. Leave pending automation protected. */
        const char *handoff=getenv("SR_MOJIN_SCRIPT_HANDOFF");
        if (handoff && !strcmp(handoff,"1") && !s_input.current) {
#ifdef _WIN32
            int cleared=_putenv_s("SR_PADSCRIPT","")==0;
#else
            int cleared=unsetenv("SR_PADSCRIPT")==0;
#endif
            fprintf(stderr,"MOJIN_SCRIPT_HANDOFF completed=%d vcount=%u segments=%d current=%d\\n",
                    cleared,v,s_route_legacy_nseg,s_input.current);
        }
''')
    if not target.exists() or target.read_text(encoding="utf-8")!=source:
        target.write_text(source,encoding="utf-8",newline="\n")


def prepare_window_pump():
    upstream = DEV / "third_party/nakagawa/src/rt/gpu_sdl3vk/sdl3vk.c"
    source = upstream.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "af3deccf963ac197089e9dbe10b23ae958f2c2e4017f9cc0fc4d1bdfe3e024cf":
        raise ValueError("sdl3vk.c changed; review window pump integration")
    target = DEV / "generated/runtime/sdl3vk.c"
    # Keep upstream's relative includes attached to their owning directory.
    # System/core include-search names remain untouched. No dependency is copied.
    def include(match):
        path = (upstream.parent / match.group(1)).resolve()
        return '#include "' + Path(os.path.relpath(path, target.parent)).as_posix() + '"' if path.is_file() else match.group(0)
    source = re.sub(r'^#include "([^"]+)"', include, source, flags=re.MULTILINE)
    replacements = {
        '#define SDL3VK_APP_USER_MODEL_ID "Nakagawa.Recomp"':
        '#define SDL3VK_APP_USER_MODEL_ID "MoJin.Native"',
        '#define SDL3VK_APP_DESKTOP_ID "nakagawa-recomp"':
        '#define SDL3VK_APP_DESKTOP_ID "mojin-native"',
        '#define SDL3VK_APP_NAME "Nakagawa Recomp"':
        '#define SDL3VK_APP_NAME "魔法禁书目录"',
        'static SDL_Window      *s_win;':
        '#include "../../runtime/window_pump.h"\n#include "../../runtime/window_size.h"\n\nstatic SDL_Window      *s_win;',
        'SDL_PROP_WINDOW_CREATE_WIDTH_NUMBER, PSP_W * 2);':
        'SDL_PROP_WINDOW_CREATE_WIDTH_NUMBER, mojin_window_dimension(0));',
        'SDL_PROP_WINDOW_CREATE_HEIGHT_NUMBER, PSP_H * 2);':
        'SDL_PROP_WINDOW_CREATE_HEIGHT_NUMBER, mojin_window_dimension(1));',
        '            "sdl3vk: SDL_CreateWindow failed: %s\\n", SDL_GetError());':
        '            "sdl3vk: SDL_CreateWindow failed: %s\\n", SDL_GetError());\n'
        '    INIT_OK(mojin_pump_configure(s_win), "sdl3vk: project window pump initialization failed\\n");',
        '    while (SDL_PollEvent(&ev)) {':
        '    mojin_pump_cycle();\n    while (mojin_pump_next(&ev)) {',
        '    sr_coro_call_on_thread_stack(poll_input_on_this_stack, quit);':
        '#ifdef _WIN32\n    poll_input_on_this_stack(quit);\n#else\n'
        '    sr_coro_call_on_thread_stack(poll_input_on_this_stack, quit);\n#endif',
        'void sdl3vk_shutdown(void) {':
        'void sdl3vk_shutdown(void) {\n    mojin_pump_stop();',
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise ValueError(f"Window overlay anchor not unique: {old}")
        source = source.replace(old, new)
    anchor = "static void poll_input_on_this_stack(void *arg) {"
    assert source.count(anchor) == 1
    source = source.replace(anchor, '#include "../../runtime/settings_probe.h"\n' + anchor + '\n    mojin_settings_probe_events();')
    anchor = '    while (mojin_pump_next(&ev)) {'
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + '\n        mojin_settings_probe_received(&ev);')
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_high_resolution():
    from pipeline_catalog import emit
    emit()
    upstream = DEV / "third_party/nakagawa/src/rt/gpu_sdl3vk/ge_gpu.c"
    source = upstream.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "df8303e3ea83188cee4765848de2e42d69877be288c63be3a465a60d71120db5":
        raise ValueError("ge_gpu.c changed; review 8x render-size support")
    target = DEV / "generated/runtime/ge_gpu.c"
    anchor = "static VkPipeline pipe_create(const PipeKey *k, int rmw) {"
    assert source.count(anchor)==1
    source=source.replace(anchor,'#include "../../runtime/pipeline_trace.h"\n'+anchor)
    anchor = "    s_pcache_create_ns += SDL_GetTicksNS() - create_started;"
    assert source.count(anchor)==1
    source=source.replace(anchor,'''    const uint64_t mojin_pipeline_elapsed=SDL_GetTicksNS()-create_started;
    s_pcache_create_ns += mojin_pipeline_elapsed;
    mojin_pipeline_trace(k,rmw,r,mojin_pipeline_elapsed);''')
    anchor = '    if (perf_started) sr_perf_vulkan_pipeline(perf_started);'
    assert source.count(anchor)==1
    source=source.replace(anchor,'    if (perf_started && !mojin_pipeline_preparing) sr_perf_vulkan_pipeline(perf_started);')
    anchor = 'static VkPipeline pipe_get_rmw(const PipeKey *k, int zshader) {'
    end = source.index('\n}\n',source.index(anchor))+3
    source=source[:end]+'\n#include "../../runtime/pipeline_prepare.h"\n'+source[end:]
    anchor = '    ge_set_gpu_hooks(&k_hooks);'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+'\n    mojin_prepare_pipelines();')
    # Cache hits do not invoke ge.c's texture sampler, whose reads normally feed
    # the capture. Record the backing texture bytes before either cache path.
    source = '#include "../ge_capture.h"\n' + source
    anchor = "    uint32_t levels = mip.max_level + 1u;\n    uint64_t hash = tex_hash();"
    assert source.count(anchor) == 1
    source = source.replace(anchor, '''    uint32_t levels = mip.max_level + 1u;
    if (g_ge_capture_active) {
        /* Diagnostics only. VRAM retains the capture's eager preimage; RAM
         * must include textures already resident in the GPU cache. Use the
         * cache's existing source-span calculation, including mip padding. */
        ge_capture_note_memory(s_ge->tex_addr, tex_source_size());
        for (uint32_t i = 0; i < mip.max_level; i++)
            ge_capture_note_memory(mip.addr[i], mip_bytes[i]);
    }
    uint64_t hash = tex_hash();''')
    # The glyph module must share the renderer's maximum. Its temporary planes
    # and per-texel blocks are dynamically sized; the GPU tile is MAX_SCALE-sized.
    # Keep the static assertion in glyph_gpu.inc, not a suppression of it.
    glyph_dir = upstream.parent
    for filename, expected in {
        "glyph_recon.h": "efd45abf6ff93b6540741fc78f71dc00cd5fae9e32e5f874e55205aa3c61974b",
        "glyph_recon.c": "07eb278c396696ee4d17aa09d33e6b6a907fbe2202c3791679de3661dd964102",
    }.items():
        content = (glyph_dir / filename).read_text(encoding="utf-8")
        if hashlib.sha256(content.encode()).hexdigest() != expected:
            raise ValueError(f"{filename} changed; review scale-8 allocations and verification")
        if filename.endswith(".h"):
            assert content.count("#define NK_GLYPH_MAX_FACTOR 6") == 1
            content = content.replace("#define NK_GLYPH_MAX_FACTOR 6", "#define NK_GLYPH_MAX_FACTOR 8 /* Project: tested by test_high_resolution.py. */")
        output = target.parent / filename
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            output.write_text(content, encoding="utf-8", newline="\n")
    def include(match):
        if match.group(1) == "glyph_recon.h":
            return '#include "glyph_recon.h"'
        path = (upstream.parent / match.group(1)).resolve()
        return '#include "' + Path(os.path.relpath(path, target.parent)).as_posix() + '"' if path.is_file() else match.group(0)
    source = re.sub(r'^#include "([^"]+)"', include, source, flags=re.MULTILINE)
    anchor = "#define MAX_SCALE 4"
    assert source.count(anchor) == 1
    source = source.replace(anchor, "#define MAX_SCALE 8 /* Project: 3840x2176 visible, 4096x2176 stride. */")
    source += '''
/* Project settings: report the renderer's accepted allocation, not env requests. */
int mojin_ge_settings(int *scale, int *ssaa) {
    *scale = s_scale; *ssaa = s_ssaa;
    return s_ready;
}
'''
    anchor = "    VkPhysicalDeviceProperties props;\n    vkGetPhysicalDeviceProperties(s_pdev, &props);\n    /* The host depth buffer"
    assert source.count(anchor) == 1
    source = source.replace(anchor, "    VkPhysicalDeviceProperties props;\n    vkGetPhysicalDeviceProperties(s_pdev, &props);" + '''
    /* Refuse unsupported requests before allocating scaled render targets. This
     * is a conservative four-target estimate, not a promise about all scenes.
     * Texture allocations and later target failures retain upstream handling. */
    uint32_t mojin_limit = props.limits.maxImageDimension2D;
    const uint32_t mojin_limits[] = {props.limits.maxFramebufferWidth,
        props.limits.maxFramebufferHeight, props.limits.maxViewportDimensions[0],
        props.limits.maxViewportDimensions[1]};
    for (unsigned i = 0; i < 4; i++)
        if (mojin_limits[i] < mojin_limit) mojin_limit = mojin_limits[i];
    if (SCL_W > mojin_limit || SCL_H > mojin_limit ||
        ssaa_bytes(s_scale, 1, 4) > ssaa_budget()) {
        fprintf(stderr, "MOJIN_RENDER refused scale=%d: device dimensions or memory budget\\n", s_scale);
        return 0;
    }
    fprintf(stderr, "MOJIN_RENDER composition=%ux%u backing=%ux%u scale=%d\\n",
        (unsigned)(DRAW_W * s_scale), SCL_H, SCL_W, SCL_H, s_scale);
    /* The host depth buffer''')
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_graphics_settings():
    rt = DEV / "third_party/nakagawa/src/rt"
    for name, expected in {
        "gui.c": "f5bc8fde618c0280b3dbb9468653ce8515098c9894bbecb541a8ef1d811ecfc3",
        "overlay/overlay_quick.c": "1182cc1837c1d6f43857010ac8444002be6ba8be9b79f8f791af0450a3bb1752",
        "overlay/nk_overlay.c": "b75fc8b250840a9ef72d39cb12bdb4dce0b498cf298d2ecdf8c6bb7ef5b682c9",
        "overlay/overlay_host.c": "f0a8a65c8c1697cd3c2229e9e23a8dc5bb50c6651c53725768d2f84f88b7075e",
    }.items():
        upstream = rt / name
        source = upstream.read_text(encoding="utf-8")
        if hashlib.sha256(source.encode()).hexdigest() != expected:
            raise ValueError(f"{name} changed; review graphics settings integration")
        target = DEV / "generated/runtime" / upstream.name
        def include(match):
            path = (upstream.parent / match.group(1)).resolve()
            return '#include "' + Path(os.path.relpath(path, target.parent)).as_posix() + '"' if path.is_file() else match.group(0)
        source = re.sub(r'^#include "([^"]+)"', include, source, flags=re.MULTILINE)
        if name == "gui.c":
            source = '#include "../../runtime/graphics_settings.h"\n' + source
            anchor = "static void gui_pause_act(NkOverlayAction action) {"
            assert source.count(anchor) == 1
            source = source.replace(anchor, anchor + '''
    if (mojin_graphics_action((int)action.kind,action.value)) {
        s_pause_dirty = 1; return;
    }
''')
            anchor = "        model.fullscreen = pause_fullscreen_row(sdl3vk_fullscreen());"
            assert source.count(anchor) == 1
            source = source.replace(anchor, '''        int mojin_scale=1, mojin_ssaa=1;
        int mojin_ready=mojin_ge_settings(&mojin_scale,&mojin_ssaa);
        mojin_graphics_observe(mojin_ready,mojin_scale,mojin_ssaa,w,h);
''' + anchor)
            anchor = "        SDL_RenderPresent(s_pause_ren);\n        gui_pause_act(action);"
            assert source.count(anchor) == 1
            source = source.replace(anchor, '''        SDL_RenderPresent(s_pause_ren);
        static int mojin_settings_captured;
        const char *mojin_capture = getenv("SR_MOJIN_SETTINGS_CAPTURE");
        if (!mojin_settings_captured && mojin_capture && mojin_capture[0] &&
            nk_overlay_host_screen(s_pause_host) == NK_OVERLAY_SCREEN_SETTINGS) {
            mojin_settings_captured = SDL_SaveBMP(s_pause_surface,mojin_capture);
            const MojinGraphicsView *v=mojin_graphics_view();
            fprintf(stderr,"MOJIN_SETTINGS_CAPTURE saved=%d scene=%dx%d composition=%dx%d output=%dx%d ssaa=%d\\n",
                mojin_settings_captured,v->scene_width,v->scene_height,v->composition_width,v->composition_height,
                v->output_width,v->output_height,v->active_ssaa);
        }
        gui_pause_act(action);''')
        elif name == "overlay/overlay_host.c":
            anchor = "    host->viewport.ui_scale_pct = 0;"
            assert source.count(anchor) == 1
            source = source.replace(anchor, '''    /* Fit the complete settings page at high desktop DPI. The shared scale
     * calculation also maps pointer coordinates to this same logical space. */
    host->viewport.min_logical_w = host->state.screen == NK_OVERLAY_SCREEN_SETTINGS ? 960.0f : 0.0f;
    host->viewport.min_logical_h = host->state.screen == NK_OVERLAY_SCREEN_SETTINGS ? 544.0f : 0.0f;
''' + anchor)
            source = source.replace("    const char *library_paths[2];", "    const char *library_paths[3];")
            anchor = "    ttf = nk_ui_ttf_create(library_count ? library_paths : NULL, library_count);"
            assert source.count(anchor) == 1
            source = source.replace(anchor, '''    const char *mojin_ttf = getenv("SR_MOJIN_TTF_LIBRARY");
    if (mojin_ttf && mojin_ttf[0]) library_paths[library_count++] = mojin_ttf;
''' + anchor)
            anchor = "        bool added = false;\n        size_t r;"
            assert source.count(anchor) == 1
            source = source.replace(anchor, '''        bool added = false;
        const char *mojin_cjk = getenv("SR_MOJIN_CJK_FONT");
        if (font == NK_UI_FONT_CJK && mojin_cjk && mojin_cjk[0])
            added = file_exists(mojin_cjk) && nk_ui_ttf_add_font(ttf,font,mojin_cjk);
        size_t r;''')
        elif name == "overlay/nk_overlay.c":
            anchor = ": NK_OVERLAY_SCREEN_MENU;"
            assert source.count(anchor) == 1
            source = source.replace(anchor, ": NK_OVERLAY_SCREEN_SETTINGS;")
        else:
            source = source[:source.index("/* The segmented control:")]
            source = source.replace("#define QUICK_ROW_HEIGHT_COMPACT 48.0f", "#define QUICK_ROW_HEIGHT_COMPACT 40.0f")
            source += '#include "../../runtime/graphics_settings_page.h"\n'
        if not target.exists() or target.read_text(encoding="utf-8") != source:
            target.write_text(source,encoding="utf-8",newline="\n")


def prepare_standalone():
    upstream = DEV / "third_party/nakagawa/src/rt/driver.c"
    source = upstream.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "221ebf14098ab8a60a1ea6f2817dbe19ded80482e201437997947a31134fd881":
        raise ValueError("driver.c changed; review standalone startup")
    target = DEV / "generated/runtime/driver.c"
    def include(match):
        path = (upstream.parent / match.group(1)).resolve()
        return '#include "' + Path(os.path.relpath(path, target.parent)).as_posix() + '"' if path.is_file() else match.group(0)
    source = re.sub(r'^#include "([^"]+)"', include, source, flags=re.MULTILINE)
    anchor = "#ifdef SR_SELFTEST_ONLY\nint driver_main(int argc, char **argv) {"
    assert source.count(anchor) == 1
    source = source.replace(anchor, '#include "../../runtime/standalone.h"\n\n' + anchor)
    anchor = "    uint32_t entry;\n    const char *ref_trace, *out;"
    assert source.count(anchor) == 1
    source = source.replace(anchor, "    if (!mojin_standalone_prepare(&argc, &argv)) return 2;\n" + anchor)
    anchor = '        sr_window_title_format(getenv("SR_GAME_TITLE"), caption, sizeof(caption));'
    assert source.count(anchor) == 1
    source = source.replace(anchor,
        '        if (!sr_window_title_sanitize(getenv("SR_GAME_TITLE"), caption, sizeof(caption)))\n'
        '            snprintf(caption, sizeof(caption), "%s", "魔法禁书目录");')
    anchor = '        gui_init(caption);'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+'''
        if(mojin_preparation_stop_reason()) {
            int reason=mojin_preparation_stop_reason();
            gui_shutdown();
            fprintf(stderr,"MOJIN_PREPARATION stopped_before_guest reason=%d\\n",reason);
            return driver_run_end(reason==1?0:2,"stopped during graphics preparation");
        }''')
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_ge_capture():
    upstream = DEV / "third_party/nakagawa/src/rt/ge_capture.c"
    source = upstream.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "cfc12958a99247352986f7efdff61eddcb82fbb562facfe7305d315c3fc938cf":
        raise ValueError("ge_capture.c changed; review streamed-memory capture")
    changes = {
        "int g_ge_capture_active;":
        "int g_ge_capture_active;\nstatic int s_mojin_capture_refused;\nstatic uint32_t s_mojin_refused_frame;",
        "    if (!path || !path[0] || !state || !zbuf || !g_mem || s_capture.active ||":
        "    if ((s_mojin_capture_refused && frame == s_mojin_refused_frame) ||\n"
        "        !path || !path[0] || !state || !zbuf || !g_mem || s_capture.active ||",
        "    uint8_t *seen;\n    uint32_t page_cap;":
        "    uint32_t *seen; /* page slot + 1, zero means absent */\n    uint8_t *observed;\n    uint64_t late_bytes;\n    uint32_t page_cap;",
        "    free(s_capture.seen);": "    free(s_capture.seen);\n    free(s_capture.observed);",
        "    s_capture.seen = (uint8_t *)calloc(GE_CAPTURE_MAX_PAGES, 1);":
        "    s_capture.seen = (uint32_t *)calloc(GE_CAPTURE_MAX_PAGES, sizeof(uint32_t));\n"
        "    s_capture.observed = (uint8_t *)calloc(GE_CAPTURE_ARENA_SIZE / 8u, 1);",
        "    if (!f->initial_zbuf || !f->initial_vram || !s_capture.seen) {":
        "    if (!f->initial_zbuf || !f->initial_vram || !s_capture.seen || !s_capture.observed) {",
        "    if (ok) {\n        fprintf(stderr, \"GE_CAPTURE: wrote":
        "    if (ok) {\n        fprintf(stderr, \"MOJIN_GE_CAPTURE late_unread_bytes=%llu\\n\", (unsigned long long)s_capture.late_bytes);\n"
        "        fprintf(stderr, \"GE_CAPTURE: wrote",
    }
    for old, new in changes.items():
        if source.count(old) != 1:
            raise ValueError(f"Capture overlay anchor not unique: {old}")
        source = source.replace(old, new)
    start = source.index("void ge_capture_note_memory(uint32_t addr, uint32_t bytes) {")
    end = source.index("\nint ge_capture_end(", start)
    source = source[:start] + '#include "../../runtime/capture_stream.h"\n' + source[end:]
    target = DEV / "generated/runtime/ge_capture.c"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


def prepare_asset_copy():
    source = (DEV / "third_party/nakagawa/tools/copy_build_assets.ps1").read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != "4d25b10c47b288ea9c1d4eeea87e984d445c7a27ae6d388d166450bfb26959d3":
        raise ValueError("copy_build_assets.ps1 changed; review copy verification")
    marker = "New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null"
    assert source.count(marker) == 1
    source = source.replace(marker, "$ErrorActionPreference = 'Stop'\n" + marker)
    marker = "$copiedSdl = $false\nif ($Sdl3DllPath -and (Test-Path $Sdl3DllPath)) {"
    assert source.count(marker) == 1
    source = source.replace(marker, '''function Get-MojinSha256([string]$filePath) {
    $stream = [System.IO.File]::OpenRead($filePath)
    $digest = [System.Security.Cryptography.SHA256]::Create()
    try { return [System.BitConverter]::ToString($digest.ComputeHash($stream)).Replace('-', '') }
    finally { $digest.Dispose(); $stream.Dispose() }
}
$copiedSdl = $false
$existingSdl = Join-Path $BuildDir 'SDL3.dll'
if ($Sdl3DllPath -and (Test-Path -LiteralPath $Sdl3DllPath) -and (Test-Path -LiteralPath $existingSdl)) {
    $sourceSdlHash = Get-MojinSha256 $Sdl3DllPath
    $existingSdlHash = Get-MojinSha256 $existingSdl
    $copiedSdl = $sourceSdlHash -eq $existingSdlHash
    if ($copiedSdl) { Write-Output "Verified existing SDL3.dll: $existingSdlHash" }
}
if (-not $copiedSdl -and $Sdl3DllPath -and (Test-Path $Sdl3DllPath)) {''')
    target = DEV / "generated/runtime/copy_build_assets.ps1"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    print(prepare())
