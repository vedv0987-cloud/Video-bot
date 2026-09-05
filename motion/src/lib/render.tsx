/**
 * The interpreter: a render plan becomes a scene graph.
 *
 * Deliberately thin. Everything that decides how the piece *looks* lives in the
 * compiler and the components; this only wires them to the timeline.
 */

import { Gradient, Rect, type View2D } from '@motion-canvas/2d';
import { all, waitFor, type ThreadGenerator } from '@motion-canvas/core';

import { resolveEase } from './easing';
import type { PlannedElement, PlannedScene, RenderPlan } from './compile';
import {
  endCard,
  listReveal,
  lowerThird,
  statCounter,
  statementCard,
  type BuildContext,
  type BuiltElement,
} from '../components';

/** Layouts whose text is treated as a closing card rather than a statement. */
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
      return statementCard;
    default:
      throw new Error(
        `no component for element kind "${element.payload.kind}" in layout "${layout}"`,
      );
  }
}

function background(plan: RenderPlan, scene: PlannedScene): Rect {
  const stops = plan.gradient.map((color, index) => ({
    offset: plan.gradient.length === 1 ? index : index / (plan.gradient.length - 1),
    color,
  }));

  return new Rect({
    width: plan.width * 1.2,
    height: plan.height * 1.2,
    fill:
      scene.bg.type === 'solid'
        ? plan.background
        : new Gradient({
            type: 'linear',
            from: [0, -plan.height / 2],
            to: [0, plan.height / 2],
            stops,
          }),
  });
}

/**
 * A slow, continuous drift on the background.
 *
 * A perfectly static ground is the other tell of generated video: real footage
 * always breathes. The amount is deliberately below conscious notice.
 */
function* drift(node: Rect, scene: PlannedScene): ThreadGenerator {
  const amount = 1 + (scene.bg.drift ?? 0.02);
  yield* node.scale(amount, scene.duration, resolveEase('sine.inOut'));
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

  const bg = background(plan, scene);
  view.add(bg);

  const built = scene.elements.map((element) =>
    chooseComponent(scene.layout, element)({ element, plan, contentWidth, centreY }),
  );
  built.forEach((item) => view.add(item.node));

  yield* all(
    drift(bg, scene),
    ...built.map((item) => item.timeline(scene.in)),
    waitFor(scene.duration),
  );
}

export function* renderPlan(view: View2D, plan: RenderPlan): ThreadGenerator {
  for (const scene of plan.scenes) {
    yield* renderScene(view, scene, plan);
    view.removeChildren();
  }
}
