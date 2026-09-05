# Motion layer — Tier A

Compiles `scene-spec.json` into animation. Motion Canvas (MIT), TypeScript.

```bash
npm install
npm run prepare-data -- ../output/dehydration/scene-spec.json
npm test          # compiler + easing, pure, no browser
npm run typecheck
npm run stills    # PNGs from the current spec, via headless Chromium
npm run render    # the MP4: frames → ffmpeg, with grain and loudness
npm run serve     # the Motion Canvas editor, for hand-tuning
```

`render` needs an ffmpeg **with libx264**. It checks before rendering a single
frame, because discovering a codec is missing after eight hundred frames is a
waste of everyone's afternoon.

- macOS: `brew install ffmpeg`
- anywhere: `pip install imageio-ffmpeg`
- or set `FFMPEG_PATH`

## Shape

```
data/spec.json + data/brand.json
        │
        ▼
   lib/compile.ts      pure: tokens resolved, staggers expanded, blur decided,
        │  RenderPlan  words sliced per scene
        ▼
   lib/render.tsx      interpreter: plan → layered scene graph
        │
        ├── lib/backgrounds.tsx   gradient mesh · particle field · grid lines
        ├── media layer           licensed still under a slow move + scrim
        ├── components/           kinetic text, stat counter, list reveal,
        │                         lower third, end card
        └── lib/overlay.tsx       vignette
```

### Layer order

Background, media, scrim, content, vignette, credit. The scrim is deliberately
heavy: a still is there to give the frame depth, not to compete with the
sentence the viewer is reading.

`compile.ts` is where the thinking is, and it is engine-independent — if the
renderer is ever swapped for Blender or After Effects, the plan survives.
`render.tsx` is deliberately thin.

## Rules enforced here

- **Linear easing throws.** `resolveEase` refuses it, mirroring the Python
  validator. The motion contract is enforced on both sides of the seam.
- **An animation with no travel distance throws.** Motion blur is a function of
  speed, so an unknown animation is a compile error rather than a silent
  zero — an unblurred fast move is exactly the artefact §5.2 exists to prevent.
- **A spec built against a different brand throws.** Rendering with the wrong
  tokens silently changes the design.
- **Fonts are self-hosted** (`@fontsource-variable/inter`) and the render waits
  on `document.fonts.ready`. Canvas text falls back silently, and a fallback
  font is the difference between the house style and Helvetica.

## Kinetic type is the caption

`KineticText` reveals each word as it is spoken, from the alignment already in
the spec. The live word carries the accent colour and settles to ink as the
voice moves on.

That makes the card *be* the caption rather than duplicating it in a strip at
the bottom — both the current short-form idiom and the honest answer to having
one piece of text and one voice reading it. When the alignment does not match
the text word-for-word it falls back to a block reveal rather than guessing.

## Imagery is opt-in, and that is a considered default

`videobot --media` attaches licensed stills from Wikimedia Commons. It is off
by default because the freely-licensed pool for health topics is largely
clinical documentation, and the general search returns things like an aerial
photograph of ploughed fields for "dehydration". An irrelevant picture
dominating the frame is worse than a clean procedural background.

When a still *is* used, its credit is drawn in the frame. CC BY and CC BY-SA
require attribution, and a description that may not travel with the file is not
compliance.

## Motion blur, honestly

The blur here decays as an element settles, scaled by its speed — the standard
2D-motion-design approximation. It is **not** sub-frame accumulation. True
accumulation belongs in the finishing stage or in Blender (Tier B). The
compiler decides *whether* to blur from the brand's speed threshold; the
animation decides how much.
