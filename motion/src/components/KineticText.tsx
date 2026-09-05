/**
 * Word-by-word type, synced to the voiceover.
 *
 * Each word lands as it is spoken, using the alignment already in the spec.
 * The word being spoken carries the accent colour and settles to ink as the
 * voice moves on; words not yet reached are not drawn.
 *
 * That makes the card *be* the caption rather than duplicating it in a strip
 * at the bottom — both the current short-form idiom and the honest answer to
 * having one piece of text and one voice reading it.
 *
 * Falls back to a block reveal when the alignment does not cover this text, so
 * an unaligned run still renders something deliberate rather than guessing.
 */

import { Layout, Txt } from '@motion-canvas/2d';
import { all, chain, waitFor, type ThreadGenerator } from '@motion-canvas/core';

import { TRAVEL_PX } from '../lib/compile';
import { exit, lifecycle } from '../lib/animate';
import { resolveEase } from '../lib/easing';
import type { BuildContext, BuiltElement } from './index';

/** Words land slightly before they are voiced; reading lags hearing. */
const LEAD_S = 0.06;

export function kineticText(ctx: BuildContext): BuiltElement {
  const { element, plan, contentWidth, centreY, words } = ctx;
  if (element.payload.kind !== 'text') {
    throw new Error(`kineticText expects a text element, got ${element.payload.kind}`);
  }
  const { style, color } = element;
  const tokens = element.payload.content.split(/\s+/).filter(Boolean);

  const node = new Layout({
    y: centreY,
    layout: true,
    direction: 'row',
    wrap: 'wrap',
    justifyContent: 'center',
    alignItems: 'center',
    gap: style.size * 0.24,
    width: contentWidth,
  });

  const fontFamily = [style.family, ...(style.fallback ?? [])].join(', ');
  const parts = tokens.map((text) => {
    const part = new Txt({
      text,
      fontFamily,
      fontWeight: style.weight,
      fontSize: style.size,
      letterSpacing: style.tracking * style.size,
      lineHeight: style.leading * style.size,
      fill: color,
      opacity: 0,
    });
    node.add(part);
    return part;
  });

  const travel = TRAVEL_PX[element.enter.anim] ?? 0;
  const synced = words.length === parts.length && parts.length > 0;

  function* timeline(sceneIn: number): ThreadGenerator {
    if (!synced) {
      yield* lifecycle(node, element, sceneIn, travel);
      return;
    }

    node.opacity(1);
    const ease = resolveEase('expo.out');

    yield* all(
      ...parts.map((part, index) => {
        const word = words[index];
        return chain(
          waitFor(Math.max(0, word.t0 - LEAD_S)),
          all(
            part.opacity(1, element.enter.dur * 0.5, ease),
            part.scale(1, element.enter.dur * 0.5, ease),
            chain(
              waitFor(Math.max(0.08, word.t1 - word.t0)),
              part.fill(color, 0.22, ease),
            ),
          ),
        );
      }),
    );

    if (element.exit) {
      const lastEnd = words[words.length - 1]?.t1 ?? 0;
      yield* chain(
        waitFor(Math.max(0, element.exit.at - sceneIn - lastEnd)),
        exit(node, element.exit),
      );
    }
  }

  // Start accented and slightly small; the timeline settles both.
  if (synced) {
    parts.forEach((part) => {
      part.fill(plan.accent);
      part.scale(0.9);
    });
  }

  return { node, timeline };
}
