# MoJin-for-Re · 魔法禁书目录

PSP《魔法禁书目录》（ULJS00329）的实验性静态重编译移植，目前验证平台为 **Windows x64**。阶段版本 **0.1.2-dev**：提供无参数原生 EXE、中文 Esc 设置、高分辨率与超采样抗锯齿、拖动窗口时持续运行，以及无需 ISO 的运行包与预生成 C 构建流程。

**大量实现、修复、测试和文档由 OpenAI Codex 辅助完成。** 详见 [AI 参与说明](AI_DISCLOSURE.md)。项目适配代码按 GPL-3.0-or-later 开源；仓库中的游戏派生代码、提取资源和原作图标不因入库而获得项目的 GPL 授权。原作和第三方版权分别保留，详见 [版权与许可范围](COPYRIGHT.md)。这是非官方项目，完整游戏尚未验收。

## 获取与构建

需要 Windows、Git、Git LFS、Python 3.11+ 和可用的 Vulkan 驱动。构建目录路径请不要包含空格。仓库不包含 ISO、预编译游戏 EXE、个人存档或诊断转储；包含预生成游戏 C、程序数据以及通过 LFS 管理的提取资源。

```powershell
git -c core.autocrlf=false clone --no-checkout https://github.com/GaodaGG/MoJin-for-Re.git
cd MoJin-for-Re
git lfs install --local
git checkout main
git submodule update --init --recursive
git lfs pull
python development/tools/setup.py
python development/tools/build.py prepared --output-name mojin-isofree.exe
python development/tools/package_preview.py development/releases/local --exe mojin-isofree.exe
```

上述构建不读取 ISO。setup 下载固定版本的工具链和字体并校验摘要；prepared 模式校验生成代码、资源及来源后，从 C 重新编译全部所需本机对象。不能只下载 GitHub 的普通源码 ZIP 而忽略 submodule 和 LFS 对象。

这里将克隆与首次 checkout 分开，兼容本机 Git 2.45.1 的 LFS hook 限制；不需要关闭 Git 的克隆安全检查。

完成后双击 **`development/releases/local/MoJin.exe`**。整个运行目录可复制到其他位置，运行不需要 ISO、Python、编译器或项目目录；必须保留资源、DLL、字体和许可文件。打包目标需要为空，以保护已有设置和存档。维护者的完整构建、增量修改及恢复说明见 [开发文档](docs/DEVELOPMENT.md)。

## 当前效果与操作

- Esc 打开中文画质设置；分开显示场景目标、游戏合成和窗口输出的实际尺寸，保存后下次启动生效。
- 默认场景 **3840×2176**，通过每轴 2 倍超采样缩小合成到 **1920×1088**，窗口为 **960×544**。这不是原生 3840×2160 最终输出；原始 HUD、视频和贴图不会凭空增加细节。
- 保持原作时间推进。**90/120 FPS 尚未验收，未作为正式设置开放**；更大渲染倍率也仍需按显卡和场景验证。
- 启动前准备已知图形管线并显示进度；未知状态继续使用正常创建路径和后续缓存。当前目录仅覆盖已测开场、菜单和夜桥战斗，不能保证所有首次访问场景无卡顿。
- Enter＝START，Z＝○确认，X＝×返回，方向键＝十字键，I/J/K/L＝摇杆，Q/W＝L/R。主菜单选择 vs CPU 可先测试战斗。关闭窗口正常退出。

保存和更新时保留 `saves/`、`settings.ini`、`settings.ini.previous`、`userdata/` 和 `logs/`。诊断工具使用独立存档，不应覆盖正常游玩数据。

## 实现边界

CPU 路径是 **MIPS → 构建时生成 C → 本机编译**。运行时实现 PSP 系统服务、内存/寄存器状态、图形命令和音频行为；这些兼容服务仍在模拟原平台行为。它不是把完整引擎重写成 PC 引擎，也不是调用 PPSSPP 程序的启动器。

本项目移除了上游 CPU/VFPU 指令解释主体。未知静态跳转或未支持指令明确失败，不静默回退到 CPU 解释执行。游戏指令修复进入静态生成流程；修改加载后的原指令不会自动改变已生成的本机代码。

Nakagawa-Recomp 以 submodule 固定在 `2263985dd8882acbbf1a7313f3752979e7f88e2d`。项目补丁保存在本仓库的生成器和运行时覆盖层，上游树保持未修改。PPSSPP 源码仅作语义参考。

## 验证范围和已知问题

已验证限定路线：AMW/OP 开场影片、夜桥 vs CPU 战斗、输入、音频输出、初始存档创建和另一进程读回、Esc 设置、正常退出，以及双击式无参数启动。完整原始输入重建与无 ISO 的预生成 C 重建均已有本机证据。详见 [验证记录](docs/VALIDATION.md)。

仍待解决或验证：城市阴影/透明矩形问题、极早跳过 OP 可能黑屏、部分系统提示自动选择默认项、其他剧情/CG/角色/场地、进度和解锁存档、设备端音画同步、90/120 FPS 各系统时间推进。跨平台构建和新动作接口是后续目标，当前没有宣称实现。

可以游玩：**限定场景的开发预览**。可以增量构建：**是**。可以从固定原始 ISO 完整重建：**已在本机验证**。仅凭仓库及固定开发依赖、无 ISO 构建：使用上面的 prepared 路径；依然需要完整下载 submodule 与 LFS 对象。
