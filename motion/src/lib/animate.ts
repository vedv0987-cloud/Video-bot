/**
 * Entrance and exit primitives.
 *
 * Every motion in the system comes through here, so the craft rules in
 * UPGRADE-PLAN §5.1–5.2 are enforced in one place rather than remembered at
 * each call site.
 *
 * On motion blur: this applies a blur that decays as the element settles,
 * scaled by how fast it is travelling. That is the standard 2D-motion-design
 * approximation, not true sub-frame accumulation — real accumulation belongs
 * in the finishing stage or in Blender. The compiler decides *whether* to blur
 * from the speed threshold; this decides how much.
 */

import { Node } from '@motion-canvas/2d';
import { all, chain, waitFor, type ThreadGenerator } from '@motion-canvas/core';

import { resolveEase } from './easing';
import type { PlannedElement, PlannedTiming, PlannedBlur } from './compile';

const BLUR_PX_PER_1000_SPEED = 6;
const MAX_BLUR_PX = 24;

export function blurAmount(blur: PlannedBlur): number {
  if (!blur.enabled) return 0;
  return Math.min(MAX_BLUR_PX, (blur.speedPxPerS / 1000) * BLUR_PX_PER_1000_SPEED);
}

/** Where an element starts, relative to its resting position. */
export function entryOffset(anim: string, travel: number): [number, number] {
  switch (anim) {
    case 'rise-blur':
      return [0, travel];
    case 'wipe-up':
      return [0, travel];
    case 'slide-left':
      return [travel, 0];
    case 'slide-right':
      return [-travel, 0];
    default:
      return [0, 0];
  }
}

export function* enter(node: Node, element: PlannedElement, travel: number): ThreadGenerator {
  const { enter: timing, blur } = element;
  const ease = resolveEase(timing.ease);
  const [dx, dy] = entryOffset(timing.anim, travel);
  const rest = node.position();
  const amount = blurAmount(blur);

  node.position([rest.x + dx, rest.y + dy]);
  node.opacity(0);
  if (timing.anim === 'pop' || timing.anim === 'fade-scale') node.scale(0.92);
  if (amount > 0) node.filters.blur(amount);

  yield* all(
    node.position(rest, timing.dur, ease),
    node.opacity(1, timing.dur * 0.8, ease),
    node.scale(1, timing.dur, ease),
    // Settle the blur faster than the move, so the element reads sharp
    // before it stops rather than arriving soft.
    amount > 0 ? node.filters.blur(0, timing.dur * 0.6, ease) : waitFor(0),
  );
}

export function* exit(node: Node, timing: PlannedTiming): ThreadGenerator {
  const ease = resolveEase(timing.ease);
  yield* all(
    node.opacity(0, timing.dur, ease),
    timing.anim === 'fade-scale' ? node.scale(0.96, timing.dur, ease) : waitFor(0),
  );
}

/**
 * One element's full life within its scene, in scene-relative time.
 *
 * Elements are queued in parallel by the caller; each waits out its own lead-in
 * rather than being sequenced, which is what lets a stagger read as
 * choreography instead of a queue.
 */
export function* lifecycle(
  node: Node,
  element: PlannedElement,
  sceneIn: number,
  travel: number,
): ThreadGenerator {
  node.opacity(0);
  yield* chain(
    waitFor(element.enter.at - sceneIn),
    enter(node, element, travel),
    element.exit
      ? chain(
          waitFor(Math.max(0, element.exit.at - element.enter.at - element.enter.dur)),
          exit(node, element.exit),
        )
      : waitFor(0),
  );
}
