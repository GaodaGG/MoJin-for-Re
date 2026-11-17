# Validation record

This records limited evidence, not a full-game compatibility claim. Source input:
ULJS00329, APP_VER 01.00, DISC_VERSION 1.02, ISO SHA256
`40469759cf0f033f8610f7920ab09b1866040d80b46ff0bdb16b03dfd137b9cb`.
The provided image's declared volume length differs from its physical length;
all used file extents are in bounds. This does not certify it as an unmodified
retail disc. No separate update/DLC was found in the scoped input investigation.

Test machine: Windows 11 25H2, Ryzen 9 8945HX, RTX 5070 Ti Laptop GPU. Linux,
macOS and other GPU families have not been validated for this port.

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

## Boundaries

Initial-save transport is not proof of story progression, unlocks or every slot.
Audio counts do not prove device-side synchronization. High-resolution internal
targets are not proof of native 4K final composition or a physical 4K display.
90/120 FPS have not passed movement, particles, animation, physics, cooldown and
movie timing checks. Known city shadow/transparency issues and early OP-skip
black screens remain. Cross-platform execution and extensible action APIs remain
future work.

Raw captures, audio, saves, process logs, restore samples and private build paths
are retained locally rather than committed. Commit/source hashes and the tools
here permit maintainers to create their own independently scoped evidence.
