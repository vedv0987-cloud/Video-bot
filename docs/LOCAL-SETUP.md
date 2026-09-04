# 🖥️ Local Setup — running the pipeline on your own machine

**Purpose**: move the GPU stages off the cloud runner and onto your laptop, where the
real models live. The pipeline was built for exactly this: every model sits behind an
interface with an offline default, so switching machines is a flag change, not a port.

> **Nothing in this document has been run on your hardware.** Claude Code sessions
> execute in an ephemeral cloud VM with no GPU and no path to your laptop. Paste your
> specs (§1) and the tier in §2 gets confirmed or corrected.

---

## 1. Report your machine

**Windows (PowerShell):**

```powershell
Get-CimInstance Win32_VideoController | Select Name, DriverVersion
Get-CimInstance Win32_Processor | Select Name, NumberOfCores, NumberOfLogicalProcessors
"RAM_GB: {0}" -f [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)
Get-PSDrive C | Select Used, Free
nvidia-smi
```

`Win32_VideoController` under-reports VRAM above 4 GB — **trust `nvidia-smi`**.

**macOS:** `system_profiler SPHardwareDataType SPDisplaysDataType`
**Linux:** `nvidia-smi; nproc; free -g; df -h /`

### What each number actually gates

| Spec | Gates | Threshold that matters |
| --- | --- | --- |
| **VRAM** | Which models run at all | 8 / 12 / 16 / 24 GB — see §2 |
| **System RAM** | Model loading and CPU offload | 32 GB is the real floor once offloading starts |
| **Free disk** | How many models you can keep resident | 150–250 GB for the full stack |
| **CPU cores** | ffmpeg encode, librosa, Motion Canvas render | 8+ cores keeps encoding off the critical path |
| **GPU generation** | fp8 / bf16 support, NVENC generation | Ada (40-series) or newer unlocks fp8 |

---

## 2. Tiers

Find your VRAM. Everything in your tier and above it is in scope.

### Tier 0 — no GPU, or under 6 GB
**Runs:** Kokoro (CPU, faster than real time), librosa, ffmpeg, Motion Canvas, the whole
content layer.
**Skip:** Chatterbox, WhisperX large, ACE-Step, all video generation.
This is still a complete Phases 1–4 pipeline. You lose the premium voice and generated
music, not the product.

### Tier 1 — 8 GB (e.g. 4060 laptop, 3070)
**Adds:** Chatterbox-Turbo (350M — comfortable), WhisperX `large-v3` in fp16 (~5 GB),
ACE-Step 1.5 for music.
**Marginal:** Wan 2.2 5B GGUF with CPU offload — slow, but it runs.
This tier covers every stage of the plan except high-res video generation.

### Tier 2 — 12–16 GB (4070/4080 laptop, 4060 Ti 16 GB)
**Adds:** HunyuanVideo 1.5 at fp8 with offload (~14 GB), Wan 2.2 5B comfortably,
Qwen3 27B-class quantised for the rewriter.
This is the practical sweet spot for the whole plan.

### Tier 3 — 24 GB+ (4090 laptop, 5090)
**Adds:** Wan 2.2 14B, LTX-2.3 at higher resolution, unquantised Qwen3, parallel stages.
Everything in UPGRADE-PLAN §4.4 runs without compromise.

### Apple Silicon
Kokoro, WhisperX (MPS), librosa, Motion Canvas and ffmpeg all work. Chatterbox and the
video models are CUDA-first — treat an M-series machine as **Tier 0 plus WhisperX**, and
keep video generation off it.

---

## 3. Install order

Five stages. Each ends with a command that proves it worked, so a failure is isolated to
the stage that caused it. Do not proceed past a failing verification.

### Stage 1 — Base (all tiers)

```bash
git clone https://github.com/vedv0987-cloud/Video-bot.git
cd Video-bot
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
videobot --topic "hydration"
```

ffmpeg — needed from Phase 4, install it now:

```powershell
winget install Gyan.FFmpeg          # Windows
```
```bash
brew install ffmpeg                  # macOS
sudo apt install ffmpeg              # Debian/Ubuntu
```

**Verify:** `pytest` green, and `ffmpeg -version` prints a version.

### Stage 2 — Voice

Kokoro first — it is CPU-viable, so it works on every tier and gives you a real voice
immediately.

```bash
pip install kokoro soundfile
videobot --topic "hydration" --voice kokoro
```

Kokoro needs **espeak-ng** for phonemisation. On Windows install it from the espeak-ng
releases page and make sure it is on `PATH`; on macOS `brew install espeak-ng`; on Debian
`sudo apt install espeak-ng`.

Then Chatterbox for finals (Tier 1+, needs CUDA torch — see Stage 3 first):

```bash
pip install chatterbox-tts
videobot --topic "hydration" --voice chatterbox
```

**Verify:** `output/<slug>/` contains a WAV you can actually listen to, and the spec's
`audio.provenance.voice.backend` reads `kokoro` or `chatterbox` rather than `null`.

> Package names for these move between releases. If `pip install` 404s, check the
> project's current README rather than assuming the name here is still right.

### Stage 3 — CUDA torch (Tier 1+)

Install torch **matching your driver**, from the selector at
<https://pytorch.org/get-started/locally/>. Do not copy a CUDA index URL from a blog
post — a mismatch here is the single most common cause of "it installed but runs on CPU".

**Verify:**

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

`True` and your GPU's name. If it prints `False`, stop and fix it — everything downstream
will silently fall back to CPU and take twenty times longer.

### Stage 4 — Alignment and beats

```bash
pip install whisperx librosa
videobot --topic "hydration" --voice kokoro --aligner whisperx --beats librosa
```

WhisperX on Windows also needs cuDNN on `PATH`; if you get a `cudnn_ops64` load error,
that is what is missing.

**Verify:** `audio.provenance.alignment.method` reads `whisperx`. That field is the
whole point — it is how a render tells you whether its timings were measured or guessed.

### Stage 5 — Rewriter and generative assets

```bash
# Local LLM for the constrained rewrite
# install Ollama from https://ollama.com then:
ollama pull qwen3
videobot --topic "hydration" --rewriter qwen3
```

Music (Tier 1+) and video (Tier 2+) come in through ComfyUI rather than this repo — they
are asset generators feeding the spec, not pipeline stages. Install ComfyUI, add ACE-Step
1.5 for music and Wan 2.2 / LTX-2.3 for B-roll, and point the pipeline at the outputs.

**Verify:** the rewriter change survives `assert_no_invented_claims`. If Qwen3 invents a
statistic, the run fails loudly rather than publishing it — that check exists precisely
for this stage.

---

## 4. Disk budget

Approximate download sizes; plan for headroom.

| Asset | Size |
| --- | --- |
| Kokoro | ~400 MB |
| Chatterbox-Turbo | ~1.5 GB |
| WhisperX large-v3 | ~3 GB |
| Qwen3 (8B quantised) | ~5 GB |
| ACE-Step 1.5 | ~8 GB |
| Wan 2.2 5B GGUF | ~6 GB |
| Wan 2.2 14B | ~30 GB |
| HunyuanVideo 1.5 | ~25 GB |
| **Full Tier 3 stack** | **~150 GB, plus render scratch** |

Keep models on your fastest drive. Loading a 30 GB model off a spinning disk costs more
per run than the inference does.

---

## 5. Automation on your machine

The plan's cron entry is Linux. On Windows, use Task Scheduler:

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\path\to\Video-bot\.venv\Scripts\videobot.exe" `
                                   -Argument '--topic "hydration" --voice chatterbox' `
                                   -WorkingDirectory "C:\path\to\Video-bot"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -TaskName "VideoBot" -Action $action -Trigger $trigger
```

**Schedule it overnight.** Two reasons, both real:

1. **Thermals.** A laptop GPU under sustained diffusion load throttles hard. A 4090 laptop
   part is power-limited to roughly a desktop 4080 at best, and drops further as it heats.
   Plug in, set the Windows power mode to Best Performance, and give it a cool surface.
2. **The machine is unusable while it renders.** Video generation will saturate the GPU
   you also design on.

Batch overnight, review in the morning. The content-addressed cache means a re-run after
a tweak only recomputes what actually changed.

---

## 6. What stays in the cloud

| Work | Where | Why |
| --- | --- | --- |
| Code, tests, review | Cloud sessions | No GPU needed; keeps your laptop free |
| Research + spec generation | Either | CPU-only, seconds to run |
| Voice, alignment, music, video | **Your laptop** | Needs the GPU and the models |
| Motion Canvas render | **Your laptop** | CPU/GPU-bound, and you will iterate visually |
| After Effects (Tier C) | **Your laptop** | Already your rig; unaffected by any of the above |

The split works because the scene spec is a plain JSON file. Generate it anywhere, render
it anywhere, commit it for reproducibility.

---

## 7. Order of operations

1. Paste your specs — confirms the tier.
2. Stage 1 everywhere. You have a working pipeline in ten minutes.
3. Stage 2 with Kokoro. First real voiceover.
4. Stage 3 + 4 if you have the VRAM. Real word timings unlock karaoke captions in Phase 4.
5. Phase 3 (Motion Canvas) — first actual video.
6. Stage 5 and the generative assets last. They are the biggest downloads and the least
   load-bearing: a beautifully animated cited explainer with a real voice beats a
   badly-timed one with AI B-roll.
