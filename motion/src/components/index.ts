/**
 * Component library.
 *
 * One builder per element kind. Each returns its node and its own timeline, so
 * a component that needs bespoke choreography (a staggered list, a rolling
 * counter) can define it, while simple ones delegate to the shared lifecycle.
 */

import { Node } from '@motion-canvas/2d';
import type { ThreadGenerator } from '@motion-canvas/core';

import type { PlannedElement, RenderPlan } from '../lib/compile';
import type { Word } from '../lib/spec';

export interface BuildContext {
  element: PlannedElement;
  plan: RenderPlan;
  /** Usable width inside the horizontal margins, in authoring pixels. */
  contentWidth: number;
  /** Vertical centre of the safe band, as an offset from frame centre. */
  centreY: number;
  /** Words spoken during this scene, in scene-relative time. */
  words: Word[];
}

export interface BuiltElement {
  node: Node;
  timeline(sceneIn: number): ThreadGenerator;
}

export { kineticText } from './KineticText';
export { statementCard } from './StatementCard';
export { statCounter } from './StatCounter';
export { listReveal } from './ListReveal';
export { lowerThird } from './LowerThird';
export { endCard } from './EndCard';
