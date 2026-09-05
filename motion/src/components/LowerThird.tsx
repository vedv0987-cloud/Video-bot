/**
 * A plated caption in the lower band.
 *
 * Sits above the platform's bottom chrome rather than centred, so it reads as
 * an overlay on the frame instead of a title card.
 */

import { Layout, Rect, Txt } from '@motion-canvas/2d';

import { TRAVEL_PX } from '../lib/compile';
import { lifecycle } from '../lib/animate';
import type { BuildContext, BuiltElement } from './index';

export function lowerThird({ element, plan, contentWidth }: BuildContext): BuiltElement {
  if (element.payload.kind !== 'text') {
    throw new Error(`lowerThird expects a text element, got ${element.payload.kind}`);
  }
  const { style, color } = element;
  const pad = plan.radius;

  // Just clear of the bottom safe inset, measured from frame centre.
  const y = plan.height / 2 - plan.safe.bottom - pad * 2;

  const node = new Layout({ y, layout: true, alignItems: 'center' });
  const plate = new Rect({
    fill: plan.background,
    radius: plan.radius,
    padding: [pad * 0.75, pad * 1.25],
    layout: true,
    opacity: 0.86,
  });
  plate.add(
    new Txt({
      text: element.payload.content,
      fontFamily: [style.family, ...(style.fallback ?? [])].join(', '),
      fontWeight: style.weight,
      fontSize: style.size * 0.72,
      letterSpacing: style.tracking * style.size,
      fill: color,
      textWrap: true,
      maxWidth: contentWidth * 0.8,
    }),
  );
  node.add(plate);

  const travel = TRAVEL_PX[element.enter.anim] ?? 0;
  return { node, timeline: (sceneIn) => lifecycle(node, element, sceneIn, travel) };
}
