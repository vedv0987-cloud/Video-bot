/** A single line of display type, centred in the safe band. */

import { Txt } from '@motion-canvas/2d';

import { TRAVEL_PX } from '../lib/compile';
import { lifecycle } from '../lib/animate';
import type { BuildContext, BuiltElement } from './index';

export function statementCard({ element, contentWidth, centreY }: BuildContext): BuiltElement {
  if (element.payload.kind !== 'text') {
    throw new Error(`statementCard expects a text element, got ${element.payload.kind}`);
  }
  const { style, color } = element;

  const node = new Txt({
    text: element.payload.content,
    fontFamily: [style.family, ...(style.fallback ?? [])].join(', '),
    fontWeight: style.weight,
    fontSize: style.size,
    // Tracking is authored as an em fraction, the way a type designer states
    // it; Motion Canvas wants pixels.
    letterSpacing: style.tracking * style.size,
    lineHeight: style.leading * style.size,
    fill: color,
    textAlign: 'center',
    textWrap: true,
    maxWidth: contentWidth,
    y: centreY,
  });

  const travel = TRAVEL_PX[element.enter.anim] ?? 0;
  return { node, timeline: (sceneIn) => lifecycle(node, element, sceneIn, travel) };
}
