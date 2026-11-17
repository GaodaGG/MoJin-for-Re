"""Bounded startup probe with private saves/output and ownership of its own process only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

# Also support the pinned embeddable Python, whose ._pth excludes this folder.
sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"


def savedata_inventory(root):
    """Hash only regular files; never follow a test folder's link or junction."""
    rows = {}
    if not root.exists():
        return rows
    for directory, dirs, files in os.walk(root, followlinks=False):
        current = Path(directory)
        for path in [current, *(current / name for name in dirs + files)]:
            if path.is_symlink() or path.is_junction():
                raise ValueError(f"Savedata contains a link or junction: {path}")
        for name in files:
            path = current / name
            data = path.read_bytes()
            rows[path.relative_to(root).as_posix()] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return rows


def clone_savedata(source_run, destination):
    """Copy a completed private probe's saves; never run against the original."""
    source = source_run / "memstick/PSP/SAVEDATA"
    for path in (source_run / "memstick", source_run / "memstick/PSP", source):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Savedata source contains a link or junction: {path}")
    before = savedata_inventory(source)
    if not before:
        raise ValueError("The selected completed probe has no savedata files")
    for name in before:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write((source / name).read_bytes())
    if savedata_inventory(source) != before or savedata_inventory(destination) != before:
        raise ValueError("Savedata changed while copying; the game was not started")
    return dict(source_run=source_run.relative_to(ROOT).as_posix(),
                source_run_sha256=hashlib.sha256((source_run / "run.json").read_bytes()).hexdigest(), files=before)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--until-closed", action="store_true", help="Visible manual test: wait until the user closes the game; no time limit")
    parser.add_argument("--exe", default="mojin.exe", help="Executable filename under generated/baseline")
    parser.add_argument('--game-data', type=Path, help='Loose resource root for the ISO-independent candidate; clears PSP_ISO')
    parser.add_argument('--deny-iso', action='store_true', help='Hold original ISO read-only with share=0 throughout this private probe')
    parser.add_argument('--runtime-package', type=Path, help='Use a private complete package and only system PATH; diagnostics/saves still go to a new private run')
    renderer = parser.add_mutually_exclusive_group()
    renderer.add_argument("--offscreen", action="store_true", help="Enable the runtime's offscreen framebuffer sink; not Vulkan/window validation")
    renderer.add_argument("--vulkan-hidden", action="store_true", help="Use the actual Vulkan presenter in a hidden window; no focus/input capture")
    renderer.add_argument("--vulkan-window", action="store_true", help="Visible native test window for actual keyboard/controller checks")
    parser.add_argument("--capture-at", type=int, help="Start capture at/after this vblank; the final captured frame is retained (use --presented-frames to stop)")
    parser.add_argument("--capture-window", help="Keep distinct presented snapshots in a bounded vblank range, e.g. 6000:12000")
    parser.add_argument("--capture-every", type=int, default=300, help="Minimum vblank spacing inside --capture-window (default 300)")
    parser.add_argument("--presented-frames", type=int, help="Stop after this many actual Vulkan presents (authentic mode only; diagnostic budget)")
    parser.add_argument("--display-trace", action="store_true", help="Log display-state changes with PC/RA, without changing behavior")
    parser.add_argument("--media-trace", action="store_true", help="Log movie decode and file I/O to locate resource/lifecycle failures")
    parser.add_argument("--auto-start", action="store_true", help="Explicit experiment: enable upstream's periodic synthetic START (off by default)")
    parser.add_argument("--input-script", type=Path, help="Explicit project-local controller script, copied and hashed into the run")
    parser.add_argument("--script-handoff", action="store_true", help="Release the automation marker only after all script inputs and their releases were consumed")
    parser.add_argument("--audio", action="store_true", help="Enable SDL device sound; bounded probes also record this runtime's mixed output")
    parser.add_argument("--record-audio", action="store_true", help="Also record mixed sound in an unbounded manual test; otherwise --until-closed does not write a WAV")
    parser.add_argument("--savedata-from-run", type=Path, help="Copy savedata from a completed project probe into this new run; source stays untouched")
    parser.add_argument("--save-trace", action="store_true", help="Record utility savedata operations and results")
    parser.add_argument("--window-pump", choices=["legacy", "cooperative"], default="legacy", help="Experimental Windows modal-loop scheduling; requires the window-pump candidate")
    parser.add_argument("--render-scale", type=int, choices=[1, 2, 3, 4, 6, 8], default=1, help="Actual GPU render scale; 6/8 require the high-resolution candidate")
    parser.add_argument("--window-size", choices=["960x544", "1280x720", "1920x1080", "2560x1440", "3840x2160"], default="960x544", help="Requested window output; independent of scene resolution")
    parser.add_argument("--perf", action="store_true", help="Write per-new-frame cadence and CPU/GPU/storage/synchronization telemetry")
    parser.add_argument("--profile", action="store_true", help="Bounded guest-PC/function and runtime-phase attribution; diagnostic overhead, not an acceptance benchmark")
    parser.add_argument("--ge-profile", action="store_true", help="Read-only graphics phase snapshots at v7600..8800; diagnostic overhead, requires loop trace")
    parser.add_argument("--readback-full", action="store_true", help="Diagnostic full-image GPU readback reference; preserves the same guest samples")
    parser.add_argument("--loop-trace", action="store_true", help="Observe pinned main-loop phases without changing game timing; bounded diagnostic CSV")
    parser.add_argument("--experimental-update-rate", type=int, choices=[90,120], help="DEVELOPMENT ONLY: bounded common-frame wait experiment at v7400:9000; requires loop trace and training-entry.pad")
    parser.add_argument('--experimental-input-peek', action='store_true', help='DEVELOPMENT ONLY: pair bounded update-rate experiment with a single nonblocking controller-read callsite')
    parser.add_argument('--experimental-step-carry', action='store_true', help='DEVELOPMENT ONLY: preserve fractional time-step remainder in the two static arithmetic sites; requires update rate and input Peek')
    parser.add_argument('--game-fps', type=int, choices=[60,120], default=60, help='Persisted battle FPS choice; normal PSP clocks outside the qualified battle scene')
    parser.add_argument("--media-poll-trace", action="store_true", help="Count MPEG imports per vblank, bounded to the first 4096 vblanks; diagnostic only")
    parser.add_argument("--pipeline-trace", action="store_true", help="Record exact native GPU pipeline keys and creation times in this private run")
    parser.add_argument("--prepare", choices=['on','off'], default='on', help="Move known pipeline creation before guest start")
    parser.add_argument("--prepare-limit", type=int, choices=range(10), help="Diagnostic partial catalog, to verify normal unseen-state fallback")
    parser.add_argument("--prepare-capture", action='store_true', help="Capture the first/last preparation progress image")
    parser.add_argument("--prepare-cancel-at", type=int, choices=range(10), help="Push own-process SDL_QUIT during preparation; no guest or desktop input")
    parser.add_argument("--ge-capture", type=int, help="Capture this GE frame's commands/resources for isolated renderer diagnosis")
    parser.add_argument("--ssaa", type=int, choices=[1, 2, 4], default=1, help="Experimental supersampling factor per axis, resolved back to render scale")
    parser.add_argument("--settings-check", action="store_true", help="Explicit own-process SDL Esc/capture/quit check, no desktop input")
    parser.add_argument("--settings-save", action="store_true", help="Own-process UI navigation/save/resume check; requires scale4/SSAA2/960x544")
    parser.add_argument("--settings-delay", type=int, default=0, help="Delay the explicit settings check by 0..260 seconds, e.g. until battle")
    args = parser.parse_args()
    if args.deny_iso and not (args.game_data or args.runtime_package):
        parser.error('--deny-iso requires --game-data')
    if args.experimental_input_peek and not args.experimental_update_rate:
        parser.error('--experimental-input-peek requires --experimental-update-rate')
    if args.experimental_step_carry and not (args.experimental_update_rate and args.experimental_input_peek):
        parser.error('--experimental-step-carry requires --experimental-update-rate and --experimental-input-peek')
    if args.script_handoff and not args.input_script:
        parser.error("--script-handoff requires --input-script")
    if args.settings_save:
        args.settings_check=True
        if (args.render_scale,args.ssaa,args.window_size)!=(4,2,'960x544'):
            parser.error("--settings-save starts from --render-scale 4 --ssaa 2 --window-size 960x544")
    if not 0 <= args.settings_delay <= 260 or (args.settings_delay and not args.settings_check):
        parser.error("--settings-delay requires a settings check and must be 0..260")
    if args.settings_check and (not args.vulkan_window or args.seconds < 20+args.settings_delay or args.until_closed):
        parser.error("Settings checks require --vulkan-window and a bounded budget of delay+20 seconds")
    if not re.fullmatch(r"mojin(?:-[A-Za-z0-9_-]+)?\.exe", args.exe):
        parser.error("--exe must name a mojin*.exe file without a path")
    if args.seconds <= 0 or args.seconds > 300:
        parser.error("--seconds must be between 1 and 300")
    if args.ge_capture is not None and not 1 <= args.ge_capture <= 0xffffffff:
        parser.error("--ge-capture must be a positive 32-bit GE frame number")
    if args.until_closed and not args.vulkan_window:
        parser.error("--until-closed requires a visible --vulkan-window")
    if args.record_audio and not args.audio:
        parser.error("--record-audio requires --audio")
    if (args.render_scale > 1 or args.ssaa > 1 or args.window_pump != "legacy") and not (args.vulkan_window or args.vulkan_hidden):
        parser.error("Rendering/window-pump experiments require the Vulkan presenter")
    if args.capture_at is not None and (not (args.offscreen or args.vulkan_hidden or args.vulkan_window) or args.capture_at < 1):
        parser.error("--capture-at requires a presenter and a positive vblank")
    capture_window = None
    if args.capture_window:
        match = re.fullmatch(r"([0-9]+):([0-9]+)", args.capture_window)
        if not match or args.capture_at is not None or not (args.offscreen or args.vulkan_hidden or args.vulkan_window):
            parser.error("--capture-window requires LO:HI, a presenter, and no --capture-at")
        lo, hi = map(int, match.groups())
        if not (1 <= lo <= hi <= 0xffffffff) or args.capture_every < 1:
            parser.error("Invalid capture window or cadence")
        if (hi - lo) // args.capture_every + 1 > 256:
            parser.error("Capture window is limited to 256 snapshots; increase --capture-every")
        capture_window = (lo, hi)
    if args.presented_frames is not None and (not (args.vulkan_hidden or args.vulkan_window) or args.presented_frames < 1):
        parser.error("--presented-frames requires a Vulkan presenter and a positive frame count")
    if args.presented_frames is not None and args.ssaa > 1:
        parser.error("The upstream frame-budget checkpoint rejects enhanced/SSAA runs; use --until-closed instead")
    if args.input_script is not None:
        args.input_script = args.input_script.resolve()
        if not args.input_script.is_relative_to(ROOT) or not args.input_script.is_file():
            parser.error("--input-script must be an existing file within this project")
    if args.auto_start and args.input_script:
        parser.error("Use either an explicit script or automatic START, not both")
    if args.savedata_from_run:
        original = args.savedata_from_run.absolute()
        if original.is_symlink() or original.is_junction():
            parser.error("--savedata-from-run must not be a link or junction")
        args.savedata_from_run = original.resolve()
        if not args.savedata_from_run.is_relative_to((DEV / "tests/runs").resolve()) or not (args.savedata_from_run / "run.json").is_file():
            parser.error("--savedata-from-run must be a completed project probe with run.json")
    exe = DEV / "generated/baseline" / args.exe
    image = DEV / "generated/baseline/mojin_image.bin"
    packaged_build = None
    if args.runtime_package:
        args.runtime_package = args.runtime_package.resolve()
        if not any(args.runtime_package.is_relative_to(DEV / p) for p in ('releases', 'tests/standalone')):
            parser.error('--runtime-package must be a private project package')
        release = json.loads((args.runtime_package / 'release-manifest.json').read_text(encoding='utf-8'))
        assert release['iso_external'] is False
        packaged_build = release['build']
        exe = args.runtime_package / 'MoJin.exe'
        image = args.runtime_package / 'data/mojin_image.bin'
        args.game_data = args.runtime_package / 'data/game'
    from program_abi import load_image as load_program_abi
    metadata = load_program_abi(image)
    run = DEV / "tests/runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run.mkdir(parents=True)
    (run/'runtime-abi.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    for name in ("memstick", "user", "data"):
        (run / name).mkdir()
    restored_save = clone_savedata(args.savedata_from_run, run / "memstick/PSP/SAVEDATA") if args.savedata_from_run else None
    # This is an ABI initialization record, NOT a claimed emulator/hardware trace.
    init = run / "module-abi-init.txt"
    init.write_text(f"# Module-info GP from the pinned ELF; no observed trace.\n# init r28=0x{metadata['module']['gp']:08x}\n", encoding="ascii")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SR_", "PSP_"))}
    env["PATH"] = str(DEV / "toolchain/msys64/ucrt64/bin") + os.pathsep + env["PATH"]
    env.update(PSP_ISO=str(ROOT / "魔法禁书目录.iso"), SR_MEMSTICK=str(run / "memstick"),
               SR_USER_DATA_ROOT=str(run / "user"),
               PSP_VFPU_TABLES=str(DEV / "third_party/nakagawa/assets/vfpu"),
               SR_BOOT_PATH="disc0:/PSP_GAME/SYSDIR/EBOOT.BIN", SR_HEADLESS="1",
               SR_EXEC_SHARE_JSON=str(run / "execution-share.json"), SR_GAME_TITLE="MoJin diagnostic")
    env["SR_MISS_SEEDS"] = str(run / "dispatch-misses.txt")
    if args.game_data:
        from disc_data import verify
        args.game_data = args.game_data.resolve()
        verify(args.game_data)
        env.pop('PSP_ISO', None)
        env['SR_MOJIN_GAME_DATA'] = str(args.game_data)
    env["SR_MOJIN_WINDOW_PUMP"] = args.window_pump
    env["SR_RESOLUTION_SCALE"] = str(args.render_scale)
    env["SR_MOJIN_WINDOW_SIZE"] = args.window_size
    env["SR_UI_ROOT"] = str(DEV / "third_party/nakagawa")
    env["SR_MOJIN_CJK_FONT"] = str(DEV / "assets/fonts/ui/noto-sans-sc/NotoSansCJKsc-Regular.otf")
    env["SR_MOJIN_TTF_LIBRARY"] = str(DEV / "toolchain/msys64/ucrt64/bin/SDL3_ttf.dll")
    if args.runtime_package:
        env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        env['PSP_VFPU_TABLES'] = str(args.runtime_package / 'data/vfpu')
        env['SR_UI_ROOT'] = str(args.runtime_package)
        env['SR_MOJIN_CJK_FONT'] = str(args.runtime_package / 'assets/fonts/ui/noto-sans-sc/NotoSansCJKsc-Regular.otf')
        env['SR_MOJIN_TTF_LIBRARY'] = str(args.runtime_package / 'SDL3_ttf.dll')
    env["SR_MOJIN_SETTINGS_FILE"] = str(run / "settings.ini")
    env["SR_MOJIN_SETTINGS_SSAA"] = str(args.ssaa)
    if args.script_handoff:
        env["SR_MOJIN_SCRIPT_HANDOFF"]="1"
    width, height = args.window_size.split("x")
    (run / "settings.ini").write_text(f"[Graphics]\nRenderScale={args.render_scale}\nSSAA={args.ssaa}\nWindowWidth={width}\nWindowHeight={height}\nFullscreen=0\n",encoding="ascii")
    if args.settings_check:
        env.update(SR_MOJIN_SETTINGS_PROBE="save" if args.settings_save else "1",
                   SR_MOJIN_SETTINGS_DELAY_MS=str(args.settings_delay*1000),
                   SR_MOJIN_SETTINGS_CAPTURE=str(run / "settings.bmp"))
    if args.perf:
        env.update(SR_PERF_FRAMES=str(run / "frames.csv"), SR_PERF_CSV=str(run / "perf.csv"),
                   SR_PERF_JSON=str(run / "perf.json"), SR_GPU_TIMESTAMPS="1")
    if args.profile:
        env.update(SR_PROFILE='1',SR_PCSAMPLE='1',SR_PERF='1')
    if args.ge_profile:
        if not args.loop_trace:
            parser.error('--ge-profile requires --loop-trace')
        env.update(SR_GPU_CPU_PROFILE='1',SR_GE_CPU_PROFILE='1',SR_GE_PRIM_PROFILE='1')
    if args.readback_full:
        env['SR_GPU_READBACK_FULL']='1'
    if args.loop_trace:
        env['SR_MOJIN_LOOP_TRACE'] = str(run / 'loop.csv')
    if args.game_fps == 120:
        if args.experimental_update_rate:
            parser.error('Choose game-fps or the bounded experiment, not both')
        env['SR_MOJIN_GAME_FPS'] = '120'
        env['SR_FPS_CAP'] = '120'
    if args.experimental_update_rate:
        routes = {(DEV / 'tests' / name).resolve() for name in ('training-entry.pad', 'training-motion.pad')}
        if not args.loop_trace or not args.input_script or args.input_script.resolve() not in routes:
            parser.error('The update-rate experiment requires --loop-trace and an inspected training route')
        env['SR_MOJIN_EXPERIMENTAL_UPDATE_RATE'] = str(args.experimental_update_rate)
        env['SR_FPS_CAP'] = str(args.experimental_update_rate)
        if args.experimental_input_peek:
            env['SR_MOJIN_EXPERIMENTAL_INPUT_PEEK'] = '1'
        if args.experimental_step_carry:
            env['SR_MOJIN_EXPERIMENTAL_STEP_CARRY'] = '1'
    if args.media_poll_trace:
        env['SR_MOJIN_MEDIA_POLL_TRACE']=str(run/'media-polls.csv')
    if args.pipeline_trace:
        env["SR_MOJIN_PIPELINE_TRACE"]=str(run/'pipelines.jsonl')
    env['SR_MOJIN_PREPARE']='1' if args.prepare=='on' else '0'
    if args.prepare_limit is not None:
        env['SR_MOJIN_PREP_LIMIT']=str(args.prepare_limit)
    if args.prepare_capture:
        env['SR_MOJIN_PREP_CAPTURE']=str(run/'preparation')
    if args.prepare_cancel_at is not None:
        env['SR_MOJIN_PREP_CANCEL_AT']=str(args.prepare_cancel_at)
    if args.ge_capture is not None:
        env.update(SR_GE_CAPTURE_FRAME=str(args.ge_capture),
                   SR_GE_CAPTURE_PATH=str(run / "frame.ngef"), SR_GE_CAPTURE_MIN_PRIMS="1")
    if args.ssaa > 1:
        env["SR_ACE"] = ("v1;tier=enhanced;af=0;text=off;readout=off;notice=off;wide=off;"
                         f"smooth=off;sas=off;tess=off;twin=off;ssaa={args.ssaa}")
    # Upstream headless mode otherwise presses START every 240 vblanks. A neutral
    # baseline must not silently skip movies or menus. Preserve opt-in only for
    # reproducing the earlier diagnostic route; it is recorded in the manifest.
    if not args.auto_start:
        env["SR_NOINPUT"] = "1"
    command = [str(exe), "--image", str(image), "0x08804000", hex(metadata["entry_point"]),
               str(init), "none", "--sched"]
    if args.offscreen:
        env["SR_VIDEO"] = "offscreen"
        command.append("--gui")
    if args.vulkan_hidden:
        env.update(SR_VIDEO="vulkan", SR_GPU_GE="1", SR_WINDOW_HIDDEN="1")
        command.append("--gui")
    if args.vulkan_window:
        env.update(SR_VIDEO="vulkan", SR_GPU_GE="1", SR_HEADLESS="0", SR_INLOG="1")
        command.append("--gui")
    if args.presented_frames is not None:
        env["SR_HEADLESS_ACCEPT_PRESENTED_FRAMES"] = str(args.presented_frames)
    if args.display_trace:
        env["SR_MOJIN_DISPLAY_TRACE"] = "1"
    if args.media_trace:
        env.update(SR_MPEGLOG="1", SR_IOLOG="1")
    if args.save_trace:
        env["SR_DLGLOG"] = "1"
    if args.input_script:
        shutil.copyfile(args.input_script, run / "input.pad")
        env.update(SR_PADSCRIPT=str(run / "input.pad"), SR_INLOG="1")
    if args.audio:
        env.update(SR_AUDIO_BACKEND="sdl", SR_AUDIOSTAT="1")
        if not args.until_closed or args.record_audio:
            env["SR_AUDIODUMP"] = str(run / "audio.wav")
    if args.capture_at is not None:
        env["SR_FBDUMP"] = str(args.capture_at)
    if capture_window:
        env.update(SR_FBSNAP=str(args.capture_every), SR_FBSNAP_WINDOWS=f"{capture_window[0]}-{capture_window[1]}")
    manifest = dict(command=command, executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                    probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                    environment={k: v for k, v in env.items() if k.startswith(("SR_", "PSP_"))},
                    purpose="Bounded native-program diagnosis; exact renderer, input and sound flags are recorded. No full-game acceptance.")
    if args.until_closed:
        manifest["purpose"] = "Visible manual diagnostic; user closes the game. No full-game acceptance."
    manifest["time_limit_seconds"] = None if args.until_closed else args.seconds
    build_manifest = exe.with_suffix(".build.json")
    if build_manifest.is_file() or packaged_build:
        build_record = packaged_build or json.loads(build_manifest.read_text(encoding="utf-8"))
        if (build_record["executable_sha256"] != manifest["executable_sha256"] or
                build_record["image_sha256"] != manifest["image_sha256"]):
            raise SystemExit("Build manifest does not match the selected executable/image")
        (run / 'build.json').write_text(json.dumps(build_record,indent=2)+'\n',encoding='utf-8')
        manifest["build_manifest_sha256"] = hashlib.sha256((run / 'build.json').read_bytes()).hexdigest()
    if args.runtime_package:
        manifest['runtime_package'] = str(args.runtime_package)
        manifest['runtime_path'] = env['PATH']
        manifest['path_has_toolchain'] = False
    if args.input_script:
        manifest["input_script_sha256"] = hashlib.sha256((run / "input.pad").read_bytes()).hexdigest()
    if restored_save:
        manifest["savedata_restored"] = restored_save
    start = time.monotonic()
    release_iso = None
    if args.deny_iso:
        from iso_unavailable import hold_iso_unavailable
        manifest['iso_unavailable'], release_iso = hold_iso_unavailable()
    with (run / "stdout.log").open("w", encoding="utf-8") as stdout, (run / "stderr.log").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=run, env=env, stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        manifest["pid"] = process.pid
        # A live record allows subsequent monitoring to identify this exact owned
        # process without enumerating or touching unrelated applications.
        (run / "started.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            manifest["exit_code"] = process.wait(timeout=None if args.until_closed else args.seconds)
            manifest["timed_out"] = False
        except subprocess.TimeoutExpired:
            process.kill()  # Only the process created above, never a process-name search.
            manifest["exit_code"] = process.wait()
            manifest["timed_out"] = True
    manifest["elapsed_seconds"] = time.monotonic() - start
    if release_iso: release_iso()
    stderr_text = (run / "stderr.log").read_text(encoding="utf-8", errors="replace")
    manifest["diagnostic_outcome"] = (
        "present_budget_reached" if manifest["exit_code"] == 42 and
        "phase=headless_acceptance status=PASS" in stderr_text else
        "time_budget_reached" if manifest["timed_out"] else "program_stopped")
    capture = run / "present_source.ppm"
    if capture.exists():
        capture_frames = re.findall(r"FBSNAP f=(\d+).*present_source\.ppm \(result=1\)", stderr_text)
        manifest["capture"] = dict(path="present_source.ppm", sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),
            last_logged_vblank=int(capture_frames[-1]) if capture_frames else None,
            meaning="Last published frame; capture threshold does not imply the exact captured vblank")
    if capture_window:
        snapshots = []
        for frame, filename in re.findall(r"FBSNAP f=(\d+).*?\b(frame_v\d+\.ppm) \(result=1\)", stderr_text):
            path = run / filename
            if path.is_file():
                snapshots.append(dict(path=filename, vblank=int(frame), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        manifest["snapshots"] = snapshots
    manifest["savedata_after"] = savedata_inventory(run / "memstick/PSP/SAVEDATA")
    (run / "run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Probe: {run}\nExit: {manifest['exit_code']}; timeout: {manifest['timed_out']}")
    print("\n".join(stderr_text.splitlines()[-22:]))


if __name__ == "__main__":
    main()
