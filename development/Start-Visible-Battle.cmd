@echo off
setlocal
pushd "%~dp0.."
echo MoJin native diagnostic - visible vs CPU test, private save folder.
echo Menus are selected automatically. After the battle intro, use your keyboard.
echo Enter=Start, Z=Circle, X=Cross, arrows=D-pad, I/J/K/L=analog, Q/W=L/R.
echo Close the game window to end this test. There is no time limit.
echo This is a development test, not a validated release.
set "MOJIN_TEST_EXE=mojin-isofree.exe"
if exist "%~dp0generated\baseline\mojin-120fps-index.exe" set "MOJIN_TEST_EXE=mojin-120fps-index.exe"
echo 120 FPS experimental battle mode. Use Esc settings in play for normal sessions.
echo Development is paused; 120 FPS combat is incomplete. Read docs/PAUSED_120FPS.md.
"%~dp0toolchain\python\python.exe" "%~dp0tools\probe.py" --exe %MOJIN_TEST_EXE% --game-data "%~dp0resources\game" --vulkan-window --window-pump cooperative --render-scale 4 --ssaa 2 --game-fps 120 --until-closed --audio --save-trace --input-script "%~dp0tests\vs-cpu-entry.pad" --script-handoff
popd
endlocal
