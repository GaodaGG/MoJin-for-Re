# High-FPS timing investigation

These are bounded development experiments, not supported playback settings. The
normal package still uses the original update path. No timing correction has been
enabled by this investigation.

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

## Next validation

A future fractional-carry experiment must be opt-in, generated into native code at
the actual step calculation, preserve the original clamp/fallback and speed
changes, and reset across inactive intervals and discontinuities. Do not put
guest-state writes in the read-only observer. Regenerate and verify the prepared
inputs when the static generator changes.

Then measure actual movement, animation, particles, physics, cooldowns, input
edges/history and complete movies independently at 60/90/120. Clock agreement by
itself does not establish those results. No new user-facing FPS option is enabled.
