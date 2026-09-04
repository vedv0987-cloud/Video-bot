# Video-bot

Automated short-form health & fitness video pipeline — free and open-source end to end.

- [`video-bot-roadmap.md`](video-bot-roadmap.md) — the original ten-stage pipeline
- [`docs/UPGRADE-PLAN.md`](docs/UPGRADE-PLAN.md) — v2 architecture, 2026 tool stack, and the craft rules

## Status: Phase 1 — foundation & the seam

The content layer produces a **scene spec**: a declarative, engine-agnostic
description of the finished video. Nothing here renders pixels — the motion
layer consumes the spec and is deliberately swappable (UPGRADE-PLAN §2).

```
research ──▶ script ──▶ compose ──▶ scene-spec.json
   │           │           │
   └───────────┴───────────┴──▶ content-addressed cache (.cache/)
```

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
`--force <node>` to recompute a node, `--strict` to fail on lint warnings.

## Layout

```
brand/health-v2.json          brand tokens — colour, type, spacing, motion
src/videobot/
├── cli.py                    entry point
├── cache.py                  content-addressed artifact cache
├── dag.py                    node graph + runner
├── spec.py                   scene spec validation and craft linting
├── brand.py                  token loading
├── platforms.py              delivery formats and platform safe areas
├── hashing.py                canonical hashing
├── schema/                   JSON Schemas for the spec and the tokens
└── nodes/                    research → script → compose
```

## Two design rules worth knowing before you edit

**The spec is a pure function of its inputs.** No build timestamps, no absolute
paths, no randomness that is not seeded from content. Break this and the cache
stops hitting, which means every typo costs a full re-render.

**Cache keys are digests, not timestamps.** Recomputing a node that produces
identical bytes leaves everything downstream cached. Bump a node's `version`
when its logic changes; that is what invalidates old artifacts.

## The compliance gate

Health content is YMYL, so the pipeline refuses to publish claims it cannot
source (UPGRADE-PLAN §7.1). `compliance.gate` only reaches `passed` when every
citation is verified, and `requires_human_signoff` is `true` by construction.
Phase 1's placeholder research is unverified on purpose — the gate stays
`pending` and nothing can ship.

## Next

Phase 2 replaces `nodes/research.py` and `nodes/script.py` with real retrieval
(Wikipedia + PubMed), citation capture, a constrained Qwen3 rewrite, Kokoro /
Chatterbox-Turbo voiceover, WhisperX word alignment, and a librosa beat map.
The spec schema already has the fields waiting.
