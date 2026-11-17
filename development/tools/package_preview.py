"""Stage the no-argument native game; no compiler, Python or ISO in the package."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"
BIN = DEV / "generated/baseline"
TOOLS = DEV / "toolchain/msys64/ucrt64/bin"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--exe", default="mojin-preview.exe", help="Tested candidate name under generated/baseline")
    args = parser.parse_args()
    dest = args.destination.resolve()
    if not dest.is_relative_to(ROOT) or (dest.exists() and any(dest.iterdir())):
        raise SystemExit("Choose an empty project directory; existing settings/saves are never overwritten")
    if not re.fullmatch(r"mojin(?:-[A-Za-z0-9_-]+)?\.exe", args.exe):
        parser.error("--exe must name a project candidate without a path")
    exe = BIN / args.exe
    build = json.loads(exe.with_suffix(".build.json").read_text(encoding="utf-8"))
    assert sha(exe) == build["executable_sha256"]
    assert sha(BIN / "mojin_image.bin") == build["image_sha256"]
    if build.get('game_input', {}).get('mode') == 'prepared-c':
        from prepared_game import verify_staged
        verify_staged(build['game_input'])
    else:
        assert sha(ROOT / "魔法禁书目录.iso") == build["input_iso_sha256"]
    for name, digest in build["local_build_inputs"].items():
        assert sha(ROOT / name) == digest, name
    dest.mkdir(parents=True, exist_ok=True)
    origins = {}

    def copy(source, relative):
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert sha(source) == sha(target)
        origins[Path(relative).as_posix()] = source.relative_to(ROOT).as_posix()
        return target

    copy(exe, "MoJin.exe")
    copy(BIN / "mojin_image.bin", "data/mojin_image.bin")
    from disc_data import DATA, MANIFEST, verify
    disc = verify()
    for entry in disc['entries']:
        if entry['directory']:
            continue
        source = DATA / entry['path']
        relative = 'data/game/' + entry['path']
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, target)  # regular files; whole-folder copying needs no junction target
        assert sha(target) == entry['sha256'] and os.path.samefile(source, target)
        origins[relative] = source.relative_to(ROOT).as_posix()
    copy(MANIFEST, 'data/disc-manifest.json')
    for name in ('LICENSE', 'COPYRIGHT.md', 'AI_DISCLOSURE.md'):
        copy(ROOT / name, Path('PROJECT_NOTICES') / name)
    for source_root, output in [(BIN / "font", "font"),
            (DEV / "third_party/nakagawa/assets/vfpu", "data/vfpu"),
            (DEV / "third_party/nakagawa/assets/fonts/ui", "assets/fonts/ui"),
            (DEV / "assets/fonts/ui/noto-sans-sc", "assets/fonts/ui/noto-sans-sc"),
            (BIN / "THIRD_PARTY_NOTICES", "THIRD_PARTY_NOTICES")]:
        for path in source_root.rglob("*"):
            if path.is_file():
                copy(path, Path(output) / path.relative_to(source_root))
    (dest / "data/module-abi-init.txt").write_text(
        "# Module-info GP from pinned ULJS00329 ELF; ABI seed, not a trace.\n# init r28=0x08a21660\n", encoding="ascii")
    # Enumerate PE imports recursively. OS components and the installed Vulkan
    # driver stay system-owned; all other runtime DLLs sit beside the EXE.
    system = Path(os.environ["SystemRoot"]) / "System32"
    queue = [dest / "MoJin.exe"]
    for name in ["SDL3_ttf.dll", "libiconv-2.dll"]:
        queue.append(copy(TOOLS / name, name))
    seen = set()
    while queue:
        path = queue.pop()
        if path.name.lower() in seen:
            continue
        seen.add(path.name.lower())
        pe = subprocess.check_output([str(TOOLS / "objdump.exe"), "-p", str(path)], text=True, encoding="utf-8")
        for name in re.findall(r"DLL Name:\s*(\S+)", pe):
            if name.lower().startswith(("api-ms-", "ext-ms-")) or (system / name).is_file():
                continue
            target = dest / name
            if not target.exists():
                source = TOOLS / name
                if not source.is_file():
                    raise SystemExit(f"Missing dependency {name} required by {path.name}")
                target = copy(source, name)
            queue.append(target)
    (dest / "settings.ini").write_text(
        "; Restart the game after edits. Window output is independent of render resolution.\n"
        "[Graphics]\nRenderScale=4\nSSAA=2\nWindowWidth=960\nWindowHeight=544\nFullscreen=0\nFPS=60\n",
        encoding="ascii")
    (dest / "使用说明.txt").write_text("""魔法禁书目录 Windows 静态重编译开发预览 v0.1.3-dev

当前开发已暂停：120 FPS 实战目标尚未完成。最新图形候选只有构建/组件/重放验证，
未完成游戏实测，不应覆盖已验证的正式游玩版本。详见项目 docs/PAUSED_120FPS.md。

双击 MoJin.exe。无需命令行、Python、编译器或模拟器。首次启动从原作开场进入。
完整复制本运行目录即可独立运行，不需要 ISO、项目目录或开发工具；不能只移动 EXE。
data/game 是直接读取的资源文件。项目内开发包与正式包用硬链接共享实体数据，
它们是普通文件；复制整个目录到其他磁盘会成为独立副本，不依赖原路径。
运行资源请勿直接修改；修改实验应先复制到独立开发目录，避免影响共享文件。
本程序本身包含静态生成的本机游戏代码，不启动另一份游戏进程。
启动时会显示图形准备进度，完成后自动进入游戏。首次遇到尚未覆盖的效果仍可能短暂停顿。

操作：Enter=START，Z=○确认，X=×返回，方向键=十字键，I/J/K/L=摇杆，Q/W=L/R。
跳过剧情：主菜单选择 vs CPU（Story 下方），选人、支援和场地后战斗。
开场影片请等出画后再按 Enter；极早跳过 OP 仍有黑屏风险，重开即可。
窗口右上角关闭结束；运行没有五分钟时间限制。Esc 打开画质设置。

画质：默认场景超采样约 3840×2176，缩小合成到 1920×1088，窗口 960×544。
这不是原生 4K 最终输出；视频、HUD 和贴图仍受原始素材分辨率限制。
Esc 中用上下选择、左右切换，保存后下次启动生效；当前和待生效尺寸分开显示。
也可关闭程序后编辑 settings.ini：RenderScale=1/2/3/4/6/8，对应合成 480×272、960×544、
1440×816、1920×1088、2880×1632、3840×2176；6/8 倍仍属实验档。
SSAA=1（关）/2/4（每轴倍率）。4 倍 SSAA 未验收，设备限制可能使实际倍率降低。
WindowWidth/WindowHeight 可用 1280/720、1920/1080、2560/1440、3840/2160。
这是窗口请求，受桌面限制；只加大窗口不会提高场景分辨率。Fullscreen=1 为桌面全屏。
上述画质设置需重启应用。4K 物理输出尚未验证。
120 FPS：Esc → 战斗帧率 → 120 FPS → 保存，然后重启。也可关闭后设 FPS=120。
FPS=60 恢复原速。120 档提高战斗更新与真实画面频率，并保留分数时间步长；
菜单、加载和影片仍使用原作时钟，没有插帧或全局加速。未覆盖所有角色和招式，保留实验标识。
已测动作耗时差在原作一帧内，但重攻击位移仍短约 6.2%；不保证所有物理、特效和冷却完全一致。

存档：saves/PSP/SAVEDATA；设置：settings.ini；有效优化缓存：userdata；诊断：logs。
更新前保留这四项，以及 settings.ini.previous（上一份设置）。测试使用开发区独立存档。
已有用户确认：战斗可操作，画质改善且流畅，拖窗期间画面和声音继续。
这是开发候选，不代表全游戏验收。部分系统提示仍自动选择默认项；
初始存档跨进程读回已验证；剧情进度、未知静态代码路径、其他场景/角色/影片仍需继续验证。

开发入口（开发项目中）：development/tools/build.py；继续记录：docs/CONTINUE.md。
原始 ISO 仅在开发侧重建/重新提取资源时需要，不属于运行依赖。
原作/资源版本：ULJS00329，APP_VER 01.00，DISC_VERSION 1.02，仅此 ISO 版本。
源码和许可证在项目 development 中；第三方声明随包保留。
项目许可范围、原作归属和大量 AI 参与说明见 PROJECT_NOTICES。
恢复：保留 saves、settings.ini、userdata、logs 后，从已校验归档恢复运行文件。
具体文件摘要及来源见 release-manifest.json。不要按目录名直接清理缓存或存档。
""", encoding="utf-8")
    files = {p.relative_to(dest).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size,
              "source": origins.get(p.relative_to(dest).as_posix(), "generated package text")}
             for p in sorted(dest.rglob("*")) if p.is_file()}
    record = {"version": "0.1.3-dev", "kind": "native development preview, limited scene coverage",
              "build": build, "files": files, "iso_external": False,
              "resource_backend": "loose files with compiled LBA index; no ISO reader",
              "resource_manifest_sha256": sha(MANIFEST),
              "settings_preservation": ["settings.ini", "settings.ini.previous", "saves", "userdata", "logs"]}
    (dest / "release-manifest.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"destination": str(dest), "files": len(files), "bytes": sum(f["bytes"] for f in files.values()),
                      "executable_sha256": sha(dest / "MoJin.exe")}, indent=2))


if __name__ == "__main__":
    main()
