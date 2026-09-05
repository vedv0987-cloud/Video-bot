/** A number that rolls to its value, with an optional label beneath. */

import { Layout, Txt } from '@motion-canvas/2d';
import { all, chain, createSignal, waitFor, type ThreadGenerator } from '@motion-canvas/core';

import { TRAVEL_PX } from '../lib/compile';
import { enter, exit } from '../lib/animate';
import { resolveEase } from '../lib/easing';
import type { BuildContext, BuiltElement } from './index';

export function statCounter({ element, centreY }: BuildContext): BuiltElement {
  if (element.payload.kind !== 'counter') {
    throw new Error(`statCounter expects a counter element, got ${element.payload.kind}`);
  }
  const { from, to, prefix, suffix, decimals } = element.payload;
  const { style, color } = element;

  const value = createSignal(from);
  const node = new Layout({ y: centreY, layout: true, direction: 'column', alignItems: 'center' });

  node.add(
    new Txt({
      text: () => `${prefix}${value().toFixed(decimals)}${suffix}`,
      fontFamily: [style.family, ...(style.fallback ?? [])].join(', '),
      fontWeight: style.weight,
      fontSize: style.size * 1.6,
      letterSpacing: style.tracking * style.size,
      fill: color,
    }),
  );

  const travel = TRAVEL_PX[element.enter.anim] ?? 0;

  function* timeline(sceneIn: number): ThreadGenerator {
    node.opacity(0);
    yield* waitFor(element.enter.at - sceneIn);
    // The roll runs longer than the entrance: the number arriving and *then*
    // counting is the beat that makes a stat land.
    yield* all(
      enter(node, element, travel),
      value(to, element.enter.dur * 2.6, resolveEase('expo.out')),
    );
    if (element.exit) {
      yield* chain(
        waitFor(Math.max(0, element.exit.at - element.enter.at - element.enter.dur * 2.6)),
        exit(node, element.exit),
      );
    }
  }

  return { node, timeline };
}
