/**
 * Frame overlays.
 *
 * A vignette darkens the corners so the eye lands on the type rather than
 * wandering to the edges — the cheapest thing that separates a rendered frame
 * from a slide.
 *
 * Grain is deliberately *not* here: ffmpeg's `noise` filter does it better and
 * at the right point in the chain, which is the finishing stage.
 */

import { Gradient, Rect } from '@motion-canvas/2d';

import type { RenderPlan } from './compile';

export function vignette(plan: RenderPlan): Rect {
  return new Rect({
    width: plan.width,
    height: plan.height,
    fill: new Gradient({
      type: 'radial',
      from: [0, 0],
      to: [0, 0],
      fromRadius: plan.height * 0.3,
      toRadius: plan.height * 0.8,
      stops: [
        { offset: 0, color: '#00000000' },
        { offset: 1, color: '#000000a8' },
      ],
    }),
  });
}
