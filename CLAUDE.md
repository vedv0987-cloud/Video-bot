# CLAUDE.md — project memory

Read this first. It is the handoff between sessions: what this is, what is decided, what
is next, and the traps already paid for.

---

## What this is

An automated pipeline that turns a health/fitness topic into a ready-to-post short video —
research, script, voiceover, motion graphics, captions, music, render, metadata. Every
component free and open-source.

Owner: **Ved** (Vedprakash Vishwakarma), Creative AI Specialist & Multimedia Designer. The
bar is agency-grade motion design, not "an AI made a video". Output that reads as generic
or algorithmic has failed, however correct its content.

**Read in this order:**

| Doc | What it holds |
| --- | --- |
| `docs/MASTER-PLAN.md` | The studio plan: dashboard, AI director, asset engine, Remotion, publishing, benchmarks. **Awaiting approval — five decisions open in §28.** |
| `docs/UPGRADE-PLAN.md` | v2 pipeline architecture, 2026 tool stack with licences, the craft rules, risk register |
| `docs/LOCAL-SETUP.md` | Running the model stages on Ved's Mac, pinned to his hardware |
| `video-bot-roadmap.md` | Original v1 roadmap. Historical — its tooling choices are superseded |

---

## Current state

**Phases 1–3 of the pipeline are complete; it renders an MP4.** The studio build
(`docs/MASTER-PLAN.md`) is now underway — Phase 0 has begun. 118 Python tests,
18 motion tests, 14 hardware tests.

Decisions settled: **Remotion** as the motion engine · **Gemini 3 Flash free tier**
for the LLM, with Ollama fallback (**never enable billing on that Google Cloud
project — it deletes the free tier**) · **generative video removed from scope**,
footage and graphics only · platform reviews submitted at Phase 6, since both
require a working demo · Phase 2 target topic is "How Nuclear Fusion Could Change
the Future".

```
research ──▶ script ──▶ voice ─┬─▶ align ─┐
    │           │              └─▶ beats ─┴─▶ compose ──▶ scene-spec.json
    └───────────┴─────────────────────────────────▶ cache (.cache/)
```

```bash
pip install -e ".[dev]" && pytest
videobot --topic "dehydration"        # live retrieval
videobot --topic "x" --offline        # no network; cannot pass the gate
```

Retrieval is live (Wikipedia + PubMed). **`--voice kokoro` is real**: Kokoro-82M
synthesises the voiceover at 24 kHz, seeded so the wav is a pure function of the script.
Alignment, beats and the rewriter still sit behind interfaces with deterministic offline
defaults. `chatterbox`, `whisperx` and `librosa` are *declared but unwritten* — they now
say so (`BackendNotImplemented`) rather than blaming the install.

The **motion layer** lives in `motion/` (Motion Canvas, MIT). `motion/src/lib/compile.ts`
turns a spec into an engine-independent render plan; `render.tsx` interprets it;
`components/` holds the five card types. `npm run stills` pulls PNGs through headless
Chromium without opening the editor.

`npm run render` produces the MP4: frames out of headless Chromium, then ffmpeg for
grain, EBU R128 loudness and the h264 encode, with the voiceover muxed in.

**Phase 4 remains**: sidechain ducking once there is music, a LUT grade, the 1:1 and 16:9
ladder, QC gates (VMAF, loudness verify, safe-area check) and OpenTimelineIO export.

---

## The architecture in one idea

A hard seam between the **content layer** (Python: research → spec) and the **motion
layer** (swappable engine), joined by `scene-spec.json`. The content layer must never know
which renderer wins. That is what makes Motion Canvas / Blender / After Effects
interchangeable, and it is why Phases 1–2 did not need the engine decision made.

---

## Invariants — do not break these

1. **The spec is a pure function of its inputs.** No build timestamps, no absolute paths,
   no unseeded randomness. Provenance goes in `run.json`, never in the spec. A timestamp
   inside a cached artifact changes its digest every run and silently kills the cache.
2. **Cache keys are digests, not timestamps.** Recomputing a node to identical bytes must
   leave downstream cached. Bump a node's `version` when its logic changes.
3. **No linear easing, anywhere.** The spec validator rejects it outright (§5.1).
4. **Verified ≠ true.** "Verified" means traced to a pinned source — a PMID or a Wikipedia
   revision id. It never means clinically endorsed, which is why
   `requires_human_signoff` is `true` by construction.
5. **`assert_no_invented_claims` runs against every rewriter backend.** Cited ids must
   exist; every number in the script must appear in the source it cites. Never loosen this
   to accommodate a backend — change the backend.
6. **The compliance gate needs a claim card on screen.** Citations the viewer never sees
   are not sourced content.
7. **Source failures are recorded, never swallowed.** A degraded run must be visible.

---

## Traps already paid for

Each of these was a real bug found by running the thing, not by reading it.

- **The numeric invariant fired on our own template.** It wrote "Sourced from 4
  peer-reviewed references" — a tally, not a sourced fact. Fix was to make connective text
  digit-free, *not* to weaken the rule. Hook and CTA text must contain no digits.
- **A transient Wikipedia outage produced a contentless video that passed the gate.** A
  bare `except Exception: continue` swallowed it. Retrieval failures now surface in
  `compliance.notes`, and the gate requires a claim card.
- **Scenes were paired to timeline boundaries by index.** A section producing no words
  would shift every later scene onto the wrong boundary. Pair by id.
- **The CTA cited a specific paper.** Its text is not a claim; only `kind == "point"`
  elements carry `cite`.
- **`$schema` leaked into the brand digest**, changing a render's identity when the file
  moved. It is stripped before hashing.
- **Canvas text falls back silently when the face has not loaded.** The first stills came
  out in Helvetica. Inter is now self-hosted via `@fontsource-variable/inter` and the
  renderer awaits `document.fonts.ready`.
- **The safe area used to cross the seam as a name.** The renderer would have needed its
  own copy of the platform table; the numbers now travel in `meta.safe_area`.
- **Building an image search query from each claim's own words produced verb soup** —
  "dehydration occurs exceeds intake". One search on the topic, widened once, is both
  simpler and better.
- **Wikimedia Commons is a poor b-roll source for health.** The pool is clinical
  documentation, and general search returns an aerial of ploughed fields for
  "dehydration". `--media` is therefore **opt-in**; the procedural backgrounds are the
  default visual language. Do not flip this without looking at what comes back.
- **Playwright bundles a minimal ffmpeg with no libx264.** It fails at the encode, after
  every frame has been rendered. `render.mjs` verifies the codec before starting.
- **Kokoro is not deterministic out of the box.** Two runs of the same sentence differed
  across 78% of their samples, by up to 9% of full scale. Unseeded it rewrites the voice
  artifact every run and invalidates align, beats and compose behind it —
  `KOKORO_SEED` is what makes invariant 1 hold for a neural voice. Seed per chunk, not
  per call, so re-chunking leaves untouched chunks byte-identical.
- **Kokoro reproduces on a machine, not across machines.** The same script and seed
  gave `b1d89064169b57da` on Ved's M5 and `56eb2995d968ad50` in a Linux x86 container —
  same sample count (both 32.72 s, so align and beats matched byte for byte), different
  sample values. That is ordinary float divergence between architectures, and invariants 1
  and 2 only ever needed determinism *per machine*. But it means a voice cache is not
  portable: never copy `.cache/voice/` between machines or expect CI to reproduce a wav
  rendered on the Air.
- **An unimplemented backend told you to `pip install` it.** `--voice kokoro` failed with
  "not installed in this environment" on a machine where Kokoro *was* installed, because
  the backend was a stub wearing an install hint. Backends that were never written now
  raise `BackendNotImplemented` and name the reason.
- **The suite only passed under `python -m pytest`.** `tests/test_nodes.py` imported
  `BRAND_PATH` across test modules, which needs `tests` to be importable — true only when
  CWD is on `sys.path`. Shared test constants belong in `conftest.py`.
- **`cd` persists between Bash calls.** Several patch scripts silently wrote nothing
  because the working directory was `motion/`. Use absolute paths.

---

## Conventions

- **Branch**: `claude/health-video-automation-roadmap-jicv5l`. Restart it from `main` after
  each merge; never commit to `main` directly.
- **Ved does not want to click merge.** Push → open PR → mark ready → merge it yourself,
  squash. Tell him what landed. If something genuinely warrants his eyes first, say so and
  leave it open.
- **Verify before pushing**: `pytest` green, and exercise the real path (a live run), not
  just tests.
- **Tests never touch the network.** Sources are exercised against fakes; CLI tests use
  `--offline`.
- Comments explain *why*, never *what*. Match the surrounding density.
- Schemas live in `src/videobot/schema/` as package data so they resolve from any cwd.
- The motion layer has its own suite: `cd motion && npm test` (pure compiler logic, no
  browser) and `npm run typecheck`. Run both before pushing anything under `motion/`.
- Node workspaces live at the repo root: `npm run hardware` measures the machine and
  prints the render budget. Run it on the target Mac before trusting any render default.

---

## Ved's machine

**MacBook Air · Apple M5 · 10 cores (4P/6E) · 8-core GPU · 16 GB unified · macOS 26.6.2.**
Measured, not assumed — `npm run hardware` on the machine.

- **Build the Python venv with 3.12.** Ved's default is 3.14.7, and `kokoro-onnx` and
  `whisperx` both pin `python <3.14`. They fail at `pip install`, late.
- **VideoToolbox is verified working** (ffmpeg 9.0.1, libx264 present). Hardware encode
  for previews, libx264 for delivery.
- **Free memory is the real constraint, not total.** 4.4 GB free with his apps open, so
  the budget recommends 2 render workers where 16 GB would suggest 4.

- ~10 GB usable for models after the OS. Qwen3 **8B** quantised — larger variants swap.
- Fanless: sustained load throttles. Long jobs belong in an overnight batch.
- Do not run the pipeline with After Effects or Premiere open.
- **No local generative video.** Measured: ~82 min for a 2-second clip on an M1 Max 64 GB;
  LTX-2 fp8 fails on Metal. Rent NVIDIA by the hour if a piece ever needs it.
- ffmpeg with VideoToolbox gives hardware encode — use it in Phase 4.

He also runs After Effects with Trapcode / Element 3D (see his `ae-motion-engine` skill).
That is **Tier C**: bespoke hero set-pieces. It is not open-source, so it sits outside the
stated constraint, but it beats everything here on one-off craft.

---

## Decisions made

| Decision | Choice | Why |
| --- | --- | --- |
| 2D motion engine | **Motion Canvas (MIT)** | Actively maintained; real scene graph and easing |
| Rejected | **Remotion** | Free only for for-profits ≤3 employees; trigger is company headcount |
| Revideo | Renderer only | MIT, but upstream work moved to commercial Midrender |
| 3D hero shots | Blender headless (GPL) | Only free option with true motion blur, DOF, volumetrics |
| TTS | Kokoro (draft) + Chatterbox-Turbo (final) | Apache-2.0 / MIT; Coqui is dead |
| Music | ACE-Step 1.5 (Apache-2.0) | Generating it removes the licensing problem entirely |
| Excluded on licence | F5-TTS, MusicGen (CC-BY-NC); FLUX.2 dev | Non-commercial or needs a paid licence |

**Still open:** whether After Effects stays as Tier C, and whether Ved wants the
TypeScript motion layer at all versus going Blender-only and staying pure Python.

---

## What not to do

- Do not add a build timestamp, anywhere in the spec.
- Do not weaken the safety screen or the claim invariant to make a backend fit.
- Do not put dosages, named drugs, diagnosis language or treatment framing on screen —
  the screen in `safety.py` over-blocks deliberately, and that is correct.
- Do not attempt local video generation on the Air.
- Do not reach for MoviePy. It has no animation model; replacing it is the whole point of
  the v2 plan.
