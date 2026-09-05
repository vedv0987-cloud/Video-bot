# VIDEO STUDIO — TECHNICAL MASTER PLAN

**Status**: proposal, for approval before implementation · **Date**: September 2026
**Scope**: local-first AI video production, editing and publishing studio
**Primary machine**: MacBook Air · Apple M5 · 10-core CPU / 8-core GPU · 16 GB unified

> Nothing in this document has been run on the target machine. Claude Code sessions
> execute in a Linux container with no GPU and no path to your Mac. Every hardware
> number below is either quoted from your report or specified as something the
> **hardware-detection module must measure at runtime** (§4). Benchmarks are
> deliverables, not assumptions.

---

## 0. Executive summary — read this first

**Roughly 40% of the hard architecture already exists in this repository and is
directly reusable.** The content layer (research → citations → safety → script →
voice → alignment → beats → deterministic scene spec) is built, tested and merged:
118 Python tests, live retrieval, a working compliance gate, a content-addressed
cache with real resumability, and an MP4 coming out of the other end.

That matters because you identified the three things that separate a professional
system from "an LLM wrote a script and put stock videos behind it":

| Your requirement | Status |
| --- | --- |
| Deterministic scene specification | **Built.** `scene-spec.json`, JSON-Schema'd, semantically validated |
| AI Director / storyboard | **Not built.** The largest single gap |
| Intelligent footage selection | **Not built.** Commons only, opportunistic |

The plan below reuses the first, builds the second and third, and swaps the motion
engine.

**Five findings that change the plan and that you need to decide on:**

1. **Remotion is free for you today and priced by headcount, not usage.** Free for
   individuals and organisations of **up to 3 people**; **$25/seat/month at 4+**. The
   trigger is company size, not how many people touch it. You are compliant as a solo
   studio. This repo currently uses Motion Canvas (MIT) *specifically* to avoid that
   trigger. Moving to Remotion is a deliberate licence trade — see §22 for why I still
   recommend it.
2. **YouTube will force every upload private until your API project is audited.** Any
   unverified project created after 28 July 2020 has `videos.insert` results restricted
   to private. This is not a bug to code around; it is a Google audit you must apply
   for. Budget weeks.
3. **Instagram cannot schedule Reels through the API.** There is no
   `scheduled_publish_time` on the Reels publish call. "Scheduling" must be our own
   scheduler waking at the target time and firing the publish. Plus a 2–4 week app
   review per permission, and a Business/Creator account linked to a Facebook Page.
4. **Veo 3.1 has no free API tier, and your consumer Google AI Pro subscription is not
   API access.** Programmatic generation is paid from the first clip: roughly
   **$0.64–0.96 per 8-second 1080p clip**. A 6-minute video that is 20% generated
   footage is ~72s of Veo ≈ 9 clips ≈ **$6–9 per render**. That is a per-video unit
   cost, and it must be surfaced in the UI before generation, not after.
5. **Local generative video is out on this machine.** Measured community results on
   Apple Silicon: ~82 minutes for a 2-second clip on an M1 Max/64 GB, LTX-2 fp8 failing
   on Metal. Generated footage means the Veo API or rented NVIDIA — not the Air.

---

## 1. Existing repository analysis

```
src/videobot/           2,586 lines Python, 118 tests
├── cli.py              entry point, backend selection
├── cache.py            content-addressed artifact cache
├── dag.py              node graph + runner, topological, per-node force
├── spec.py             scene-spec validation + craft linting
├── safety.py           blocked-category screen for health claims
├── brand.py            design tokens, digest-pinned
├── platforms.py        delivery formats, platform safe areas
├── http.py             throttled, retrying stdlib client
├── schema/             JSON Schemas as package data
├── sources/            wikipedia · pubmed · commons
└── nodes/              research → script → media → voice → align → beats → compose

motion/                 22 TS files, 18 tests — Motion Canvas
├── src/lib/compile.ts  spec → engine-independent render plan
├── src/lib/render.tsx  interpreter: plan → scene graph
├── src/lib/backgrounds procedural: gradient mesh · particle field · grid lines
├── src/components/     kinetic text · counter · list · lower third · end card
└── scripts/render.mjs  frames → ffmpeg → MP4 (grain, EBU R128, h264)
```

### What to keep, unchanged

| Module | Why it survives |
| --- | --- |
| `cache.py`, `dag.py` | Content-addressed resumability is exactly your §40 requirement, already working. Recomputing a node to identical bytes leaves downstream cached. |
| `sources/`, `safety.py` | Live citation capture with pinned source ids, and a blocked-category screen. This is your §9 and §57. |
| `spec.py` + schemas | The deterministic scene specification you called out as decisive. |
| `brand.py`, `platforms.py` | Design tokens and safe areas, already digest-pinned. |
| `audio/` interfaces | TTS/aligner/beats provider abstractions — your §29 and §61, already in place. |
| `motion/src/lib/compile.ts` | Engine-independent by design. Port it to Remotion props; the logic survives. |

### What to replace

| Module | Replaced by | Why |
| --- | --- | --- |
| `motion/src/lib/render.tsx` + components | Remotion compositions | No embeddable player in Motion Canvas; §6 needs a live scrubbing preview in the dashboard |
| `nodes/script.py` template rewriter | LLM script service | A template cannot write a 6-minute documentary |
| `nodes/media.py` | Asset Acquisition Engine | Commons-only, no ranking, no clip extraction |
| `cli.py` as the only entry | Job service + HTTP API | A CLI cannot drive a dashboard |

### What is missing entirely

AI Director · storyboard · footage ranking · clip extraction · generative video ·
image generation · thumbnails · charts · maps · music · SFX · audio mixing beyond
loudnorm · database · job queue · dashboard · editor · versioning · publishing ·
scheduling · analytics · brand kit · content memory · multi-aspect composition ·
Shorts extraction.

---

## 2. Machine analysis and hardware detection

Reported: MacBook Air, Apple M5, 10-core CPU, 8-core GPU, 16 GB unified, macOS 26.6.2,
286 GB free.

Two properties drive every decision:

**16 GB unified is the binding constraint.** macOS plus your open apps take 4–6 GB,
leaving ~10 GB. Chromium instances under Remotion are the largest consumer; each
concurrent renderer holds a full page context plus decoded frames.

**The Air is passively cooled.** It sprints, then throttles. The correct target is
sustained throughput with a responsive machine, not peak utilisation.

### `packages/hardware` — must measure, never assume

| Signal | Source | Used for |
| --- | --- | --- |
| chip, CPU cores, GPU cores | `sysctl -n machdep.cpu.brand_string`, `system_profiler SPHardwareDataType -json` | concurrency ceiling |
| unified memory, free memory | `sysctl hw.memsize`, `vm_stat` | worker count, proxy decisions |
| architecture (arm64 vs Rosetta) | `process.arch`, `sysctl.proc_translated` | **critical** — Remotion under Rosetta is up to 2× slower |
| free disk | `statfs` | cache policy, render guard |
| macOS version | `sw_vers` | VideoToolbox feature set |
| Node, Python, Chromium, Remotion | `--version` probes | compatibility gate |
| ffmpeg build + encoders | `ffmpeg -encoders` | must contain `libx264` **and** `h264_videotoolbox` |
| VideoToolbox availability | trial encode of 10 synthetic frames | hardware encode decision |

The Rosetta check is not optional. A Node installed under x64 emulation silently halves
render speed and nothing in the output says so.

---

## 3. Product requirements and user workflow

```
Topic ─▶ options ─▶ GENERATE ─▶ [research · script · direct · storyboard ·
        assets · voice · graphics · compose · render · validate] ─▶ preview
        ─▶ download / recreate / edit ─▶ metadata + thumbnail ─▶ publish
```

Two modes, both first-class:

- **Full auto** — one click, no interruption.
- **Review mode** — approval gates after research, script, storyboard and video. This
  is the mode I would default to for anything factual, and the one that makes the
  compliance gate meaningful.

---

## 4. System architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  apps/studio            Next.js 15 · React 19 · TypeScript       │
│  dashboard · create · projects · editor · publishing · settings  │
│  @remotion/player for live preview and scrubbing                 │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP (localhost) + SSE for job progress
┌───────────────────────────▼──────────────────────────────────────┐
│  apps/server            Node · Fastify · SQLite (Drizzle)        │
│  ├── job runner        in-process, SQLite-backed, resumable      │
│  ├── resource manager  semaphores: render / ffmpeg / tts / net   │
│  └── services/         research script director assets tts music │
│                        graphics render thumbnail publish         │
└──────┬──────────────────────────────┬────────────────────────────┘
       │ child process (JSON contract) │ child process
┌──────▼──────────────┐        ┌───────▼──────────────────────────┐
│  content layer      │        │  packages/compositions           │
│  (existing Python)  │        │  Remotion · React · SVG          │
│  research · safety  │        │  renders frames → ffmpeg → MP4   │
│  citations · script │        │                                   │
│  → scene-spec.json  │        │                                   │
└─────────────────────┘        └───────────────────────────────────┘
```

### Why the Python layer stays

The research, citation-pinning, safety-screening and claim-invariant code is the part
of this system that is hardest to get right and easiest to get subtly wrong. It is
built, it is tested, and it is already contract-bound to the rest by a JSON file. The
boundary is a child process and a schema — the same seam that let the motion engine be
swapped without touching content.

The alternative — porting ~2,600 lines of tested logic to TypeScript for language
uniformity — buys tidiness and risks the safety properties. Revisit after MVP, not
before.

---

## 5. Folder structure

```
video-studio/
├── apps/
│   ├── studio/              Next.js dashboard
│   └── server/              Fastify API + job runner + services
├── packages/
│   ├── compositions/        Remotion project (the motion system)
│   ├── core/                shared types, scene-spec TS bindings, zod schemas
│   ├── hardware/            detection + benchmark harness
│   ├── providers/           asset · tts · image · video · music · publish adapters
│   └── db/                  Drizzle schema + migrations
├── content/                 the existing Python package (renamed from src/videobot)
├── data/
│   ├── projects/<id>/       project files, renders, proxies
│   ├── cache/               content-addressed assets, TTS, research
│   └── logs/
└── docs/
```

---

## 6. Database schema

SQLite via Drizzle. Local-first, single user, no daemon, real migrations, and it
handles the concurrency of one desktop app comfortably. Postgres only becomes right if
this ever becomes multi-user or hosted.

```
users                 id, name, settings_json
brands                id, name, tokens_json, logo_path, intro_path, outro_path
projects              id, title, topic, description, language, platform,
                      aspect, resolution, target_duration_s, brand_id,
                      mode(auto|review), status, created_at, updated_at
project_versions      id, project_id, n, spec_json, storyboard_json,
                      parent_version_id, label, created_at
scenes                id, version_id, idx, narration, duration_s, visual_type,
                      visual_intent, transition, music_intensity, sfx, spec_json
assets                id, provider, provider_asset_id, kind(video|image|audio),
                      source_url, creator, licence, attribution_required,
                      width, height, duration_s, file_path, sha256, phash,
                      downloaded_at, bytes
clips                 id, asset_id, scene_id, start_s, end_s, crop_json, speed
asset_usages          id, project_id, asset_id, scene_id   -- the licence ledger
audio_tracks          id, version_id, kind(vo|music|sfx), file_path, duration_s,
                      lufs, provider, licence, asset_id
captions              id, version_id, words_json, style
renders               id, version_id, preset, aspect, width, height, fps,
                      file_path, bytes, duration_s, encoder, render_s, status
thumbnails            id, version_id, provider, concept, prompt, file_path,
                      width, height, selected, created_at
jobs                  id, project_id, version_id, type, state, stage,
                      progress, attempts, error_json, started_at, finished_at
job_steps             id, job_id, stage, state, input_digest, output_digest,
                      cache_hit, duration_ms, error_json
accounts              id, platform, external_id, display_name, scopes,
                      token_ciphertext, refresh_ciphertext, expires_at, status
publish_jobs          id, version_id, render_id, account_id, state,
                      scheduled_for, published_at, remote_id, error_json
analytics_snapshots   id, publish_job_id, captured_at, metrics_json
settings              key, value_json
benchmarks            id, machine_fingerprint, preset, concurrency, encoder,
                      render_s, fps, peak_rss_mb, created_at
```

`job_steps.input_digest` is the resumability primitive: it is the same content-address
the existing Python cache uses, promoted into the database so the UI can show which
stages were reused.

---

## 7. Job and worker architecture

```
QUEUED → RESEARCHING → SCRIPTING → DIRECTING → PLANNING_SCENES →
FETCHING_ASSETS → GENERATING_VOICE → GENERATING_GRAPHICS → COMPOSING →
RENDERING → VALIDATING → COMPLETED
                    ↘ FAILED · CANCELLED · PAUSED · RETRYING
```

- **In-process runner, SQLite-backed.** No Redis, no external broker. This is a
  desktop app; a broker is operational weight with no benefit.
- **Every stage is a step row** with an input digest. Re-running a job skips steps whose
  inputs are unchanged. Scene 18 failing re-runs scene 18.
- **Progress is real or absent.** Remotion emits `onProgress` with rendered frame
  counts; ffmpeg emits frame/time on stderr. Where a stage cannot report granular
  progress it shows as indeterminate rather than a fabricated percentage.
- **Structured errors** throughout: `{stage, code, message, retryable, context}`.
- Retry policy: network and provider 5xx/429 retry with exponential backoff and jitter
  (3 attempts); 4xx other than 429 never retries; render OOM retries once at reduced
  concurrency, then fails with a specific code.

### Resource manager

Weighted semaphores over a single budget, sized from `packages/hardware`:

| Resource | Default on 16 GB M5 | Rationale |
| --- | --- | --- |
| Concurrent renders | 1 | A second render doubles Chromium memory for sub-linear gain |
| Remotion concurrency (workers within a render) | benchmark; start at 4 | Half the cores. Too high is as bad as too low |
| ffmpeg processes | 2 | One encode, one proxy/probe |
| TTS processes | 1 | Model load dominates; parallel loads thrash |
| Asset downloads | 4 | Network-bound, cheap |
| Image processing | 2 | sharp is fast, memory is the limit |

A render must not start when free memory is under a floor (default 3 GB) or free disk
under 10 GB — it fails fast with an actionable message rather than swapping the machine
to a halt.

---

## 8. The video pipeline, stage by stage

| Stage | Input | Output | Technology | Retry | Cached |
| --- | --- | --- | --- | --- | --- |
| Research | topic | claims + pinned citations | existing Python: Wikipedia REST, PubMed E-utils, +Tavily/Brave for general topics | yes | yes |
| Fact screen | claims | screened claims + rejections | `safety.py` | n/a | yes |
| Outline | claims, duration | section plan | LLM (structured output) | yes | yes |
| Script | outline, claims | narration per section | LLM + `assert_no_invented_claims` | yes | yes |
| **Direct** | script | shot list: visual type, intent, duration, emphasis per beat | LLM (structured output) | yes | yes |
| Storyboard | shot list | `scene-spec.json` | compose service | yes | yes |
| Asset search | visual intents | ranked candidates | Pexels → Pixabay → Commons → Archive | yes | yes |
| Asset download | candidates | files + metadata + proxies | undici + sharp + ffmpeg | yes | yes (sha256 + phash) |
| Clip selection | assets, scene | `{asset, start, end}` | heuristic + optional CLIP scoring | yes | yes |
| Generative video | prompts | clips | Veo 3.1 via Gemini API | yes | yes (**paid**) |
| Voice | script | WAV + timings | Kokoro / Chatterbox / external | yes | yes |
| Alignment | WAV + text | word timings | WhisperX / mlx-whisper | yes | yes |
| Music | mood, duration | track + licence | Pixabay Music → local library → ACE-Step | yes | yes |
| Graphics | scene spec | React components | Remotion (render-time) | n/a | n/a |
| Compose | everything | Remotion props | compose service | yes | yes |
| Render | props | frame stream / MP4 | Remotion renderer | yes | per-scene |
| Mix | vo, music, sfx | mastered audio | ffmpeg sidechain + loudnorm | yes | yes |
| Validate | MP4 | QC report | ffprobe, ebur128, frame stats | yes | no |
| Thumbnail | video + script | 3–5 candidates | Imagen via Gemini API / frames + typography | yes | yes |
| Metadata | script | title/description/tags/caption | LLM | yes | yes |
| Publish | render + metadata | remote id | YouTube Data API / Instagram Graph API | yes | no |

---

## 9. AI Director — the biggest missing piece

This is what separates a professional automated editor from stock footage behind
narration. It runs **after** the script and **before** any asset work.

Input: the script, its claims and citations, target duration, platform, visual style.
Output: a shot list — a sequence of beats, each with an intent and a chosen medium.

```jsonc
{
  "scene": "fusion-history",
  "narration": "Scientists have spent decades trying to recreate the reaction that powers the Sun.",
  "duration_s": 7.4,
  "beats": [
    { "at": 0.0, "dur": 3.1, "medium": "footage",
      "intent": "researchers working in a laboratory",
      "queries": ["scientist laboratory", "research lab equipment", "physicist working"],
      "shot": "medium", "motion": "slow push in" },
    { "at": 3.1, "dur": 2.4, "medium": "graphic",
      "intent": "fusion reaction diagram", "component": "Diagram",
      "props": { "kind": "fusion", "labels": ["deuterium", "tritium", "helium"] } },
    { "at": 5.5, "dur": 1.9, "medium": "kinetic-type",
      "intent": "emphasise the timescale", "text": "decades" }
  ],
  "transition": { "type": "dip", "dur": 0.28 },
  "music_intensity": 0.4,
  "sfx": [{ "at": 3.1, "kind": "whoosh" }]
}
```

**Rules the director must follow, enforced in code not prompt:**

- No beat longer than 6 seconds without motion or a cut. Static shots are how a video
  reads as a slideshow.
- Pacing derives from the *actual* voice duration, never from a character estimate. The
  director proposes durations; the compose stage rewrites them from the aligned audio.
- A statistic gets a chart, not a sentence on a card. If the director marks a beat as
  carrying a number, the compose stage requires a `chart` or `counter` component.
- Every claim beat inherits its citation. A beat with no traceable source cannot be a
  claim beat.
- Medium diversity: no more than two consecutive beats of the same medium.

The director is an LLM call with a strict schema and a validator that rejects
non-conforming output and retries with the errors appended. It is not "ask the model
for a storyboard and hope".

---

## 10. Asset Acquisition Engine

Assets and clips are separate concepts. This is the single decision that makes
recreation, editing, multi-aspect and render recovery tractable.

```
Asset   provider · provider_asset_id · source_url · creator · licence ·
        attribution_required · width · height · duration · file · sha256 · phash
Clip    asset_id · scene_id · start_s · end_s · crop · speed
```

We never cut a new giant file to represent a clip. ffmpeg seeks into the cached source
at render time.

### Provider chain and fallback

```
Pexels → Pixabay → Wikimedia Commons → Internet Archive → generated (Veo) →
motion graphic
```

A missing clip must never fail a project. The last link in that chain always succeeds.

| Provider | Licence | Attribution | Limits | Notes |
| --- | --- | --- | --- | --- |
| **Pexels** | Pexels licence, commercial OK | Not required, **encouraged** | 200 req/hr, 20k/month; **lifted free if you display attribution** | Primary. Best modern B-roll |
| **Pixabay** | Content Licence, commercial OK | Not required | 100 req / 60s | Secondary. Cannot redistribute standalone — irrelevant here, we add value |
| **Wikimedia Commons** | Per-asset; CC0/PD/BY/BY-SA only | **Required for BY / BY-SA** | Courtesy limits, 429s common | Already built, with licence + clinical-subject + shape filters |
| **Internet Archive** | Per-item, must be checked | Per-item | Courteous | Archival/historical only |

**We display attribution regardless.** It lifts the Pexels rate limit for free, it is
required by CC BY/BY-SA, and it is the honest thing to do. The renderer already draws
a credit line.

**YouTube is a research source, never a footage source.** Technically trivial to
download; legally not ours to reuse. It appears in this system only as a citation.

### Candidate ranking

Do not take the first result. Fetch ~20, score, take the best.

| Signal | Weight | How |
| --- | --- | --- |
| Semantic relevance | 0.35 | CLIP embedding of proxy frames vs the beat's intent text |
| Resolution adequacy | 0.15 | ≥ target, penalise gross overshoot (download cost) |
| Orientation match | 0.15 | portrait for 9:16, landscape for 16:9 |
| Motion suitability | 0.10 | frame-difference energy from the proxy |
| Duration fit | 0.10 | can it supply the beat length with headroom |
| Uniqueness | 0.10 | perceptual-hash distance from assets already in this project |
| Provider preference | 0.05 | tie-break |

CLIP scoring is a Phase 4 addition; the MVP ranks on the deterministic signals and is
still far better than "first result". Candidates are judged on a **low-res proxy**, not
the full download — download only the winner.

### Deduplication

sha256 for identity, perceptual hash for similarity. Ten scenes searching "city
skyline" download one file.

---

## 11. Motion graphics — Remotion

### The engine decision

| | Remotion | Motion Canvas (current) | Blender |
| --- | --- | --- | --- |
| Licence | Free ≤3 people, **$25/seat at 4+** | MIT | GPL |
| Embeddable player | **`@remotion/player`, React, scrubbing** | none | none |
| Ecosystem | Very large; charts, captions, media parsing | small | N/A for 2D |
| React component model | native | generator functions | Python |
| Your component list (§22) | maps directly | would be hand-built | wrong tool |

**Recommendation: Remotion.** The decisive factor is not animation quality — Motion
Canvas is genuinely good and already working here — it is `@remotion/player`. Your
dashboard requires a live, scrubbing, in-browser preview of the composition with a
timeline, and an editor that reflects edits immediately. Motion Canvas has no
embeddable player; building one is a project in itself.

**What this costs**: the licence trigger at 4 people, and a rewrite of
`motion/src/lib/render.tsx` plus the five components. **What it does not cost**:
`compile.ts` was written engine-independent precisely for this; the compiler, the
easing contract, the blur decision and the token resolution all port.

**Keep the Motion Canvas renderer in the repo** until Remotion parity is proven, then
delete it. Do not maintain two.

### Component library

Grouped by what they do, all driven from the design system, all sharing one easing set:

**Type** — Title · Subtitle · SectionTitle · KineticText · FullscreenText · Quote ·
Caption
**Structure** — LowerThird · Callout · IconLabel · Comparison · BeforeAfter
**Data** — StatCard · NumberCounter · BarChart · LineChart · PieChart · Timeline ·
ProgressIndicator
**Media** — ImageReveal · VideoReveal · KenBurns · MaskedReveal
**Geo** — MapMarker · MapRoute · RegionHighlight
**Frame** — LogoIntro · Outro · Watermark · Vignette · Grain

Charts are hand-built SVG with Remotion's `interpolate`, not a charting library
wrapped. Recharts and friends animate on mount with their own timing model, which
fights a frame-deterministic renderer and produces non-reproducible output. Data
visualisation here is a dozen small components we control.

Maps use **react-simple-maps** with **Natural Earth** topojson (public domain). No API
key, no tile licensing, no attribution obligation, and it renders deterministically.
Mapbox/Google tiles would be prettier and bring per-request billing plus attribution
requirements into a video pipeline.

### Design system

Extends the existing `brand/health-v2.json` schema. Spacing on an 8px grid, a type
ramp, one easing set, safe areas per platform, and motion tokens. Two rules carried
over from the current implementation and worth keeping:

- **Linear easing throws.** Enforced in the Python validator and in the renderer.
- **An animation with no declared travel distance throws**, because motion blur is a
  function of speed and a silent zero is the artefact it exists to prevent.

Typography: **Inter Variable**, self-hosted via `@fontsource-variable/inter`, with the
renderer awaiting `document.fonts.ready`. Canvas and DOM text both fall back silently;
an early render in this repo came out in Helvetica with no error.

Icons: **Lucide** (ISC) — one library, one stroke weight, one grid. Mixing icon sets is
the fastest way to make a professional piece look assembled.

---

## 12. Multi-aspect composition

One project, several outputs. Not a crop.

Each component declares behaviour per aspect: safe-area-relative position, scale ramp,
and whether it is present at all. A lower third that reads well at 16:9 may become a
centred card at 9:16. Footage gets a subject-aware crop window (face/saliency
detection where available, centre-weighted otherwise) rather than a centre crop that
decapitates people.

```
project ──┬─▶ 1920×1080  YouTube
          ├─▶ 1080×1920  Reels / Shorts
          └─▶ 1080×1080  feed
```

Shorts extraction (post-MVP) scores segments on hook strength, self-containment and
visual density, then re-renders those spans at 9:16 — not the first 60 seconds.

---

## 13. TTS, captions, music, audio

**TTS** — the existing provider abstraction stands. Kokoro (Apache-2.0, CPU-viable,
fast) for drafts; Chatterbox-Turbo (MIT) for finals, on the CPU path on Apple Silicon
where MPS is unreliable. At ~30–60s of narration that is seconds of compute either way.
External providers slot in as adapters.

**Alignment** — WhisperX for word timings; `mlx-whisper` as the Apple-native
alternative. The value is the wav2vec2 *forced alignment*, not the transcription — any
substitute must return word boundaries. Provenance records which method ran, so an
estimate can never be mistaken for a measurement.

**Captions** — driven from the alignment already in the spec. Burned in at render, with
a karaoke highlight. The current implementation makes the on-screen card *be* the
caption for statement scenes rather than duplicating text in a strip; for documentary
16:9 with footage behind, a proper bottom-band caption is the right form. Both live in
the component library, chosen by the director.

**Music** — Pixabay Music via API (Content Licence, no attribution, commercial OK) as
primary; a curated local library as fallback; ACE-Step 1.5 (Apache-2.0) generation
later, which removes the licensing question entirely. Music intensity comes from the
director per scene.

**SFX** — Freesound API (per-asset CC licences, must be filtered exactly like Commons)
and Pixabay. Placed on director-declared events only. Restraint is the whole skill
here.

**Mixing** — ffmpeg. Narration normalised, music **sidechain-compressed** against the
voice (not a static volume multiply — ducking must breathe), fades, then a final
two-pass `loudnorm` to **I=-14 LUFS, TP=-1.5 dBTP, LRA=11**. Verified with `ebur128` in
QC.

---

## 14. Rendering strategy and Apple Silicon

```
Remotion renderMedia
  └─ Chromium (arm64, native — verify, Rosetta is up to 2× slower)
     └─ frames → ffmpeg
        ├─ h264_videotoolbox   hardware, fast, larger files at equal quality
        └─ libx264             software, better quality per bit, slower
```

**Presets**

| Preset | Resolution | Encoder | Use |
| --- | --- | --- | --- |
| Preview | 480×854 / 854×480 | videotoolbox | scrub in dashboard |
| Draft | 720p | videotoolbox | review pass |
| Final | 1080p | libx264 CRF 19, preset medium | delivery |
| High | 1080p | libx264 CRF 17, preset slow | archival |

VideoToolbox is the right default for previews and drafts, where speed dominates.
libx264 is the right default for delivery, where quality per bit dominates and the
render is an overnight job anyway. **This is a hypothesis to be benchmarked, not a
conclusion** — §16.

**Per-scene rendering** is the unit. Render scene ranges to intermediate files,
concatenate. That gives render recovery (scene 38 fails → re-render 38, not 1–52), and
it caps peak memory.

---

## 15. Caching, disk and proxies

Content-addressed throughout, extending what exists. Keys are digests of inputs, never
timestamps. A build timestamp inside a cached artifact changes its digest every run and
silently kills the cache — this repo learned that one already.

```
data/cache/
├── research/     topic + source-set digest
├── script/       + model + prompt version
├── tts/          text + voice + model
├── assets/       sha256 of file bytes
├── proxies/      asset sha256 + proxy profile
└── scenes/       scene spec digest + preset
```

Proxies matter more here than anywhere: previewing 4K source on a 16 GB machine is how
you make the dashboard unusable. Downloaded source → 540p proxy → editor and preview
use the proxy → final render seeks the original.

Disk policy: warn under 20 GB, block renders under 10 GB, cache eviction is LRU over
`assets/` and `proxies/` only, and **project assets are never deleted without
confirmation**.

---

## 16. Benchmarking — a deliverable, not an assumption

`packages/hardware` ships a benchmark harness and a standard project: 75 seconds,
stock footage, generated graphics, SVG charts, captions, voiceover, music, transitions,
1080p.

Run the matrix, record to the `benchmarks` table, and derive defaults:

- Remotion concurrency: 1, 2, 4, 6, 8, 10
- Encoder: `libx264` (medium, slow) vs `h264_videotoolbox`
- Scene-parallel vs sequential
- Cold vs warm cache

Capture: wall time, average FPS, peak RSS, output size, VideoToolbox engagement, and
**thermal behaviour across three consecutive runs** — the third run on a passively
cooled Air is the number that matters, not the first.

Defaults ship from measurement. Where a measurement is missing, the code uses a
conservative value and says so in the log.

---

## 17. Thumbnails

First-class, never a random frame.

```
script + storyboard + rendered video
   ↓ identify the curiosity hook (LLM, from the script — not the title)
   ↓ extract candidate frames (scene-change detection, face/subject scoring, sharpness)
   ↓ generate concepts: 3–5 meaningfully different compositions
   ↓ provider: Imagen via Gemini API │ frame + typography │ template fallback
   ↓ brand kit applied
   ↓ validate at 168×94 — if the text is unreadable at that size it has failed
   ↓ user selects → stored, versioned → uploaded on publish
```

`ThumbnailProvider` is an interface with a template fallback that always succeeds.
Thumbnail failure must never block the video.

---

## 18. Publishing — the real constraints

### YouTube

Official Data API v3, OAuth 2.0, `videos.insert` resumable upload,
`thumbnails.set`, `status.publishAt` for scheduling.

**The blocker you must plan around:** every video uploaded via `videos.insert` from an
**unverified API project created after 28 July 2020 is forced to private**, regardless
of the privacy status you request. Lifting it requires a Google API audit of the
project. The UI must show verification status and must not offer "publish public" as if
it will work before the audit passes. Uploads sit at ~100/day in the current quota
model (uploads were moved out of the shared pool in June 2026).

Tokens: OS keychain via `keytar`, never in the database in plaintext, never in the
frontend. Refresh handled server-side.

### Instagram

Instagram Graph API, Business or Creator account linked to a Facebook Page, Meta app
review per permission (`instagram_business_content_publish`), 2–4 weeks per submission
with a screencast.

**Two hard constraints:**

1. **No API scheduling for Reels.** There is no `scheduled_publish_time` on the publish
   call. Our scheduler holds the job, wakes at the target time, re-checks the container,
   and fires. Present it as "we will publish at this time", never as
   "Instagram will publish this later" — those are different reliability stories and
   the user should know which one they have.
2. **Rate limits are low and were tightened.** ~200 API calls/hour per account, and
   published posts capped per rolling 24 hours (sources disagree between 25 and 100 —
   treat 25 as the planning number and read the live header).

Reels requirements: 9:16, 5–90s, H.264/HEVC, AAC. The container flow is create → poll
until `FINISHED` → publish. Polling is mandatory; publishing an unfinished container
fails.

### Never
Automating a consumer web UI for either platform. It violates terms, breaks silently,
and risks the account.

---

## 19. Smart publishing time

No universal "viral hour". The recommendation is derived and explained:

```
account timezone
+ historical performance of this channel's own posts (YouTube Analytics API)
+ audience-activity windows where the platform exposes them
+ day-of-week and format priors
→ recommended slot + the reason + confidence
```

With no history, say so: "No history yet — this is a general prior for your timezone,
not a prediction." Always overridable.

---

## 20. Licensing ledger and content safety

Every project answers "where did this come from?" `asset_usages` joins project → asset
→ licence, and exports a per-project **Licence Report**: every clip, image, track,
sound, font and icon with creator, licence, source URL and attribution requirement.

Pre-publish content checks, extending the existing gate: unsourced claim detection,
the blocked-category screen (dosages, named drugs, diagnosis, treatment framing),
copyright-risk flags on assets whose licence needs attribution that is not present in
the render, and platform metadata validation. **Warn and block, never silently
publish.**

---

## 21. Security

- Secrets in the OS keychain; `.env` for non-secret config only; nothing sensitive in
  the Next.js client bundle.
- **No shell string interpolation, ever.** `execFile`/`spawn` with argument arrays for
  ffmpeg and every other binary. This is the single highest-risk area: a filename from
  a provider reaching a shell is command injection.
- Path traversal: every file path resolved and asserted to be inside its project or
  cache root.
- SSRF: asset downloads restricted to an allowlist of provider hosts; no user-supplied
  URLs fetched server-side without validation; redirects to private ranges rejected.
- Media validation: `ffprobe` before use; reject files whose container or codec does not
  match what the provider declared.
- The server binds to `127.0.0.1` only.

---

## 22. Error handling, observability, QC

Structured errors everywhere: `{stage, code, message, retryable, context}` — surfaced
in the UI with an action, logged with project/job/version ids.

**QC gates before a render is marked complete:**

| Domain | Checks |
| --- | --- |
| Video | resolution, fps, duration within tolerance, playable, no all-black frames, no unintended frozen spans, every scene present |
| Audio | narration present, loudness within ±1 LU of target, true peak under ceiling, no clipping, duration matches video |
| Graphics | no text outside safe area, fonts loaded (not fallback), no missing assets, no overlap collisions |
| Assets | all files present and probe-clean, licence metadata complete, attribution rendered where required |
| Publish | metadata complete, account connected and token valid, platform constraints satisfied |

The font check deserves its place: an early render in this repo silently used Helvetica
and nothing reported it.

---

## 23. Testing

- **Unit** — compiler, director schema validation, ranking, licence filters, timing maths.
- **Integration** — pipeline stages against recorded provider fixtures. **No test
  touches the network**; the existing suite already holds this line.
- **Render** — a deterministic 10-second fixture project rendered on every CI run,
  compared frame-hash-wise at three timestamps. This catches silent visual regressions,
  which are otherwise invisible until someone watches an export.
- **Failure** — provider 429/500, truncated download, OOM, disk full, revoked token.
- **Publishing** — against sandbox/mocked APIs. Never a live publish in tests.
- **Benchmark** — the 75-second project, tracked over time.

---

## 24. Decision tables

### Technology decisions

| Component | Recommended | Alternative | Licence | Cost | Local/Cloud | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| Motion engine | **Remotion** | Motion Canvas (built), Blender | ⚠️ Free ≤3 people, $25/seat at 4+ | $0 for you today | Local | `@remotion/player` is the only one with an embeddable scrubbing preview, which the dashboard requires |
| Dashboard | **Next.js 15 + React 19** | Vite + React, Tauri | MIT | Free | Local | Server actions + SSE for job progress; one toolchain with Remotion |
| Styling | **Tailwind + Radix primitives** | shadcn wholesale, CSS Modules | MIT | Free | Local | Primitives without a template look; you asked not to look generic |
| Database | **SQLite + Drizzle** | Postgres, Prisma | MIT/Apache | Free | Local | No daemon, real migrations, right size for one desktop user |
| Job queue | **In-process, SQLite-backed** | BullMQ + Redis | MIT | Free | Local | A broker is operational weight with no benefit on a desktop |
| Content layer | **Existing Python** | Port to TS | — | Free | Local | 118 tests, live retrieval, safety gate — reuse, don't rewrite |
| Research LLM | **Provider abstraction; API default** | Local Qwen3 8B | varies | ~$0.02–0.15/video | Cloud (local fallback) | 16 GB cannot hold a model good enough for 6-minute documentary prose alongside a render |
| Footage | **Pexels → Pixabay → Commons → Archive** | single provider | permissive | Free | Cloud | Fallback chain; one dead provider must not fail a project |
| Generative video | **Veo 3.1 via Gemini API** | rented NVIDIA + Wan 2.2 | commercial | **$0.64–0.96 / 8s 1080p** | Cloud | No local option on an Air. Surface cost before generating |
| Images | **Imagen via Gemini API** | FLUX.2 klein (Apache-2.0) on rented GPU | commercial | per image | Cloud | Thumbnails and conceptual plates |
| TTS | **Kokoro (draft) + Chatterbox (final)** | Piper, external APIs | Apache-2.0 / MIT | Free | Local | Already abstracted; CPU-viable on Apple Silicon |
| Alignment | **WhisperX** | mlx-whisper, aeneas | BSD-ish | Free | Local | Forced alignment, sub-100ms word boundaries |
| Music | **Pixabay Music** | Free Music Archive, ACE-Step | Content Licence | Free | Cloud→Local | API access, no attribution burden, commercial OK |
| SFX | **Freesound + Pixabay** | commercial packs | per-asset CC | Free | Cloud | Must filter licences per asset, like Commons |
| Charts | **Hand-built SVG + interpolate** | Recharts, visx | — | Free | Local | Library animation fights frame-deterministic rendering |
| Maps | **react-simple-maps + Natural Earth** | Mapbox, Google Maps | MIT + public domain | Free | Local | No key, no tile licensing, deterministic |
| Icons | **Lucide** | Tabler, Phosphor | ISC | Free | Local | One library, one weight, one grid |
| Fonts | **Inter Variable, self-hosted** | Google Fonts CDN | OFL | Free | Local | Offline determinism; variable axis for kinetic weight |
| Encode | **libx264 delivery, VideoToolbox preview** | ProRes intermediate | LGPL/GPL | Free | Local | Benchmark before locking (§16) |
| Publishing | **YouTube Data API v3, Instagram Graph API** | third-party aggregators | — | Free tier | Cloud | Official only |
| Secrets | **OS keychain (keytar)** | encrypted file | MIT | Free | Local | Tokens never in the DB in plaintext |

### Feature phasing

| Feature | MVP | Phase 2 | Phase 3 | Difficulty |
| --- | --- | --- | --- | --- |
| Research + citations | ✅ built | | | done |
| Safety / claim gate | ✅ built | | | done |
| Scene spec + validation | ✅ built | | | done |
| Cache + resumable DAG | ✅ built | | | done |
| LLM script | ✅ | | | medium |
| **AI Director / storyboard** | ✅ | | | **high** |
| Pexels + Pixabay footage | ✅ | | | medium |
| Clip extraction | ✅ | | | medium |
| Candidate ranking (deterministic) | ✅ | | | medium |
| CLIP semantic ranking | | ✅ | | high |
| TTS + alignment | ✅ built | | | done |
| Remotion composition | ✅ | | | high |
| Component library (core 12) | ✅ | | | high |
| Full component library (25+) | | ✅ | | medium |
| Charts | | ✅ | | medium |
| Maps | | ✅ | | medium |
| Music + ducking | ✅ | | | medium |
| SFX | | ✅ | | low |
| Captions | ✅ built | | | done |
| 1080p render + QC | ✅ | | | high |
| Dashboard + player | ✅ | | | high |
| Job system + progress | ✅ | | | medium |
| Recreate (whole) | ✅ | | | low |
| Recreate (scene) | | ✅ | | medium |
| Editor | | ✅ | | high |
| Versioning | | ✅ | | medium |
| Multi-aspect | | ✅ | | high |
| Generative video (Veo) | | ✅ | | medium |
| Thumbnails | | ✅ | | medium |
| Metadata generation | | ✅ | | low |
| YouTube publishing | | | ✅ | high |
| Instagram publishing | | | ✅ | high |
| Scheduling | | | ✅ | medium |
| Shorts extraction | | | ✅ | high |
| Analytics | | | ✅ | medium |
| Brand kit | | ✅ | | medium |
| Content memory | | | ✅ | medium |

### Providers

| Capability | Provider | API? | Official? | Fallback |
| --- | --- | --- | --- | --- |
| Stock video | Pexels | yes | yes | Pixabay → Commons → Archive → generated |
| Stock video | Pixabay | yes | yes | Commons |
| Archival media | Wikimedia Commons | yes | yes | Internet Archive |
| Archival media | Internet Archive | yes | yes | motion graphic |
| Generative video | Veo 3.1 (Gemini API) | yes | yes | rented NVIDIA + Wan 2.2 → motion graphic |
| Generative video | Google Flow (consumer) | **no** | consumer UI only | not automatable — manual import only |
| Images | Imagen (Gemini API) | yes | yes | frame + typography template |
| Research | Wikipedia REST, PubMed | yes | yes | — |
| Research (general) | Tavily / Brave Search | yes | yes | Wikipedia only |
| Script LLM | Anthropic / Gemini API | yes | yes | Ollama + Qwen3 8B local |
| TTS | Kokoro, Chatterbox | local | OSS | external TTS adapter |
| Alignment | WhisperX | local | OSS | estimated (marked in provenance) |
| Music | Pixabay Music | yes | yes | local library → ACE-Step |
| SFX | Freesound | yes | yes | Pixabay → none |
| Publish | YouTube Data API v3 | yes | yes | manual export |
| Publish | Instagram Graph API | yes | yes | manual export |

### Risks

| Risk | Severity | Probability | Mitigation |
| --- | --- | --- | --- |
| YouTube audit not granted → cannot publish public | **High** | Medium | Apply early, before Phase 3. UI shows verification state. Manual-export path always available |
| Instagram app review rejected or slow | **High** | Medium-High | Start review in Phase 3 planning. Export + manual post as the honest fallback |
| Veo per-video cost surprises you | Medium | **High** | Show projected cost before generation; hard per-project cap; generated footage off by default |
| Remotion licence trigger if you hire | Medium | Low | Documented; $25/seat is small next to the alternative of a rewrite |
| Render OOM on 16 GB | Medium | Medium | Per-scene rendering, memory floor check, concurrency from benchmark, proxies for preview |
| Thermal throttling distorts benchmarks | Low | **High** | Benchmark three consecutive runs; use the third |
| Footage relevance poor → generic video | **High** | Medium | Ranking over 20 candidates; director-authored multi-query intents; graphics as first-class alternative, not a fallback |
| Provider licence change | Medium | Low | Licence recorded per asset at download time; ledger is historical, not re-derived |
| LLM invents facts | **High** | Medium | Existing `assert_no_invented_claims`: cited ids must exist, every number must appear in its source. Runs against any backend |
| Scope collapse under its own weight | **High** | **High** | Phase gates below. One end-to-end video before anything else |

---

## 25. Implementation sequence

The single most important rule: **one complete, reliable video before breadth.**

### Phase 0 — restructure (≈3 days)
Monorepo layout, move `src/videobot` → `content/`, `packages/core` with TS bindings
generated from the JSON Schemas, Drizzle schema + first migration, hardware detection
module. **Exit**: existing 118 tests still pass from the new layout; `hardware detect`
prints a real report on your Mac.

### Phase 1 — foundation (≈1 week)
Fastify server, job runner over SQLite, resource manager, project CRUD, SSE progress,
Next.js shell with real navigation. **Exit**: create a project, run the existing Python
pipeline as a job, watch true progress, see `scene-spec.json` in the UI.

### Phase 2 — first end-to-end video (≈2 weeks) ← **the milestone that matters**
LLM script service, Pexels + Pixabay providers, asset cache with proxies, clip
extraction, Remotion project with 12 core components, per-scene render, ffmpeg mux,
QC, player in the dashboard. **Exit**: topic in → 60-second 1080p video with real
footage, voiceover, captions and music, playing in the dashboard. Reliably, three times
in a row.

### Phase 3 — the director (≈1.5 weeks)
Shot-list generation with schema validation, medium selection, pacing from actual
audio, beat-level composition, candidate ranking. **Exit**: the same topic produces a
visibly *edited* video — cuts, mixed media, varied pacing — not one clip per sentence.

### Phase 4 — motion depth (≈2 weeks)
Full component library, charts, maps, transitions, sound design, brand kit,
multi-aspect. **Exit**: a chart-carrying documentary segment that looks designed.

### Phase 5 — control (≈2 weeks)
Editor, scene recreate, footage replace, versioning, thumbnails, metadata.
**Exit**: regenerate one scene without re-rendering the video.

### Phase 6 — publishing (≈2 weeks, plus external review time)
YouTube OAuth + upload + thumbnail, Instagram container flow, publish queue, our own
scheduler, connected-accounts UI. **Start the YouTube audit and Meta app review at the
beginning of Phase 3**, not here — they are the long poles.

### Phase 7 — optimisation and hardening (≈1.5 weeks)
Benchmark matrix, defaults from measurement, render recovery, offline resume, disk
management, analytics.

**Total to MVP (end of Phase 2): ~4 weeks.** Total to the full vision: ~3 months of
focused work. That is an honest estimate for one person, and the phases are ordered so
that stopping after any of them leaves something usable.

---

## 26. Known limitations — stated plainly

1. **You cannot publish public YouTube videos until Google audits the API project.**
2. **Instagram cannot schedule Reels via API.** Our scheduler fires at the target time;
   the machine must be awake and online.
3. **Generated video costs real money per clip** and cannot run locally on this machine.
4. **Google Flow consumer access is not API access.** Flow output can be imported
   manually as an asset; it cannot be automated.
5. **Footage relevance is the quality ceiling for stock-driven scenes.** Ranking helps;
   it does not make a perfect clip exist. This is why graphics are first-class.
6. **Analytics are limited to what the platforms expose.** Watch time and audience
   retention have real API constraints; the system will not invent metrics it cannot
   read.
7. **A 16 GB Air renders 1080p comfortably and 4K uncomfortably.** 4K delivery is out of
   scope for local rendering.
8. **"Best time to publish" is a prior until you have history.** It will say so.

---

## 27. Environment variables

```
# LLM
ANTHROPIC_API_KEY=            # or
GEMINI_API_KEY=
LLM_PROVIDER=anthropic|gemini|ollama
OLLAMA_HOST=http://127.0.0.1:11434

# Media providers
PEXELS_API_KEY=
PIXABAY_API_KEY=
FREESOUND_API_KEY=
NCBI_EMAIL=                   # optional, courtesy to NCBI
TAVILY_API_KEY=               # optional, general-topic research

# Generative (paid — leave unset to disable)
GEMINI_VIDEO_MODEL=veo-3.1-fast-generate-preview
GEMINI_IMAGE_MODEL=
VEO_MONTHLY_BUDGET_USD=25     # hard cap; generation refuses past it

# Publishing (OAuth client config; tokens live in the keychain)
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
META_APP_ID=
META_APP_SECRET=

# Local
DATA_DIR=./data
FFMPEG_PATH=                  # auto-detected; must have libx264
RENDER_CONCURRENCY=           # auto from benchmark
```

No secret is ever read by the Next.js client. The server is the only holder.

---

## 28. What I need from you before implementation

1. **Remotion, or stay on Motion Canvas?** My recommendation is Remotion, for the
   player. It is your licence exposure if the studio ever exceeds three people.
2. **LLM provider.** An API model will write markedly better 6-minute documentary
   narration than anything that fits in 16 GB alongside a render. Which key do you
   want to use?
3. **Veo budget.** Off, or a monthly cap? I would start off, and turn it on for
   specific scenes once the rest is good.
4. **Start the YouTube audit and Meta app review now?** They are the longest external
   dependencies and they gate Phase 6 regardless of how fast the code goes.
5. **First real topic.** Phase 2's exit criterion should be a video you actually want,
   not "dehydration" again.
