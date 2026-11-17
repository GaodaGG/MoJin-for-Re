# Continue development

Milestone: **0.1.2-dev**, Windows-only acceptance so far. Read README for build/run
commands, COPYRIGHT.md for license boundaries, and VALIDATION.md for exact scope.

The published repository has passed a fresh remote-clone/submodule/LFS build and
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

Next priorities:

1. Broaden real play/save coverage: additional stages, characters, story, movies,
   progress/unlocks. Diagnose shared ownership, lifetime and synchronization
   before adding scene exceptions. Existing bridge success is not full-game proof.
2. Investigate city shadows/translucent rectangles and very early OP-skip black
   screens. Diagnose remaining stalls by I/O, decode, upload, compilation and sync.
3. Finish high-FPS timing experiments. Blocking controller reads limit updates;
   an experimental Peek/deadline path reached roughly 90 updates/s but showed a
   mismatch between elapsed wall time and an internal accumulated time field.
   The 120-Hz test did not cover its whole window. Add full observation-window
   coverage assertions before interpreting those analyses. Do not enable these
   settings until movement, particles, animation, physics, cooldowns and movies
   have independent timing checks.
4. Isolate Windows host APIs and validate another OS/toolchain before claiming
   cross-platform support. Define state, animation, input and hit-detection hooks
   before promising extensible actions.

Keep normal-play data separate from probes. Preserve the last verified package,
commit/submodule/LFS identities, settings, saves and effective caches. Never
publish local probe dumps or overwrite a user's save with a test fixture.
