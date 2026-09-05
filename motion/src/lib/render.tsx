/**
 * The interpreter: a render plan becomes a scene graph.
 *
 * Deliberately thin. Everything that decides how the piece *looks* lives in the
 * compiler, the backgrounds and the components; this only wires them to the
 * timeline and stacks them in the right order.
 *
 * Layer order, back to front:
 *
 *   background   procedural system, always moving
 *   media        licensed still under a slow move, when the spec carries one
 *   scrim        darkens whatever is beneath so type stays legible
 *   content      the cards
 *   vignette     pulls the eye to the middle
 */

import { Gradient, Img, Layout, Rect, Txt, type View2D } from '@motion-canvas/2d';
import { all, chain, waitFor, type ThreadGenerator } from '@motion-canvas/core';

import { buildBackground } from './backgrounds';
import { resolveEase } from './easing';
import { vignette } from './overlay';
import type { PlannedElement, PlannedScene, RenderPlan } from './compile';
import {
  endCard,
  kineticText,
  listReveal,
  lowerThird,
  statCounter,
  type BuildContext,
  type BuiltElement,
} from '../components';

const END_LAYOUTS = new Set(['end-card']);
const LOWER_THIRD_LAYOUTS = new Set(['lower-third']);

export function chooseComponent(
  layout: string,
  element: PlannedElement,
): (ctx: BuildContext) => BuiltElement {
  switch (element.payload.kind) {
    case 'counter':
      return statCounter;
    case 'list':
      return listReveal;
    case 'text':
      if (END_LAYOUTS.has(layout)) return endCard;
      if (LOWER_THIRD_LAYOUTS.has(layout)) return lowerThird;
      // Everything else gets word-synced type; it falls back to a block
      // reveal on its own when the alignment does not match.
      return kineticText;
    default:
      throw new Error(
        `no component for element kind "${element.payload.kind}" in layout "${layout}"`,
      );
  }
}

/**
 * A still under a slow move. A static photograph in a moving cut reads as a stall.
 *
 * Footage deliberately does *not* go through here. Motion Canvas's Video node
 * hangs this renderer outright: frames are pulled by seeking the playback
 * manager and screenshotting, and an HTMLVideoElement never becomes ready
 * under that loop — measured, the render stops dead at the first scene
 * carrying a clip. Footage is composited by ffmpeg instead, which decodes
 * video properly and is already in the chain. These scenes render with a
 * transparent background and the clip is laid in underneath afterwards.
 */
function mediaLayer(plan: RenderPlan, scene: PlannedScene): { node: Img; move: ThreadGenerator } | null {
  if (!scene.media || scene.media.kind !== 'image') return null;
  const { treatment } = scene.media;

  const node = new Img({
    src: scene.media.src,
    width: plan.width,
    height: plan.height,
    scale: treatment.scale_from,
  });

  const drift = plan.width * 0.05;
  const target: [number, number] =
    treatment.move === 'pan-left'
      ? [-drift, 0]
      : treatment.move === 'pan-right'
        ? [drift, 0]
        : [0, 0];

  return {
    node,
    move: all(
      node.scale(treatment.scale_to, scene.duration, resolveEase('sine.inOut')),
      node.position(target, scene.duration, resolveEase('sine.inOut')),
    ),
  };
}

/**
 * On-screen attribution.
 *
 * CC BY and CC BY-SA *require* credit. Putting it in a description that may or
 * may not travel with the file is not compliance; putting it in the frame is.
 * Small and low-contrast so it reads as a caption, not as content.
 */
function credit(plan: RenderPlan, scene: PlannedScene): Txt | null {
  if (!scene.media) return null;
  const style = plan.captions.style;
  return new Txt({
    text: scene.media.credit,
    fontFamily: [style.family, ...(style.fallback ?? [])].join(', '),
    fontWeight: 500,
    fontSize: style.size * 0.3,
    fill: plan.inkMuted,
    opacity: 0.65,
    // Just inside the bottom safe inset, where platform chrome will not sit.
    y: plan.height / 2 - plan.safe.bottom + style.size * 0.55,
  });
}

/** Keeps type legible over imagery without flattening the picture. */
function scrim(plan: RenderPlan): Rect {
  return new Rect({
    width: plan.width,
    height: plan.height,
    fill: new Gradient({
      type: 'linear',
      from: [0, -plan.height / 2],
      to: [0, plan.height / 2],
      // Heavy on purpose. A still is there to give the frame depth, not to
      // compete with the sentence the viewer is reading.
      stops: [
        { offset: 0, color: `${plan.background}f2` },
        { offset: 0.45, color: `${plan.background}cc` },
        { offset: 1, color: `${plan.background}fa` },
      ],
    }),
  });
}

export function* renderScene(
  view: View2D,
  scene: PlannedScene,
  plan: RenderPlan,
): ThreadGenerator {
  const contentWidth = plan.width - plan.margin.x * 2;
  // Platform chrome is heavier at the bottom, so the readable band sits above
  // the frame's true centre.
  const centreY = (plan.safe.top - plan.safe.bottom) / 2;

  const root = new Layout({});
  view.add(root);

  // A footage scene leaves its background transparent so ffmpeg can lay the
  // clip in underneath; drawing a procedural background there would simply
  // hide it.
  const overFootage = scene.media?.kind === 'video';
  const background = buildBackground(plan, scene);
  if (!overFootage) root.add(background.node);

  const media = mediaLayer(plan, scene);
  if (media) root.add(media.node);
  if (media || overFootage) root.add(scrim(plan));

  const built = scene.elements.map((element) =>
    chooseComponent(scene.layout, element)({
      element,
      plan,
      contentWidth,
      centreY,
      words: scene.words,
    }),
  );
  built.forEach((item) => root.add(item.node));
  root.add(vignette(plan));

  const attribution = credit(plan, scene);
  if (attribution) root.add(attribution);

  // The dip runs alongside the content rather than before it, so a transition
  // costs no screen time — the cards are already leading in by more than this.
  const dip = scene.transition.type === 'dip' ? scene.transition.dur : 0;
  const ease = resolveEase('sine.inOut');
  if (dip > 0) root.opacity(0);

  yield* all(
    overFootage ? waitFor(0) : background.animate(),
    media?.move ?? waitFor(0),
    ...built.map((item) => item.timeline(scene.in)),
    dip > 0
      ? chain(
          root.opacity(1, dip, ease),
          waitFor(Math.max(0, scene.duration - dip * 2)),
          root.opacity(0, dip, ease),
        )
      : waitFor(0),
    waitFor(scene.duration),
  );
}

export function* renderPlan(view: View2D, plan: RenderPlan): ThreadGenerator {
  for (const scene of plan.scenes) {
    yield* renderScene(view, scene, plan);
    view.removeChildren();
  }
}
