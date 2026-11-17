# 120 FPS checkpoint — paused 2026-11-17

The user paused development and requested a record and commit of the current
work. **120 FPS is not finished or accepted for sustained combat.** Do not resume
performance experiments, promote a package, or extend the port without a new
request. This is a development checkpoint, not a release announcement.

## Installed version and current source

- The local normal-play installation remains **0.1.2-dev**, EXE SHA256
  `15c81bbbcc01c4d6c56935fd1bc03bb3d4df35970407720b3a426c860167b7a0`.
  Its settings, saves and effective caches were not replaced.
- Current source identifies itself as **0.1.3-dev** and includes an experimental
  persistent 60/120 battle setting, static fractional-step hooks and graphics
  performance candidates. Its latest prepared build succeeded, but that latest
  EXE has **not been launched or battle-tested**.
- Latest EXE: `development/generated/baseline/mojin-120fps-math.exe`, SHA256
  `39abae479f8d7a3f36f6c7585e7c7ae2f5623d5f9ff5c23b79087a0093a5a955`.
  Its build record matches all current local build inputs. A local archival
  package is kept under `development/releases/0.1.3-paused`; it is not installed.
- Prepared manifest SHA256:
  `4639a95b2b54b3109d17b452e456d69bc79f2811e209a5c20f952cd0f757c092`.
  The relocated image remains
  `aa17cb3f96155592be82a9a0629ec876b61169e3dd3e7ab4e5d8b5e6da53d2f4`.
  The Nakagawa submodule remains `2263985dd8882acbbf1a7313f3752979e7f88e2d`.

`play/`, ISO files, test saves, captures, binaries, toolchains and private archives
remain excluded from Git. Prepared C and the previously authorized LFS game
resources remain versioned. License and AI-participation boundaries are unchanged.

## Implemented and tested before the pause

Esc offers `120 FPS [experimental]`, with atomic INI save, previous-file backup
and application on restart. Default/rollback remains 60. A real 960×544 settings
capture exposed clipped controls; the compact layout was fixed and visually
checked. The separate UI test covered keyboard selection, Unicode paths,
failed-write preservation and high-DPI layout. The saved 120 choice was read by
a separate no-argument process with only System32 on PATH and ISO access denied.

The generator verifies opcode `28440081` at `0891c0c4` and `0891c1c8`, then emits
the correction before the original comparison. Only prepared C chunk 89 changed;
the other 132 prepared inputs and the relocated image were preserved. The helper
retains fractional title ticks, resets on discontinuity/speed changes, and keeps
the original fallback/clamp. The real C helper passed 20,000 irregular intervals,
13 boundary cases and captured-clock replays. It is not a global clock multiplier.

Continuous 120 uses the battle callback/loading/thread gate; it no longer expires
at the old development interval. PSP scanout, system time, audio and movie clocks
remain on their original paths. Unknown CPU dispatch still fails explicitly;
the tested runs reported zero CPU interpreter entries and missing dispatches.

## Measurements, bound to each executable

All rates below use complete vcount 7600..8800 windows and distinguish actual
common updates from newly presented frames. These are not monitor-refresh
measurements. Tests include observation overhead and do not clear driver caches.
The same combat input route does not make enemy AI/hit-stop states identical.

| EXE SHA prefix / run ID | Route / scene target / composition / SSAA | Updates/s | New frames/s |
| --- | --- | ---: | ---: |
| `cbb8873d702a` / `20261117T125926366911Z` | Training / 3840×2176 / 1920×1088 / 2 | 119.373 | 119.376 |
| `36f8108a73ae` / `20261117T131429474063Z` | Night bridge vs CPU / 3840×2176 / 1920×1088 / 2 | 85.772 | 85.778 |
| `7eeebf6a095f` / `20261117T132810480147Z` | Same combat route, O3 graphics / same dimensions | 94.172 | 94.174 |
| `c6e87b212070` / `20261117T134553512845Z` | Same route, advisory texture index / same dimensions | 94.723 | 94.725 |
| `c6e87b212070` / `20261117T135136341320Z` | Same route / 2880×1632 / 1440×816 / 2 | 105.037 | 105.050 |

The window output was 960×544. Lower resolution did not meet 120 either. The
index's small observed difference is **not proof of a repeatable performance
gain**. None of these combat results establishes sustained 120 FPS. In the last
lower-resolution diagnostic, missing script handoff kept the automation guard
active; Esc was rejected. That run is not settings-overlay acceptance.

The controlled training comparison used the exact nine expected input edges at
60/120. Running and light-attack distances were within 5%; measured movement and
attack durations differed by less than one original 60-Hz frame. **Heavy-attack
distance was 6.2% shorter**, failing the retained 5% parity check. Dense captures
showed motion/guard/attacks/hit glow but reduced performance, so they are separate
visual evidence. See [HIGH_FPS.md](HIGH_FPS.md) for ratios and exact runs.

The `36f8108a...` movie run `20261117T131125235915Z` decoded and delivered all 270
AMW and 3240 OP frames with 120 selected, zero timing overrides and no mixed-audio
drops. A distinct bridge process loaded its private initial save successfully.
Its no-argument launch and seven icon payloads also passed. Those checks do not
transfer automatically to the latest `39abae47...` build.

## Graphics investigation and newest unaccepted candidate

The read-only profile run `20261117T133644851677Z` measured 20.022 seconds:
16.843 seconds in GE lists, 9.138 in their inclusive GPU hook, and 6.131 in the
backend's object-lookup category. **Lookup includes content hashing and memory
coherence/readback waits**; it is not 6.1 seconds of texture-table scanning.
Nearby interval telemetry showed about 4.8 seconds in Vulkan readback, no
in-frame pipeline creation and negligible texture decoding/storage activity.
Profiling has overhead and is not a performance acceptance run.

Retained development changes:

- Native GE frontend/backend use O3 without fast-math; the frontend keeps the
  upstream `-fno-math-errno` policy. Game AOT objects remain O1.
- The texture index is advisory: every candidate index is bounds checked and
  compared against the full existing key/mip descriptor. Hash/content checks,
  invalidation, uploads and linear miss fallback remain. The compiled helper
  matched ordered lookup in 100,000 randomized operations, including collisions,
  3,222 moving-slot evictions, mip changes and stale entries after reset.
- The newest candidate adds an inline guard around five inactive capture calls
  and finite min/max comparisons in native graphics code. NaNs, infinities and
  pairs of signed zeros use the original C functions. A first test found a NaN
  payload mismatch caused by compiler substitution; explicit indirect fallback
  fixed it. The final helper passed 4,000,900 result-bit comparisons. Floating
  exception flags and other platforms were not certified by that test.
- Four retained real GE streams at actual 1×/4×/8× targets produced byte-identical
  480×272 guest readback before/after the newest renderer changes (12 pairs).
  This graphics-only tool does not initialize ACE/SSAA; no claim of high-resolution
  presented-pixel or SSAA equivalence is inferred from those exports.

GPU T&L was investigated but **not enabled**: this device failed upstream's
`shaderDenormPreserveFloat32` requirement, and every tested primitive retained
the CPU graphics path. Matching pixels prove fallback, not GPU T&L acceptance.
Full-image readback matched the row-copy pixels but showed no consistent replay
speed benefit; it was not selected for normal startup or tested in live combat.

## Resume only on request

The smallest next experiment is one visible, private night-bridge run of
`mojin-120fps-math.exe`, at scale 4/SSAA2, with `--game-fps 120 --perf --loop-trace`,
the retained `vs-cpu-120.pad`, and `--script-handoff` before the Esc check. Compare
complete windows with the recorded 94-FPS candidates; do not infer a benefit
from successful compilation or replay equality. The new capture guard also needs
an active in-game capture check. If the candidate regresses, retain the failure
and use a verified checkpoint to revert only the affected optimization.

Before any promotion, recheck the chosen exact EXE's combat/motion, movie timing,
save/reload, settings, no-argument launch and package dependencies. Heavy-attack
displacement, particles/fire, physics/cooldowns, scene transitions and other
characters remain incomplete. The attempted pause-menu route did not prove exit
from the battle callback. Do not extend 90 FPS, cross-platform or new-action work.

Local recovery: preserve `archive/`, the matching `.build.json` files, test run
directories and `development/evidence/`. Source/package ZIPs record all SHA256s,
CRC verification and actual restore samples; resource payloads are indexed
separately to share one entity. The post-commit Git bundle and LFS recovery index
are recorded in local `development/evidence/publication-recovery.json`.
