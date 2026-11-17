# Continue development

Status: **paused by the user on 2026-11-17**. Current source is the unaccepted
0.1.3-dev / 120-FPS development checkpoint; installed normal play remains
0.1.2-dev. **Do not resume development or promote a package automatically.** Read
[PAUSED_120FPS.md](PAUSED_120FPS.md) for the current facts, exact candidates,
failures and smallest next experiment. README contains build/run commands;
COPYRIGHT.md defines license boundaries and VALIDATION.md records tested scope.

The prior 0.1.2 published repository passed a fresh remote-clone/submodule/LFS build and
packaging check without an ISO, followed by the scoped bridge battle, Esc settings,
and no-argument EXE launch. See VALIDATION.md for the tested commit and EXE hashes.
`play/` remains an ignored local installation; maintainers create their own package
from the committed prepared inputs. ISO files, saves and private evidence stay local.

The active runtime is ahead-of-time compiled MIPS game code plus PSP system and
graphics/audio services. CPU interpreter bodies are replaced by fatal guards.
Loose game files replace the ISO reader. The prepared build takes versioned C,
headers, imports and a relocated image; `prepared_game.py` checks all their hashes
and rejects changed generator inputs until regeneration. Upstream is the exact
Nakagawa submodule commit `2263985dd8882acbbf1a7313f3752979e7f88e2d`.

Fixed title: ULJS00329, ELF SHA256
`0a25b484b3b324879d2d951172bf44aff8b13bf11bb6a958ff060be8ea4b8b12`,
load base `0x08804000`, entry `0x08804114`, relocated GP `0x08a21660`.
Relocated image SHA256
`aa17cb3f96155592be82a9a0629ec876b61169e3dd3e7ab4e5d8b5e6da53d2f4`.
Use the relocated module-info GP, not the raw ELF word plus the load base.

Retained fixes: proved interior-entry discovery; VSGN and VFAD/VAVG lowering;
RTC TickAddTicks binding; offline Adhoc/Matching lifecycle; cooperative Windows
event pumping; high-resolution composition and SSAA; Unicode startup; native
settings; early pipeline preparation; MPEG's six-byte timestamp parsing.
The module's unknown static targets still fail explicitly. Unsupported VFPU paths
have not been shown unreachable for the entire game.

The earlier scope was **finish 120 FPS, then stop**. The latest instruction is
to pause, record the current results/problems and commit them. The 120 milestone
is incomplete; only resume it on a new request.

120 is selected in Esc, saved and applied on restart (`Graphics/FPS=120`). The
default/rollback is 60. The static generator inserts fractional-step hooks before
the two original comparisons. `step_clock.h` preserves boundaries and time/speed
discontinuities; scene-gated waits and input Peek leave PSP/movie/audio clocks
unchanged. Original and continuous-120 training runs use identical recorded inputs.
Observed 120 rate is about 119.4 updates and new frames per second. Input edges
occur once, and tested movement/attack durations differ by less than one original
frame. Heavy-attack distance differs by 6.2%, failing the five-percent parity
check. Do not claim complete physics equivalence or remove the experimental label.

Night-bridge combat reached 94.72 updates/s at scene 3840×2176 / composition
1920×1088 / SSAA2, and 105.04 at scene 2880×1632 / composition 1440×816 / SSAA2.
Both used a 960×544 output window. Neither met 120. The latest built candidate is
`39abae479f8d7a3f36f6c7585e7c7ae2f5623d5f9ff5c23b79087a0093a5a955`
(`mojin-120fps-math.exe`): its finite graphics math, inactive-capture fast path,
O3 graphics and advisory texture index passed the recorded component/replay
checks, but this exact EXE has not been launched. Preserve it as a WIP candidate;
do not inherit the previous EXE's movie/battle/no-argument acceptance.
See PAUSED_120FPS.md, HIGH_FPS.md and VALIDATION.md. Prepared manifest SHA256 is
`4639a95b2b54b3109d17b452e456d69bc79f2811e209a5c20f952cd0f757c092`.

Unresolved backlog (requires a future request): all characters/stages/story,
progress/unlocks, fire/particle and cooldown timing coverage, city transparency,
early OP skip, other operating systems and new-action APIs. No whole-game claim.

Keep normal-play data separate from probes. Preserve the last verified package,
commit/submodule/LFS identities, settings, saves and effective caches. Never
publish local probe dumps or overwrite a user's save with a test fixture.
