# Motion layer — Tier A

Compiles `scene-spec.json` into animation. Motion Canvas (MIT), TypeScript.

```bash
npm install
npm run prepare-data -- ../output/dehydration/scene-spec.json   # or copy by hand
npm test          # compiler + easing, pure, no browser
npm run typecheck
npm run stills    # PNGs from the current spec, via headless Chromium
npm run serve     # the Motion Canvas editor, for hand-tuning
```

## Shape

```
data/spec.json + data/brand.json
        │
        ▼
   lib/compile.ts      pure: tokens resolved, staggers expanded, blur decided
        │  RenderPlan
        ▼
   lib/render.tsx      interpreter: plan → scene graph
        │
        ▼
   components/         statement card, stat counter, list reveal,
                       lower third, end card
```

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

## Motion blur, honestly

The blur here decays as an element settles, scaled by its speed — the standard
2D-motion-design approximation. It is **not** sub-frame accumulation. True
accumulation belongs in the finishing stage or in Blender (Tier B). The
compiler decides *whether* to blur from the brand's speed threshold; the
animation decides how much.
