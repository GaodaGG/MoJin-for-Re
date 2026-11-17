# Validation record

This records limited evidence, not a full-game compatibility claim. Source input:
ULJS00329, APP_VER 01.00, DISC_VERSION 1.02, ISO SHA256
`40469759cf0f033f8610f7920ab09b1866040d80b46ff0bdb16b03dfd137b9cb`.
The provided image's declared volume length differs from its physical length;
all used file extents are in bounds. This does not certify it as an unmodified
retail disc. No separate update/DLC was found in the scoped input investigation.

Test machine: Windows 11 25H2, Ryzen 9 8945HX, RTX 5070 Ti Laptop GPU. Linux,
macOS and other GPU families have not been validated for this port.

## Paused 120 FPS development, 2026-11-17

The milestone is incomplete and development is paused. The latest candidate
`39abae479f8d7a3f36f6c7585e7c7ae2f5623d5f9ff5c23b79087a0093a5a955`
has only build/component/graphics-replay checks, **no game launch or battle
acceptance**. [PAUSED_120FPS.md](PAUSED_120FPS.md) records exact performance runs,
retained fixes, failed checks and the smallest next experiment. Installed play
remains 0.1.2-dev. The following describes an earlier UI-layout candidate.

UI-layout EXE SHA256: `36f8108a73aed406b42e26c172c084de99714df8875eb35c612f2db2e287d371`
(0.1.3-dev). Built through the no-ISO prepared path. Prepared manifest:
`4639a95b2b54b3109d17b452e456d69bc79f2811e209a5c20f952cd0f757c092`.
The only change from the measured `cbb8873d...` candidate was the settings-page
layout; only `overlay_quick.o` was recompiled. The final page's save buttons fit
the real 960×544 game window and were visually checked.

See HIGH_FPS.md for the continuous 119.4-Hz training measurement, matching input
edges and actual movement/attack durations. Strict displacement parity did **not**
pass: measured heavy-attack distance was 6.2% shorter. FPS=120 remains explicitly
experimental; this is not a full-game physics, particle or cooldown certification.
An earlier run containing extra physical input was excluded from controlled-motion
comparison. The repeat used the same script and exact nine expected input edges.

That candidate's movie run `20261117T131125235915Z` completed in 145.197 seconds
with the 120 setting selected: all 270 AMW and 3240 OP frames decoded/delivered,
no stale/rejected/superseded/held pictures, no dropped mixed-audio frames and zero
120-rate frame/input/step override calls. The movie clocks therefore remained on
the original path. ISO access was denied throughout; CPU interpreter entries,
static dispatch misses and loose-resource errors were zero. Device-loopback A/V
synchronization is still outside this evidence.

The native UI test verified selecting/saving 120, unrelated INI preservation,
previous-file backup and failed-write preservation. A separate no-argument restart
of the `cbb8873d...` candidate consumed that UI-saved FPS=120 configuration from
a private folder, C:\Windows working directory and System32-only PATH, with ISO
denied. The layout candidate also passed its separate no-argument launch, seven
icon payload checks and private initial-save reload in battle; its night-bridge
rate was only 85.77 updates/s. Later graphics candidates measured 94.17/94.72,
and 105.04 at a lower scene resolution. None is sustained-120 combat acceptance.

## Rebuild, 2026-11-17

- Restored pinned project source, 2,001 fixed upstream source files and 7,307
  prerequisite files into a fresh target. Read and checked the original ISO anew;
  no old ELF, generated game C, objects or executable seeded that full rebuild.
- Corrected the build entry for the portable Python module path and for the
  packaging script's Python lookup. Failed attempts were retained locally.
- A second fresh target consumed the explicit prepared C/image and loose-resource
  inputs with no ISO or input ELF in the snapshot. The original ISO was held with
  a read-only exclusive Windows handle throughout source/tool restoration,
  compilation and packaging; a second open returned error 32. All four stages
  exited successfully. No original files were renamed or changed.
- All 127 game object files and the resulting EXE were byte-identical between
  these two build routes. EXE SHA256:
  `6862536420a0bdb9c90f16f3d101e47eafddb3e062eb6d99207ee82074e3bad3`.
- Prepared input manifest SHA256:
  `a2133da5d87a0228bf8d839b57982802de7cfc1c76940069fd46dd207d5c3915`.
  It covers 133 files (127 C compilation units plus headers/data/metadata).

## Runtime acceptance of that EXE

Two private processes, about 150 seconds each, ran the night-bridge vs CPU route:
one at scene 3840×2176 / composition 1920×1088 / output 960×544 (SSAA2), and one at
scene/composition 480×272 / output 960×544 (SSAA1). The game created an initial
3,744-byte save; the second process loaded it successfully before any replacement
save. Both runs had zero CPU interpreter entries and zero missing static dispatches,
normal guest exit, and no dropped audio output frames. Battle captures and the
original-resolution Chinese settings capture were inspected.

The package launched without arguments from C:\Windows with only System32 on the
runtime PATH, with the original ISO denied. It displayed the Chinese title,
matched all seven icon images, and exited normally after a window-close request.

The newly prepared-input package was also launched from C:\Windows without
arguments, with the original ISO denied, and exited normally after 15.486 seconds.
Its 152 runtime files were compared against the full-rebuild package: 151 were
byte-identical; the sole differing notice index changed only the build executable
name in two fields. No code, runtime library, font or game-resource bytes differed.
The battle/save evidence above therefore refers to the exact same executable and
runtime content, rather than an assumption based only on successful compilation.

Prepared-input rejection checks passed for a missing C unit, an extra C unit,
an unresolved LFS pointer, and changed generator source with stale generated C.
These checks used a private disposable copy and verified the original inputs
remained intact. The dependency setup command also completed using the pinned
local archive and font; all project Python files passed syntax compilation.

The earlier packaged EXE
`15c81bbbcc01c4d6c56935fd1bc03bb3d4df35970407720b3a426c860167b7a0`
also completed the full AMW (270-frame) and OP (3,240-frame) openings, as well as
the same scoped battle/save checks. Its input and runtime fixes are the baseline
for this source milestone. Do not transfer a result to an arbitrary changed build
without checking its inputs and affected behavior.

Nine known pipeline descriptions were prepared before game entry. In the two
fresh-rebuild battle routes no further pipelines were created during drawing.
Application-private caches started empty; the driver-wide cache was not cleared.
These results do not establish cold-driver timing or all-game shader coverage.

## Published repository checkout, 2026-11-17

A new remote clone of commit `b635d0342c17461517b06d89646dcd0237485cd9`
completed checkout, recursive submodule initialization, Git LFS download, setup,
prepared compilation and packaging. The checkout contained neither an ISO nor an
input ELF, nor previous native build outputs. The original external ISO was
read-only locked against other opens throughout these stages and the battle run.
Setup reused the byte-verified official prerequisite archive/tool files; the font
was fetched from its pinned official source. No existing game EXE or objects were
copied into the build.

The resulting EXE SHA256 is
`15c81bbbcc01c4d6c56935fd1bc03bb3d4df35970407720b3a426c860167b7a0`.
A new private battle process ran for 150.292 seconds, created its initial
3,744-byte save, accepted Esc through the normal input path, displayed settings,
and exited normally. Its logs reported zero interpreter entries, missing static
dispatches, loose-file read errors and dropped audio frames. Nine pipelines were
created during preparation and none during drawing. Actual night-bridge battle
and Chinese settings captures were visually inspected; dimensions were scene
3840×2176, composition 1920×1088, output 960×544 with SSAA2.

The image-check subprocess initially failed because the runner intentionally hid
user-installed Python packages, including Pillow. After that failure was retained,
the existing host Pillow 11.3.0 completed the image checks; the game and build inputs
were unchanged. A separate no-argument launch with System32-only runtime PATH and
the ISO locked again exited normally. All seven icon images matched. The cloned
tracked tree remained clean after the build and tests. This adds remote retrieval
and fresh-build evidence; it does not extend the scene coverage listed above.

## Boundaries

Initial-save transport is not proof of story progression, unlocks or every slot.
Audio counts do not prove device-side synchronization. High-resolution internal
targets are not proof of native 4K final composition or a physical 4K display.
120 has limited motion and full opening-movie checks on the specified older
candidates; complete gameplay equivalence and sustained combat performance have
not passed. Known city shadow/transparency issues and early OP-skip
black screens remain. Cross-platform execution and extensible action APIs remain
future work.

Raw captures, audio, saves, process logs, restore samples and private build paths
are retained locally rather than committed. Commit/source hashes and the tools
here permit maintainers to create their own independently scoped evidence.
