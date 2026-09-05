/**
 * Items that arrive one after another.
 *
 * The stagger is the whole point: simultaneous entrances read as a slide,
 * staggered ones read as choreography (UPGRADE-PLAN §5.1). Per-item delays are
 * computed by the compiler from the brand's stagger token.
 */

import { Layout, Txt } from '@motion-canvas/2d';
import { all, chain, waitFor, type ThreadGenerator } from '@motion-canvas/core';

import { TRAVEL_PX } from '../lib/compile';
import { enter, exit } from '../lib/animate';
import type { BuildContext, BuiltElement } from './index';

export function listReveal({ element, plan, contentWidth, centreY }: BuildContext): BuiltElement {
  if (element.payload.kind !== 'list') {
    throw new Error(`listReveal expects a list element, got ${element.payload.kind}`);
  }
  const { style, color } = element;
  const gap = plan.radius;

  const node = new Layout({
    y: centreY,
    layout: true,
    direction: 'column',
    gap,
    alignItems: 'start',
    width: contentWidth,
  });

  const rows = element.payload.items.map(({ text, delay }) => {
    const row = new Txt({
      text,
      fontFamily: [style.family, ...(style.fallback ?? [])].join(', '),
      fontWeight: style.weight,
      fontSize: style.size,
      letterSpacing: style.tracking * style.size,
      lineHeight: style.leading * style.size,
      fill: color,
      textWrap: true,
      maxWidth: contentWidth,
      opacity: 0,
    });
    node.add(row);
    return { row, delay };
  });

  const travel = TRAVEL_PX[element.enter.anim] ?? 0;

  function* timeline(sceneIn: number): ThreadGenerator {
    yield* waitFor(element.enter.at - sceneIn);
    yield* all(
      ...rows.map(({ row, delay }) =>
        chain(waitFor(delay), enter(row, element, travel)),
      ),
    );
    if (element.exit) {
      const lastIn = rows.length ? rows[rows.length - 1].delay + element.enter.dur : element.enter.dur;
      yield* chain(
        waitFor(Math.max(0, element.exit.at - element.enter.at - lastIn)),
        // Leave together — a staggered exit draws attention to the departure
        // rather than to what comes next.
        all(...rows.map(({ row }) => exit(row, element.exit!))),
      );
    }
  }

  return { node, timeline };
}
