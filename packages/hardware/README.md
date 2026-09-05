# @studio/hardware

Measures the machine and derives a render budget. Nothing here guesses: a field
that cannot be measured is `undefined` with a warning, because a guessed core
count silently produces a wrong render configuration.

```bash
npm run hardware            # human-readable report
npm run hardware -- --json  # machine-readable, for the server
```

Exit code is non-zero when the machine cannot render, so it works as a preflight
check in CI or a launch script.

## What it measures

CPU brand, physical cores, performance/efficiency split, GPU cores · unified vs
discrete memory and genuinely reclaimable free memory · free disk · macOS version
· Node, Python, Chromium · ffmpeg path, version and encoder list.

Two checks earn their place:

**Rosetta detection.** `sysctl.proc_translated` tells us whether Node is being
translated. Remotion under Rosetta is reported at up to half speed and nothing
else says so — the render is simply slow forever. The budget halves concurrency
and the report warns.

**VideoToolbox trial encode.** `h264_videotoolbox` appearing in `-encoders` does
not mean it works; it is compiled into builds on machines that cannot run it, and
the failure only surfaces at encode time. We encode 0.2s of black and see.

## The budget

| Field | Default on 16 GB M5 | Why |
| --- | --- | --- |
| `concurrentRenders` | 1 | A second render doubles peak memory for sub-linear gain, and on a fanless chassis buys throttling |
| `renderConcurrency` | 4 | `min(memory ceiling, performance cores)`. Efficiency cores make a render slower when frames are handed out evenly |
| `ffmpegProcesses` | 2 | One encode, one proxy or probe |
| `ttsProcesses` | 1 | Model load dominates; parallel loads thrash a shared pool |
| `previewEncoder` | `h264_videotoolbox` | Speed dominates for previews |
| `deliveryEncoder` | `libx264` | Quality per bit dominates for delivery, and the render is not interactive |

**These are derived, not measured.** `reasons[]` says how each was reached. The
benchmark harness replaces `renderConcurrency` with a real number; until it has
run, treat the value as provisional — which is exactly what the report says.
