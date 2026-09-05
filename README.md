# Video-bot

Automated short-form health & fitness video pipeline — free and open-source end to end.

- [`video-bot-roadmap.md`](video-bot-roadmap.md) — the original ten-stage pipeline
- [`docs/UPGRADE-PLAN.md`](docs/UPGRADE-PLAN.md) — v2 architecture, 2026 tool stack, and the craft rules
- [`docs/LOCAL-SETUP.md`](docs/LOCAL-SETUP.md) — running the GPU stages on your own machine, by hardware tier

## Status: Phase 3 — motion layer renders

The content layer produces a **scene spec**: a declarative, engine-agnostic
description of the finished video, with live citations, a voiceover, word
timings and a beat map. Nothing here renders pixels — the motion layer consumes
the spec and is deliberately swappable (UPGRADE-PLAN §2).

```
research ──▶ script ──▶ voice ─┬─▶ align ─┐
    │           │              └─▶ beats ─┴─▶ compose ──▶ scene-spec.json
    └───────────┴─────────────────────────────────▶ cache (.cache/)   │
                                                                       ▼
                                            motion/  (Motion Canvas) ──▶ frames
```

The motion layer is a separate TypeScript project under [`motion/`](motion/), joined to
the content layer only by the spec file. See [motion/README.md](motion/README.md).

Retrieval is live (Wikipedia + PubMed). Voice, alignment and beats sit behind
interfaces with deterministic offline defaults, so the graph runs anywhere and
the real models drop in unchanged on a machine with a GPU.

| Stage | Default here | Swap in with |
| --- | --- | --- |
| Rewriter | `template` (verbatim) | `--rewriter qwen3` (Ollama) |
| Voice | `null` (silent, correct length) | `--voice kokoro` / `chatterbox` |
| Alignment | `estimated` | `--aligner whisperx` |
| Beats | `fixed-tempo` | `--beats librosa` |

Uninstalled backends fail with an install command, never an ImportError.
Whatever ran is recorded in `audio.provenance` — an estimate must never read as
a measurement.

## Quick start

```bash
pip install -e ".[dev]"
videobot --topic "hydration"          # or: python -m videobot --topic "hydration"
pytest
```

Output lands in `output/<slug>/`:

| File | Contents |
| --- | --- |
| `scene-spec.json` | The spec. A pure function of its inputs — no timestamps. |
| `run.json` | Provenance: when it ran, cache hits/misses, artifact digests, warnings. |

Useful flags: `--aspect {9:16,1:1,16:9}`, `--brand <tokens.json>`, `--print`,
`--force <node>` to recompute a node, `--strict` to fail on lint warnings, and
`--offline` to skip retrieval entirely (which produces an uncited spec that
cannot pass the gate — useful for CI).

## Layout

```
brand/health-v2.json          brand tokens — colour, type, spacing, motion
src/videobot/
├── cli.py                    entry point
├── cache.py                  content-addressed artifact cache
├── dag.py                    node graph + runner
├── spec.py                   scene spec validation and craft linting
├── safety.py                 blocked-category screening for health claims
├── brand.py                  token loading
├── http.py                   throttled stdlib HTTP for the sources
├── sources/                  wikipedia + pubmed retrieval
├── audio/                    speech, alignment, beats
├── platforms.py              delivery formats and platform safe areas
├── hashing.py                canonical hashing
├── schema/                   JSON Schemas for the spec and the tokens
└── nodes/                    research → script → voice → align/beats → compose
```

## Two design rules worth knowing before you edit

**The spec is a pure function of its inputs.** No build timestamps, no absolute
paths, no randomness that is not seeded from content. Break this and the cache
stops hitting, which means every typo costs a full re-render.

**Cache keys are digests, not timestamps.** Recomputing a node that produces
identical bytes leaves everything downstream cached. Bump a node's `version`
when its logic changes; that is what invalidates old artifacts.

## The compliance gate

Health content is YMYL, so the pipeline refuses to publish what it cannot
source (UPGRADE-PLAN §7.1). Four things have to hold before `compliance.gate`
reaches `passed`:

1. Every claim is bound to a **pinned, resolvable** source — a PMID or a
   Wikipedia revision id. "According to Wikipedia" is not a citation.
2. Every passage clears the **safety screen**: no dosages, named drugs, drug
   interactions, diagnosis language, cure/treatment framing, or therapeutic
   supplement claims. The patterns deliberately over-block, and every drop is
   reported with its reason rather than vanishing.
3. At least one **claim card** reaches the screen. Citations the viewer never
   sees are not sourced content.
4. Retrieval did not silently fail. A dead source degrades the run, but it is
   always recorded in `compliance.notes`.

`requires_human_signoff` is `true` by construction. *Verified* here means
"traced to a pinned source", not "endorsed by a clinician" — which is exactly
why a person still presses publish.

The rewriter is swappable, but `assert_no_invented_claims` runs against every
backend's output: cited ids must exist, and any number in the script must
appear in the source it cites. Models invent plausible statistics far more
readily than whole sentences, so that is the check that earns its keep.

## Next

Phase 3 builds the Tier A motion engine: a Motion Canvas project, a spec→scene
compiler, and the component library (statement card, stat counter, list reveal,
lower third, end card) with the easing, stagger and motion-blur defaults from
UPGRADE-PLAN §5.1–5.2 baked in.
