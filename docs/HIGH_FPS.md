# 120 FPS setting and timing evidence

**Paused 2026-11-17; the 120-FPS milestone is incomplete.** Training reached
119.4 updates/s, while the tested night-bridge candidates reached about 94.7 at
the highest tested quality and 105.0 at the lower SSAA2 preset. The latest
graphics candidate is built/replay-checked but has no live-game acceptance.
See [the current checkpoint](PAUSED_120FPS.md) before using the historical results.

Version 0.1.3 adds a persistent **120 FPS [experimental]** battle setting. Open Esc,
select the battle frame-rate row, save and restart. `Graphics/FPS=60` restores the
original path; existing settings and saves are preserved during installation.
The normal launcher clears inherited diagnostic variables before applying its INI.
The user requested that development stop after this 120-FPS milestone.

The battle gate is the observed scene callback `0885f978`, completed loading state
3 and a valid wait-capable guest thread. The regular setting has no vblank expiry.
Menu/movie code retains the original waits and clocks. The separate bounded
90/120 development switches remain only to reproduce the earlier evidence below.

## Controlled motion and current limits

Candidate `cbb8873d702a8054b9d09ee74ea6b841d6b26b71ed7eac97674dc1f7049f743c`
completed the same `training-motion.pad` route at original speed
(`20261117T130329814313Z`) and continuous 120 (`20261117T125926366911Z`).
Both used private saves, denied ISO access and exited normally. Each of the nine
measured button edges appeared exactly once. The 120 measurement window contained
119.373 updates/s and 119.376 newly presented frames/s. Its step correction was
already active at vcount 6391, and remained active beyond the former v9000 limit.

| Motion | 120/original path length | Duration difference |
| --- | ---: | ---: |
| Run right | 1.03543 | +7.60 ms |
| Run left | 1.03192 | +6.00 ms |
| Light attack | 1.00749 | -9.63 ms |
| Heavy attack | 0.93805 | -15.30 ms |

The sampled transform is guarded by its fixed class table and compared after the
common update. Durations are within one original 60-Hz frame. **The heavy attack
fails the retained five-percent displacement-parity check.** This remains a known
difference; the timing comparison does not turn that failure into a pass. The
port therefore exposes 120 as experimental, not as full gameplay equivalence.
All fighters, fire/particle lifetimes, collisions and ability cooldowns have not
been exhaustively measured. One fixed fighter/room cannot establish those results.

Separate dense render captures at 60/120 show movement, guard, attacks and hit glow.
Those captures incur GPU readback overhead (about 49/100 updates/s), so they are
visual timing evidence, not the 120-FPS performance measurement. An earlier run
with extra physical key presses was rejected by the controlled-input comparison;
it is retained as interactive evidence only. The settings page was subsequently
compacted after a real 960×544 capture exposed clipped save buttons.

## Earlier bounded experiments

## Version and method

Tested on the Windows/NVIDIA machine in VALIDATION.md with ULJS00329's fixed
prepared image, SHA256
`aa17cb3f96155592be82a9a0629ec876b61169e3dd3e7ab4e5d8b5e6da53d2f4`.
The instrumented EXE SHA256 is
`c0664017b4a89498556fb97267742697903a065909c6eb570705ba6612889b2a`.
It was compiled from prepared C without ISO input; each private runtime probe
held the original ISO read-only and unavailable to a second open.

The training entry script reaches the same room and character pair. Rendering is
scene 3840×2176, composition 1920×1088, window 960×544, SSAA2. Measurements cover
vcount 7600 through 8800 after the experimental gate starts at 7400. Both update
traces and newly presented frames must bracket the entire measurement window.
An early normal exit is rejected: the older 120-Hz run ended at update vcount 8102
and fails the new coverage check. Its result is not accepted as a full-window test.

The observer records the engine's last measured system time, signed speed factor,
integer/float step and accumulated time. It only reads guest state. The experiment
replaces one statically identified blocking controller read with the existing Peek
service and one frame wait with callback-aware deadline waits. PSP scanout,
RTC/system time, audio clocks and movie clocks remain unchanged. A presented-frame
count does not measure physical monitor refresh.

## Confirmed arithmetic loss

`f_0891bf14` calculates the next integer step, for the positive-speed regime:

```text
percent = floor(delta_us * 100 / 16667)
step = floor(percent * (speed_i16 << 5) / 12800)
step <= 0 falls back to 32; step > 128 is clamped to 128
```

Both branches (ordinary frame and every-sixth-frame statistics) use that same
arithmetic. `f_08907c44` subsequently consumes the integer/float fields and adds
float step / 1920 to its accumulator. Observed speed was 128 throughout all three
windows, with no positive common-step override.

| Requested rate | Measured updates/s | New frames/s | System-time span | Integer-step sum / 1920 | Formula matches |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original path (~60) | 59.842 | 59.840 | 20.020000 s | 19.859896 s | 1198 / 1198 |
| 90 | 89.880 | 89.880 | 20.026762 s | 19.560417 s | 1800 / 1800 |
| 120 | 119.616 | 119.615 | 20.022268 s | 19.347917 s | 2395 / 2395 |

Runs: `20261117T120353899680Z` (original), `20261117T115711061277Z` (90),
`20261117T120026755811Z` (120). All completed normally with no trace drops, CPU interpreter entries, missing
static dispatches, loose-resource errors or dropped audio frames. Training-room
captures were visually inspected. These idle-window observations confirm the
quantization loss; they do not validate movement, animation or gameplay speed.
The original path also loses about 0.8% against measured time on this host; do not
assume that making the high-rate clock exact automatically matches every stock
behavior. The high-rate runs retained the automation marker, so their delayed Esc
was refused by that guard; they provide no new settings acceptance. The original
run handed control back after its script and passed Esc/pause/capture/normal quit;
its Chinese overlay was visually inspected.

The 90-Hz captured deltas were also replayed through an **offline** exact rational
model. Carrying the discarded fraction gives 38450 integer ticks versus the exact
38450.614028, instead of the game's 37556. This is a candidate calculation for a
future static hook, not a repair applied to the tested executable.

## Static fractional-carry experiment

Candidate EXE SHA256:
`583c753d6477c0932c58b1958165e8ebc96bc132bdd9a59e0eac7fb98332878f`.
The generator checks opcode `28440081` at `0891c0c4` and `0891c1c8` and emits
the optional hook before the original comparison. Only `mojin_recomp_89.c` changed:
the exact two hook insertions were verified, with the other 132 prepared inputs
unchanged, including the original image. This is compiled native code, not a
patch to loaded MIPS bytes.

The positive-speed ratio simplifies to `delta_us * speed / 66668`. The helper
retains the integer division remainder across consecutive samples. It resets
on inactivity, time discontinuity or speed changes, and preserves the original
zero-step fallback and long-frame clamp. A mismatched original quotient is
reported as an error and left untouched. The read-only observer does not write
guest state. The switch is `probe.py --experimental-step-carry`, which requires
both `--experimental-update-rate 90` (or 120) and `--experimental-input-peek`.

The actual production arithmetic compiled with warnings-as-errors passed 20,000
irregular intervals against Python's exact Fraction oracle, 13 boundary/reset
cases, and replay of the three captured stock-clock runs. These component checks
were followed by visible training runs with the new native EXE:

| Corrected rate | Actual updates/s | System-time span | Actual integer steps / 1920 | Verified intervals |
| --- | ---: | ---: | ---: | ---: |
| 90 | 89.780 | 20.026542 s | 20.026563 s | 1798 / 1798 |
| 120 | 119.311 | 20.023869 s | 20.023438 s | 2389 / 2389 |

Runs: `20261117T121941577915Z` and `20261117T122253728046Z`. Each interval's
remainder, integer step, floating step and step / 32 agree. Total quantization
error is less than one tick (1/1920 second) against the unrounded title ratio.
The game's float accumulator still has its own rounding: it advances by
20.025730 and 20.024359 seconds respectively. System time is not rescaled.
Both runs completed without correction errors/bypasses, trace drops, missing
static dispatches or interpreter entries. Script handoff allowed the subsequent
normal Esc settings capture and normal guest quit. The training captures and
the 90-Hz run's Chinese overlay were visually inspected.

The same EXE with all three experimental switches disabled completed run
`20261117T122613352718Z`: 59.840 updates/s, 20.020000 measured seconds and
19.855729 integer-step seconds. All 1198 intervals retained the original formula;
all observed carry states stayed inactive. Both enabled runs also verified reset
outside the bounded gate. The disabled run passed normal Esc and guest quit.

The regenerated prepared manifest is
`4639a95b2b54b3109d17b452e456d69bc79f2811e209a5c20f952cd0f757c092`.
The previous prepared input set was verified against its retained archive, a C
file was actually restored and compared, and the entire old set was preserved
before export. The game image and loose-resource hashes are unchanged.

## Remaining validation

The fractional-carry prepared inputs also passed a fresh ISO-denied build and
standalone launch (`step-carry-noiso-01`). Its 127 game objects match the raw-input
build; the source-ZIP restoration lacks Git build-identity defines in the flight
recorder, so its complete EXE hash is different. This is not byte-identical EXE
reproducibility. The current 120 setting's scoped motion results are above.
Remaining per-character effects, physics and cooldown coverage stays explicitly
unverified. Further 90-FPS, cross-platform and action-extension work is outside
the user's final 120-FPS delivery scope.
