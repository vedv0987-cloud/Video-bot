# 🎛️ Video-Bot v2 — Upgrade Plan

**Status**: proposal · **Date**: September 2026 · **Supersedes**: the tooling choices in `video-bot-roadmap.md` (the pipeline shape stays)

---

## 0. The one-sentence version

The v1 roadmap builds a *slideshow generator*; this plan turns it into a *motion design system* by moving animation off MoviePy onto a real scene-graph engine, joining the two halves with a declarative scene spec, and adding the six craft layers (easing, motion blur, karaoke captions, beat sync, loudness mastering, grade) that actually separate agency-grade output from AI slop.

---

## 1. Honest diagnosis of v1

The v1 pipeline is correct in *shape* — the ten stages are the right ten stages. It is wrong in one load-bearing place, and that one place caps the ceiling of everything downstream.

### The core problem: MoviePy is a compositor, not an animation engine

MoviePy wraps FFmpeg for **cutting, layering, and muxing**. It has no animation model:

| What pro motion graphics needs | What MoviePy offers |
| --- | --- |
| Scene graph with parented transforms | Flat list of clips |
| Easing curves (cubic, expo, back, spring) | Linear interpolation, or hand-rolled `lambda t:` |
| Timeline with relative/staggered timing | Absolute start/end seconds per clip |
| Sub-frame motion blur | None |
| Vector shapes, masks, strokes, gradients | Rasterized PNGs you supply |
| Retiming without re-authoring | Re-derive every constant by hand |

Every "animation" becomes a per-frame Python callback. That is why programmatically generated MoviePy videos read as PowerPoint with a voiceover — **no amount of font choice or gradient polish fixes a missing easing model**. v1's own Challenges §2 identifies the symptom ("MoviePy text is basic") and prescribes better fonts and background shapes. That treats the rash, not the infection.

### Five secondary gaps

1. **No captions.** ~85% of short-form is watched muted. v1 has a voiceover and no burned-in text sync. This is the single highest-ROI omission in the document.
2. **No audio mastering.** "Lower music volume with pydub" is not ducking, and nothing targets a platform loudness spec. Output will be quiet and muddy next to native content.
3. **No cache / DAG.** Every run regenerates everything. Fix one word in the script → re-run TTS, re-render 1400 frames. This kills iteration speed, which kills quality.
4. **Dated model choices.** Coqui shut down; `tacotron2-DDC` is 2020-era. `pydub` is effectively unmaintained. The 2026 open-weight landscape is dramatically better (§4).
5. **No health-content gate.** Auto-generated medical claims published at scale is the largest *actual* risk in this project and v1 does not mention it (§7.1).

---

## 2. Target architecture

The central change is a **hard seam** between content and motion, joined by a serialisable spec.

```
┌─────────────────── CONTENT LAYER (Python) ───────────────────┐
│  topic → research → claims+citations → script → VO → music   │
│  → forced alignment (word timings) → beat map                │
└───────────────────────────┬──────────────────────────────────┘
                            │
                    scene-spec.json   ◄── the seam. Version it. Diff it. Review it.
                            │
┌───────────────────────────▼─────── MOTION LAYER ─────────────┐
│  Tier A  Motion Canvas / Revideo   2D kinetic type, charts   │
│  Tier B  Blender (bpy, EEVEE Next) 3D hero shots, anatomy    │
│  Tier C  After Effects (your rig)  bespoke set-pieces        │
└───────────────────────────┬──────────────────────────────────┘
                            │ PNG/EXR sequences + stems
┌───────────────────────────▼───── FINISHING LAYER (FFmpeg) ───┐
│  conform → grade (LUT) → captions (libass) → master (R128)   │
│  → encode ladder (9:16 / 1:1 / 16:9) → QC gates → publish    │
└──────────────────────────────────────────────────────────────┘
```

**Why the seam pays for itself:**

- The motion engine becomes swappable. Start on Tier A; add Tier B for hero shots; drop in AE for a client piece — the content layer never changes.
- The spec is reviewable *before* rendering. Catch a bad claim or clumsy pacing in a 2KB JSON, not after a 6-minute render.
- It is cacheable. Hash the spec node → skip the render if unchanged.
- It is a handoff format. Emit **OpenTimelineIO** alongside it and any render opens in DaVinci Resolve or Kdenlive for manual polish. The bot gets you to 90%; you finish the hero pieces by hand.

### The scene spec (sketch)

```jsonc
{
  "meta": { "topic": "hydration", "duration_s": 42.5, "aspect": "9:16", "fps": 30 },
  "brand": { "tokens": "brand/health-v2.json" },       // colors, type ramp, timing scale
  "audio": {
    "vo": "cache/vo/8f3a….wav",
    "music": { "track": "cache/music/ace-step/2b1c….wav", "duck": "sidechain" },
    "beats": [0.51, 1.02, 1.53, 2.04],                 // librosa onset map
    "words": [ { "w": "Did", "t0": 0.31, "t1": 0.48 }, … ]   // WhisperX alignment
  },
  "scenes": [
    {
      "id": "hook", "in": 0.0, "out": 4.2, "tier": "A",
      "layout": "statement-center",
      "elements": [
        { "type": "text", "content": "You're 60% water.",
          "role": "display",
          "in": { "at": 0.35, "anim": "rise-blur", "ease": "expo.out", "dur": 0.42 },
          "out": { "at": 3.9, "anim": "fade-scale", "ease": "cubic.in", "dur": 0.25 } },
        { "type": "counter", "from": 0, "to": 60, "suffix": "%",
          "in": { "at": 0.55, "ease": "expo.out", "dur": 1.1 }, "snap": "beat" }
      ],
      "bg": { "type": "gradient-mesh", "seed": 4412, "drift": 0.02 }
    }
  ],
  "captions": { "style": "karaoke-pop", "safe_area": "tiktok-9x16" },
  "citations": [ { "claim": "60% water", "source": "PMID:12345678", "verified": true } ]
}
```

---

## 3. Motion engine: the decision

This is the choice the whole upgrade hinges on. All four are credible; they are not interchangeable.

| Engine | License | Animation model | Batch/headless | 3D | Verdict |
| --- | --- | --- | --- | --- | --- |
| **Motion Canvas** | **MIT** ✅ | Generator-based timeline, scene graph, full easing library, waveform-synced editor | Adequate | ✗ | **Tier A pick** |
| **Revideo** (MC fork) | **MIT** ✅ | Same as MC | **Built for it** — headless API, React player | ✗ | Strong, but see risk |
| **Remotion** | ⚠️ **Not free for 4+ employee for-profits** ($25/seat) | React components, huge npm ecosystem | Best in class | ✗ | Conditional |
| **Blender** (`bpy`) | **GPL** ✅ | Full 3D: keyframes, F-curves, Geometry Nodes, physics | CLI headless | ✅ | **Tier B pick** |

**Recommendation: Motion Canvas as Tier A, Blender headless as Tier B.**

Reasoning:

- **Motion Canvas is MIT and actively maintained** (last updated July 2026). Its generator-function timeline (`yield* tween(...)`) is the closest thing in open source to authoring in After Effects with code — real easing, real scene graph, real relative timing. It is explicitly a *craftsman's* tool, which is the correct bias when the goal is "looks expert."
- **Revideo** is the better *pipeline* shape (headless rendering API, library-first, MIT). But its team has moved to a commercial product, **Midrender**, and states that recent engine work has not been upstreamed to the open-source repo. Usable today, slowing tomorrow. → **Use Revideo's headless renderer if you need it, but keep scenes authored in vanilla Motion Canvas idiom so you can walk away without a rewrite.**
- **Remotion has the strongest ecosystem and batch story, and it is the one to reject on your stated constraint.** Free for individuals and for-profits with **up to 3 employees**; a for-profit hitting **4 people needs a paid company license — triggered by company headcount, not by how many people touch the tool**. As a solo studio you are compliant today. The moment you hire, or ship this as a product to a client, you are not. Since the brief is "free, open source," Tier A goes to Motion Canvas. Revisit only as a deliberate, budgeted decision.
- **Blender is the actual ceiling for "expert."** It is the only free option with physically-based light, true motion blur, depth of field, volumetrics, and Geometry Nodes procedural motion — i.e. the anatomical cutaways, liquid sims, and 3D product turns that make health content look premium. EEVEE Next renders fast enough for short-form. Use it for the 10–20% of shots that carry the piece.
- **Manim** is excellent and wrong here — its idiom is mathematical exposition, not brand motion. Keep it in the box for the occasional data explainer.

---

## 4. Tool stack — 2026 replacements

Every row below was checked against current sources (September 2026). **License column is the deciding column.**

### 4.1 Voice — replaces Coqui/Tacotron2

| Tool | License | Why |
| --- | --- | --- |
| **Kokoro** (82M) | **Apache 2.0** | Draft/iteration voice. Faster than real-time on CPU, ~2–3GB VRAM, 54 voices / 8 languages. Cannot clone. |
| **Chatterbox-Turbo** (350M, Resemble AI) | **MIT** | Final voice. Blind study: **65.3% preferred it over ElevenLabs vs 24.5%**. Supports cloning. |
| ~~F5-TTS~~ | ❌ CC-BY-NC 4.0 | **Excluded** — non-commercial only. |

**Pattern: stack, don't pick.** Kokoro for every draft render (instant), Chatterbox-Turbo for the final master. Put both behind one `synthesize(text, voice_profile) -> wav` interface.

### 4.2 Music — replaces "a folder of CC tracks"

| Tool | License | Why |
| --- | --- | --- |
| **ACE-Step 1.5** | **Apache 2.0** | Released Jan 2026. Full track in **<10s on an RTX 3090**. Bespoke, on-brief, zero attribution burden, zero Content-ID risk. |
| Stable Audio Open | ⚠️ Community License, free **under $1M revenue** | Fallback. Note the cap. |
| ~~MusicGen~~ | ❌ CC-BY-NC 4.0 | **Excluded** — output not commercially licensed. |

Generating music removes the entire "Copyright of Background Music" challenge from v1 §5 rather than mitigating it.

### 4.3 Captions — new, highest ROI in this document

| Tool | License | Why |
| --- | --- | --- |
| **WhisperX** | BSD-ish (check per-component) | wav2vec2 forced alignment → **<100ms word-level timestamps**, enough for true karaoke highlighting |
| **libass** via FFmpeg `subtitles=` | ISC/GPL | ASS `\k` karaoke tags, per-word colour, outlines, shadows, positioning |
| FFmpeg 8.0 `whisper` filter | LGPL/GPL | Built-in ASR as of FFmpeg 8.0 — simpler path when you don't need wav2vec2 precision |

Align against **your own script text** (you already know the words — this is forced alignment, not transcription), which makes it near-perfect rather than ASR-accurate.

### 4.4 Generative B-roll — new

| Tool | License | Notes |
| --- | --- | --- |
| **Wan 2.2** | **Apache 2.0** | Best photoreal humans among open models; runs from **8GB VRAM** (5B GGUF + offload) |
| **LTX-2.3** (Lightricks) | check current | Only open model with **native synced audio** in one diffusion pass; 4K/50fps |
| **HunyuanVideo 1.5** | check current | Best physics/cloth/fluid; ~14GB VRAM with FP8 + offload |
| **Qwen-Image** | **Apache 2.0** | Stills / plates. **Best in-image text rendering of any open model**, no revenue cap |
| FLUX.2 [klein] 4B | **Apache 2.0** | Alternative stills |
| ⚠️ FLUX.2 [dev] | Commercial licence required from BFL | Do not ship commercially without it |

**Hardware reality**: 16GB VRAM is the practical floor for meaningful model choice; 24GB runs everything current without compromise.

### 4.5 Script — replaces GPT4All

**Qwen3 family via Ollama (Apache 2.0)** — best quality/licence/size balance for local generation in 2026; Gemma 4 as the alternative. Sizing: 16GB → Gemma 4 12B; 32GB → Qwen3.6-35B-A3B; 48–64GB → Qwen3.8 27B.

Use it as a **constrained rewriter, not an author**: it receives verified claims + citations and returns structured JSON conforming to a schema. It never invents a medical fact (§7.1).

### 4.6 Finishing & orchestration

| Concern | Tool | Note |
| --- | --- | --- |
| Encode/filter/master | **FFmpeg 8.1** | 8.0 added the `whisper` filter + Vulkan AV1 encode; 8.1 (Mar 2026) added D3D12 H.264/AV1 encode and GPU `scale_d3d12` |
| Audio analysis / beat map | **librosa** | Onset + tempo → beat-synced cutting |
| Editorial handoff | **OpenTimelineIO** | Export EDL → open in Resolve/Kdenlive for manual polish |
| Quality gate | **VMAF**, `ffprobe`, `ebur128` | Automated QC before publish |
| Orchestration | Python DAG + content-addressed cache | Start here. Visual tools only if you want them |
| — if visual | **Activepieces (MIT)** over ⚠️ **n8n (Sustainable Use Licence — source-available, not OSI-open)** | n8n forbids reselling as a hosted service |

---

## 5. The craft layer — what actually makes it look expert

Tools are necessary and nowhere near sufficient. These nine rules are the difference. **Encode them as defaults in the motion library, not as guidance in a README.**

### 5.1 Easing — never linear, ever

Linear motion is the #1 tell of generated video. Defaults to hard-code:

| Motion | Curve | Duration |
| --- | --- | --- |
| Text/element entrance | `expo.out` or `cubic.out` | 350–450ms |
| Exit | `cubic.in` | 200–250ms |
| Emphasis / pop | `back.out(1.4)` | 300ms |
| Counters, number roll | `expo.out` | 900–1200ms |
| Camera / background drift | `sine.inOut`, continuous | 8–20s |

**Overlap, don't queue.** Stagger sibling elements by **60–90ms**. Simultaneous entrances read as a slide; staggered entrances read as choreography.

### 5.2 Motion blur

Sub-frame sampling (render 4–8 subframes, accumulate) on any element moving >600px/s. Blender gives it natively; in Tier A implement as an accumulation pass. This is the single most underrated "why does theirs look expensive" factor.

### 5.3 Karaoke captions with a real type system

Word-level highlight, 2–4 words on screen, weight or colour shift on the active word, **not** a static SRT block. Burn via libass ASS `\k` tags. Respect platform safe areas: **top ~12% and bottom ~20% of a 9:16 frame are covered by platform UI** — captions live in the middle third, nudged low.

### 5.4 Beat-synced editing

Cut, accent, and land entrances on `librosa` beat positions. Snap every scene boundary to the nearest beat within ±120ms. Free rhythm; costs nothing.

### 5.5 Variable-font kinetic typography

Animate the `wght` and `wdth` axes, not just position and opacity. A word that thickens as it lands has weight (literally). Requires variable fonts — Google Fonts ships many, all OFL.

### 5.6 Audio mastering to spec

Two-pass FFmpeg `loudnorm`, targeting **I=-14 LUFS, TP=-1.5 dBTP, LRA=11** (YouTube/Spotify normalise to -14). Duck music under VO with **`sidechaincompress`**, not a static volume multiplier — ducking must breathe with the voice.

```bash
# pass 1 measures, pass 2 applies with measured_* values
ffmpeg -i mix.wav -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -
```

### 5.7 One grade, applied everywhere

A single 3D LUT via FFmpeg `lut3d` across every shot — generated B-roll, stills, and Tier A vector output alike. Nothing shouts "assembled from parts" louder than three colour temperatures in forty seconds.

### 5.8 Brand tokens as a file

`brand/health-v2.json`: colour ramp, type scale, spacing grid, **timing scale**, easing set, corner radii, shadow spec. Every scene reads from it. This is what makes fifty videos look like one studio made them — and it is how you resell the system to a client under their tokens.

### 5.9 Compose in 4K, deliver down

Author at 2160×3840, downscale with `lanczos` for delivery. Downsampled text and vector edges are dramatically cleaner, and it future-proofs the masters.

---

## 6. Phased plan

Each phase ends with something renderable. No phase is longer than about a fortnight of focused work.

### Phase 1 — Foundation & the seam
- Repo scaffold; content-addressed cache (`hash(inputs) → artifact`); Python DAG runner
- Scene-spec JSON schema + validator
- Brand token file + loader
- **Exit**: `main.py --topic X` emits a valid, reviewable `scene-spec.json`. No pixels yet.

### Phase 2 — Content layer
- Research with citation capture (Wikipedia + PubMed via `pymed`)
- Claim extraction → **verification gate** (§7.1) → Qwen3 constrained rewrite into script JSON
- Kokoro draft VO + Chatterbox-Turbo final behind one interface
- WhisperX forced alignment → word timings; librosa → beat map
- **Exit**: spec fully populated with audio, word timings, beats, citations.

### Phase 3 — Tier A motion engine
- Motion Canvas project; spec → scene compiler
- Component library: statement card, stat counter, list reveal, quote, lower third, end card
- Easing/stagger/motion-blur defaults from §5.1–5.2 baked in
- **Exit**: first full 9:16 render that looks *deliberate*.

### Phase 4 — Finishing
- libass karaoke captions with safe areas
- Two-pass loudnorm + sidechain ducking
- LUT grade; 9:16 / 1:1 / 16:9 encode ladder
- QC gates: duration, loudness, safe-area, VMAF, contact sheet
- OpenTimelineIO export
- **Exit**: publishable master + a Resolve-openable timeline.

### Phase 5 — Tier B + publishing
- Blender headless hero-shot renderer (3D anatomy / product / logo), composited into Tier A
- Optional Wan 2.2 / LTX-2.3 B-roll with a strict prompt template locked to the brand grade
- YouTube Data API auto-publish; TikTok via **draft mode**; Instagram staged for manual post
- Scheduling
- **Exit**: topic in → published Short out, with a human approval gate on medical claims.

---

## 7. Risk register

### 7.1 🔴 Health content liability — the biggest risk here

Auto-generated medical claims published at scale is a genuine legal, ethical, and platform-policy exposure. Health is YMYL ("Your Money or Your Life") content: platforms demote it aggressively, and wrong advice can hurt people. **v1 does not mention this at all.**

Required controls, built as pipeline gates rather than good intentions:

1. **Every factual claim carries a citation** to PubMed / WHO / NHS / CDC. Claims that fail to resolve to a source are dropped, not softened.
2. **The LLM never authors facts.** It rewrites verified claims into script form under a JSON schema. Temperature low. Any output claim not traceable to an input citation fails validation and blocks the render.
3. **Hard-blocked categories**: dosages, drug interactions, diagnosis, "cures", supplements with therapeutic claims, anything implying treatment.
4. **Human sign-off gate before publish** on any video containing a health claim. The automation ends at "ready to post"; a person presses publish.
5. **On-screen and in-description disclaimer**, plus source citations in the description.

This costs perhaps two days of work and is the difference between a portfolio piece and a liability.

### 7.2 🟠 Licence drift
Model licences change between releases (FLUX is the cautionary tale). **Record the exact licence + model revision hash in `metadata.json` for every render.** Re-verify on the Hugging Face page before any commercial deployment.

### 7.3 🟠 Platform API friction
- **Instagram**: Business/Creator account + Meta app + `instagram_business_content_publish` App Review (screencast per scope, 5+ business days, rejections need resubmission). Rate limits tightened hard in 2025: **200 API calls/hour per account**, **100 published posts / rolling 24h**. Personal accounts cannot publish via API at all.
- **TikTok**: Content Posting API supports **Direct Post** and an inbox/draft mode. Ship draft mode first — it is far more forgiving.
- **YouTube**: cleanest path; OAuth2 + Data API. Automate this one first.
- ❌ **Never** use `instagrapi`, Selenium uploaders, or similar unofficial automation. Terms-of-service violation, and it will get the account banned.

### 7.4 🟡 Hardware
16GB VRAM floor for generative B-roll, 24GB for comfort. Everything else (Motion Canvas, FFmpeg, Kokoro, WhisperX, ACE-Step) runs comfortably below that — **Phases 1–4 need no GPU at all**, which is why generative video is deliberately last.

### 7.5 🟡 Revideo maintenance
Upstream work has moved to commercial Midrender. Mitigation already stated: author in vanilla Motion Canvas idiom, treat Revideo as a swappable renderer.

---

## 8. What changes vs. v1, at a glance

| Stage | v1 | v2 |
| --- | --- | --- |
| Script LLM | GPT4All | Qwen3 via Ollama, **constrained rewriter + citation gate** |
| TTS | Coqui `tacotron2-DDC` | **Kokoro** (draft) + **Chatterbox-Turbo** (final) |
| Animation | MoviePy `TextClip` | **Motion Canvas** (MIT) + **Blender** hero shots |
| Text rendering | ImageMagick via TextClip | Native scene graph; **no ImageMagick dependency** |
| Captions | — | **WhisperX + libass karaoke** |
| Music | Folder of CC tracks | **ACE-Step 1.5**, generated per video |
| Audio mix | `pydub` volume multiply | **Two-pass loudnorm + sidechain ducking** |
| Colour | — | **Single LUT grade across all sources** |
| Editing | MoviePy composite | FFmpeg conform + **OpenTimelineIO** handoff |
| Orchestration | Cron | **DAG + content-addressed cache**, then cron |
| QC | — | **Loudness / safe-area / VMAF / duration gates** |
| Compliance | — | **Citation gate + human sign-off** |

---

## 9. Decisions needed before Phase 1

1. **Tier A engine** — Motion Canvas (recommended, MIT) or Remotion (better ecosystem, needs a paid licence the moment the studio exceeds 3 people)?
2. **Node vs Python for the motion layer** — Tier A is TypeScript either way. Confirm that split is acceptable, or we go Blender-only and stay pure Python (slower to author 2D, higher ceiling in 3D).
3. **GPU available?** Determines whether Phase 5 generative B-roll is in scope or deferred.
4. **Brand tokens** — do you have an existing palette/type system to encode, or should Phase 1 propose one?
5. **AE Motion Engine** — keep After Effects as Tier C for hero set-pieces? It is not open-source, so it sits outside the stated constraint, but you already own the rig and it beats everything here on bespoke work.

---

## 10. Sources

Licensing and capability claims above were verified against these, September 2026:

- [Remotion LICENSE.md](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) · [Remotion License FAQ](https://www.remotion.dev/docs/license/faq)
- [Motion Canvas](https://github.com/motion-canvas/motion-canvas) · [Revideo](https://github.com/midrender/revideo) · [The next chapter of Revideo](https://midrender.com/revideo)
- [Remotion vs Motion Canvas vs Revideo (PkgPulse)](https://www.pkgpulse.com/blog/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026)
- [Best Open Source TTS 2026 (Speakeasy)](https://www.tryspeakeasy.io/blog/open-source-text-to-speech-2026) · [Open-source TTS comparison (BentoML)](https://www.bentoml.com/blog/exploring-the-world-of-open-source-text-to-speech-models)
- [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) · [Open-source music generation guide (Spheron)](https://www.spheron.network/blog/deploy-open-source-ai-music-generation-gpu-cloud-2026/)
- [WhisperX](https://github.com/m-bain/whisperx)
- [Open-source video models 2026 (Thunder Compute)](https://www.thundercompute.com/blog/best-open-source-ai-video-generation-models) · [LTX open-source landscape guide](https://ltx.io/blog/open-source-video-generation-models-guide)
- [Open-source image models 2026 (BentoML)](https://www.bentoml.com/blog/a-guide-to-open-source-image-generation-models)
- [Best open-weight LLMs to run locally (Hugging Face)](https://huggingface.co/blog/daya-shankar/open-source-llm-models-to-run-locally)
- [FFmpeg 8.0 release (Phoronix)](https://www.phoronix.com/news/FFmpeg-8.0) · [FFmpeg 8.1 GPU acceleration](https://en.linuxadictos.com/ffmpeg-8-1-da-un-salto-en-aceleracion-gpu-metadatos-y-nuevos-codecs.html)
- [FFmpeg loudnorm / EBU R128 guide](https://ffmpeg-cookbook.com/en/articles/loudness-normalization/)
- [Blender programmatic rendering (CGWire)](https://blog.cg-wire.com/blender-programmatic-rendering/)
- [n8n vs Activepieces licensing](https://automationatlas.io/answers/n8n-vs-activepieces-2026/)
- [Social media API rules & limits 2026 (Postproxy)](https://postproxy.dev/blog/social-media-platform-api-rules-rate-limits-media-specs/) · [TikTok Content Posting API 2026](https://www.netrows.com/blog/tiktok-content-posting-api-guide-2026)

> Licences change between model releases. Re-verify on the source's own page before any commercial deployment.
