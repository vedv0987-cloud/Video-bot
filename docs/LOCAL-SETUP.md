# 🖥️ Local Setup — running the pipeline on your own machine

**Purpose**: move the model-backed stages off the cloud runner and onto your own hardware.
The pipeline was built for this: every model sits behind an interface with an offline
default, so switching machines is a flag change, not a port.

> **Claude Code sessions on the web run in an ephemeral Linux VM with no GPU and no path
> to your machine.** Nothing here has been executed on your hardware. To let Claude run
> these steps for you, install Claude Code locally (`npm i -g @anthropic-ai/claude-code`,
> then `claude` in a terminal) — a local session has your actual shell.

---

## 1. Report your machine

**macOS:**

```bash
system_profiler SPHardwareDataType | grep -E "Model Name|Chip|Total Number of Cores|Memory"
sw_vers && df -h / | tail -1
```

**Windows (PowerShell):** `nvidia-smi` is the line that matters — `Win32_VideoController`
under-reports VRAM above 4 GB.

```powershell
nvidia-smi
Get-CimInstance Win32_Processor | Select Name, NumberOfCores
"RAM_GB: {0}" -f [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)
```

**Linux:** `nvidia-smi; nproc; free -g; df -h /`

---

## 2. Confirmed target machine

**MacBook Air · Apple M5 · 10 cores (4 performance / 6 efficiency) · 16 GB unified memory ·
macOS 26.6.2 · 286 GB free.**

Two facts drive every decision below.

**16 GB unified memory is the binding constraint.** macOS and open apps take 4–6 GB, so
budget **~10 GB for models**. That is comfortable for everything this pipeline needs and
firmly rules out the large ones.

**The Air is fanless.** It will hold a burst indefinitely-fast and then throttle under
sustained load. Anything that runs for more than a few minutes wants to be an overnight
batch, lid open, charger in — not a foreground task you sit and watch.

| Stage | Verdict on this machine | Footprint |
| --- | --- | --- |
| Content layer (research → spec) | ✅ Trivial, CPU-only | — |
| Kokoro voice | ✅ Faster than real time | ~400 MB |
| Chatterbox-Turbo | ✅ Use the CPU path | ~1.5 GB |
| WhisperX alignment | ✅ 30-second clips are seconds of work | ~3 GB |
| Motion Canvas + ffmpeg | ✅ VideoToolbox hardware encode | — |
| Qwen3 rewriter | ✅ **8B quantised** — not 14B, not 27B | ~5 GB |
| ACE-Step music | ⚠️ Run it alone, nothing else open | ~8 GB |
| Generative video | ❌ Not on this machine. Rent NVIDIA | 25–30 GB |

**Do not run the pipeline with After Effects or Premiere open.** On 16 GB you will hit
memory pressure and swap, and everything gets slower at once.

Disk is not a constraint: the recommended stack is ~10 GB against 286 GB free.

---

## 3. macOS / Apple Silicon — background

**The headline: a MacBook is a good machine for this pipeline.** Everything except
generative video runs well natively, and generative video is the least load-bearing part
of the plan.

On Apple Silicon the number that matters is **unified memory**, not VRAM — the GPU and CPU
share one pool, so a 64 GB Mac can hold models that would need a 48 GB discrete card.

| Unified memory | What runs comfortably |
| --- | --- |
| **16 GB** | Full content layer, Kokoro voice, Whisper alignment, Motion Canvas, ffmpeg. Qwen3 8B for the rewriter. |
| **24–36 GB** | The above, plus larger local models and comfortable parallel work while rendering. |
| **48–64 GB** | Everything in the plan. Generative video becomes *possible* — see the warning below. |
| **96 GB+** | Video generation without quantisation gymnastics, still slow. |

### What is native and fast

- **Ollama** — Metal-accelerated, the easiest path to Qwen3 for the rewriter.
- **MLX** — Apple's own framework. `mlx-whisper` and `lightning-whisper-mlx` give
  Apple-native speech-to-text; `mlx-audio` covers TTS/STT/STS.
- **Kokoro** — faster than real time on CPU alone; the Mac makes it effortless.
- **ffmpeg with VideoToolbox** — hardware H.264/HEVC encode (`h264_videotoolbox`,
  `hevc_videotoolbox`). A real advantage for Phase 4's encode ladder.
- **Motion Canvas / Node** — platform-neutral, no caveats.
- **After Effects** — runs natively. Verify your Trapcode and Element 3D builds are
  Apple-Silicon-native rather than Rosetta, or Tier C work will crawl.

### What needs care

**Chatterbox-Turbo** advertises MPS support, but reports of MPS tensor-allocation failures
are common enough that community builds default to CPU on Apple Silicon for stability. Our
voiceovers are ~30 seconds, so **CPU inference is perfectly usable here** — it is a few
seconds of compute, not minutes. Try MPS; fall back to CPU without regret.

**Alignment is not a problem on Mac, despite WhisperX being CUDA-oriented.** The clip is
half a minute long. Even CPU forced alignment costs seconds. If WhisperX proves awkward,
`mlx-whisper` transcribes natively — just remember that the value in WhisperX is the
wav2vec2 *forced alignment*, not the transcription, so check that whatever you substitute
still returns word-level boundaries.

### What not to attempt locally: generative video

Measured community results on Apple Silicon, late 2026:

- Wan 2.2 GGUF on an **M1 Max / 64 GB: ~82 minutes for a 2-second clip**.
- LTX-2 fp8 **fails outright on Metal**.
- CogVideoX q4 on an **M3 Ultra: ~338 seconds for one second** at 672×384.
- Wan 2.2 14B at Q4 consumes essentially all of a 32 GB machine.

Even an M4 Max is minutes-per-second-of-footage. That is not a daily pipeline; it is an
overnight job for a few seconds of B-roll.

**Recommendation: skip local video generation entirely.** Rent an NVIDIA GPU by the hour
on the rare occasion you want AI B-roll, and keep your Mac for the stages where it is
genuinely strong. This costs you the least valuable part of the plan — a well-timed cited
explainer with a real voice and clean motion design beats a badly-timed one with AI
B-roll, every time.

---

## 4. NVIDIA tiers (Windows / Linux)

For completeness, and for the rented-GPU case.

- **Under 6 GB or no GPU** — full content layer, Kokoro, librosa, Motion Canvas, ffmpeg.
- **8 GB** — adds Chatterbox-Turbo, WhisperX `large-v3` fp16 (~5 GB), ACE-Step music.
- **12–16 GB** — adds HunyuanVideo 1.5 at fp8, Wan 2.2 5B comfortably. The sweet spot.
- **24 GB+** — Wan 2.2 14B, LTX-2.3 at higher resolution, nothing compromised.

CUDA torch must match your driver — install from the selector at
<https://pytorch.org/get-started/locally/>, never a URL copied from a blog post.

---

## 5. Install order

Five stages. Each ends with a command that proves it worked, so a failure is isolated to
the stage that caused it. Do not proceed past a failing verification.

### Stage 1 — Base (every machine)

```bash
git clone https://github.com/vedv0987-cloud/Video-bot.git
cd Video-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
videobot --topic "hydration"

brew install ffmpeg          # macOS
```

**Verify:** `pytest` green, `ffmpeg -version` prints. On a Mac also confirm hardware
encode is present:

```bash
ffmpeg -hide_banner -encoders | grep videotoolbox
```

### Stage 2 — Voice

```bash
brew install espeak-ng       # Kokoro needs it for phonemisation
pip install kokoro soundfile
videobot --topic "hydration" --voice kokoro
```

Then Chatterbox for finals:

```bash
pip install chatterbox-tts
videobot --topic "hydration" --voice chatterbox
```

**Verify:** `output/<slug>/` holds a WAV you can listen to, and the spec's
`audio.provenance.voice.backend` reads `kokoro` or `chatterbox`, not `null`.

> Package names for fast-moving projects move between releases. If `pip install` 404s,
> check the project's current README rather than trusting the name here.

### Stage 3 — PyTorch

**macOS:** `pip install torch torchaudio` — MPS support is built in.

```bash
python -c "import torch; print(torch.__version__, torch.backends.mps.is_available())"
```

**Windows/Linux:** install the CUDA build matching your driver, then:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

If CUDA prints `False`, stop and fix it. Everything downstream silently falls back to CPU
and takes twenty times longer while appearing to work.

### Stage 4 — Alignment and beats

```bash
pip install whisperx librosa
videobot --topic "hydration" --voice kokoro --aligner whisperx --beats librosa
```

**Verify:** `audio.provenance.alignment.method` reads `whisperx`. That field exists
precisely so a render tells you whether its timings were measured or estimated.

### Stage 5 — Rewriter

```bash
brew install ollama && ollama serve      # or the installer from ollama.com
ollama pull qwen3:8b        # 8B on 16 GB — larger variants will swap
videobot --topic "hydration" --rewriter qwen3
```

**Verify:** the run survives `assert_no_invented_claims`. If Qwen3 invents a statistic the
run fails loudly rather than publishing it — that check exists for exactly this stage.

---

## 6. Disk budget

| Asset | Size |
| --- | --- |
| Kokoro | ~400 MB |
| Chatterbox-Turbo | ~1.5 GB |
| WhisperX large-v3 | ~3 GB |
| Qwen3 8B quantised | ~5 GB |
| ACE-Step 1.5 | ~8 GB |
| **Mac-recommended stack** | **~20 GB** |
| Wan 2.2 14B / HunyuanVideo (skip on Mac) | ~30 GB / ~25 GB |

---

## 7. Automation

**macOS** — `launchd` is the native scheduler; cron still works and is simpler:

```bash
crontab -e
# 02:00 daily
0 2 * * * cd ~/Video-bot && .venv/bin/videobot --topic "hydration" --voice chatterbox
```

**Windows** — Task Scheduler:

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\path\Video-bot\.venv\Scripts\videobot.exe" `
                                   -Argument '--topic "hydration" --voice chatterbox' `
                                   -WorkingDirectory "C:\path\Video-bot"
Register-ScheduledTask -TaskName "VideoBot" `
    -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At 2am)
```

**Schedule it overnight**, and on a laptop keep it plugged in. Sustained inference
throttles hard on battery, and macOS will nap a machine on battery power regardless of
what cron thinks. `caffeinate -s` in the wrapper if you need it awake.

---

## 8. What stays in the cloud

| Work | Where | Why |
| --- | --- | --- |
| Code, tests, review | Cloud sessions | No GPU needed; keeps your Mac free |
| Research + spec generation | Either | CPU-only, seconds to run |
| Voice, alignment, rewriter | **Your Mac** | Native and fast on Apple Silicon |
| Motion Canvas + ffmpeg render | **Your Mac** | VideoToolbox encode, and you iterate visually |
| After Effects (Tier C) | **Your Mac** | Already your rig |
| Generative video, if ever | **Rented NVIDIA** | Minutes-per-second on Apple Silicon |

The split works because the scene spec is plain JSON. Generate it anywhere, render it
anywhere, commit it for reproducibility.

---

## 9. Order of operations

1. **Stage 1** — working pipeline, ten minutes, no GPU.
2. **Stage 2 with Kokoro** — first real voiceover. Skip Chatterbox until you have heard
   Kokoro and decided it is not good enough.
3. **Phase 3 (Motion Canvas)** — first actual video. **This is the step that changes what
   the output looks like**, it needs no GPU, and on this machine it is the single highest
   return in the plan.
4. **Stages 3–5** when you want measured alignment and a smarter rewriter.
5. **Generative video** — not on this machine. Rent an hour of NVIDIA if a specific piece
   ever needs it.
