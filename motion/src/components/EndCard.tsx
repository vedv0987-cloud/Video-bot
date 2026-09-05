/**
 * The closing card.
 *
 * Carries a rule above the line so the cut has a visual full stop rather than
 * just running out of words.
 */

import { Layout, Rect, Txt } from '@motion-canvas/2d';
import { all, chain, waitFor, type ThreadGenerator } from '@motion-canvas/core';

import { TRAVEL_PX } from '../lib/compile';
import { enter, exit } from '../lib/animate';
import { resolveEase } from '../lib/easing';
import type { BuildContext, BuiltElement } from './index';

export function endCard({ element, plan, contentWidth, centreY }: BuildContext): BuiltElement {
  if (element.payload.kind !== 'text') {
    throw new Error(`endCard expects a text element, got ${element.payload.kind}`);
  }
  const { style, color } = element;

  const node = new Layout({
    y: centreY,
    layout: true,
    direction: 'column',
    gap: plan.radius,
    alignItems: 'center',
  });

  const rule = new Rect({
    fill: color,
    height: 8,
    width: 0,
    radius: 4,
  });
  node.add(rule);
  node.add(
    new Txt({
      text: element.payload.content,
      fontFamily: [style.family, ...(style.fallback ?? [])].join(', '),
      fontWeight: style.weight,
      fontSize: style.size,
      letterSpacing: style.tracking * style.size,
      lineHeight: style.leading * style.size,
      fill: color,
      textAlign: 'center',
      textWrap: true,
      maxWidth: contentWidth,
    }),
  );

  const travel = TRAVEL_PX[element.enter.anim] ?? 0;

  function* timeline(sceneIn: number): ThreadGenerator {
    node.opacity(0);
    yield* waitFor(element.enter.at - sceneIn);
    yield* all(
      enter(node, element, travel),
      // The rule draws itself under the line as it lands.
      chain(waitFor(element.enter.dur * 0.4), rule.width(contentWidth * 0.22, element.enter.dur, resolveEase('expo.out'))),
    );
    if (element.exit) {
      yield* chain(
        waitFor(Math.max(0, element.exit.at - element.enter.at - element.enter.dur)),
        exit(node, element.exit),
      );
    }
  }

  return { node, timeline };
}
