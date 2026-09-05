/**
 * Easing token → timing function.
 *
 * The brand file names curves ("expo.out"); this resolves them. Linear is
 * rejected rather than supported, mirroring the Python validator — the motion
 * contract has one rule and it is enforced on both sides of the seam.
 */

import {
  easeInCubic,
  easeInOutCubic,
  easeInOutSine,
  easeInQuad,
  easeOutCubic,
  easeOutExpo,
  easeOutQuad,
  type TimingFunction,
} from '@motion-canvas/core';

export class EasingError extends Error {}

/**
 * Overshoot-and-settle. Motion Canvas ships a fixed-overshoot easeOutBack;
 * the brand file parameterises it, so we build it here to honour the token.
 */
export function backOut(overshoot: number): TimingFunction {
  const c = overshoot;
  return (value: number) => 1 + (c + 1) * Math.pow(value - 1, 3) + c * Math.pow(value - 1, 2);
}

const TABLE: Record<string, TimingFunction> = {
  'expo.out': easeOutExpo,
  'cubic.out': easeOutCubic,
  'cubic.in': easeInCubic,
  'cubic.inOut': easeInOutCubic,
  'quad.out': easeOutQuad,
  'quad.in': easeInQuad,
  'sine.inOut': easeInOutSine,
};

const BACK = /^back\.out\(([\d.]+)\)$/;

export function resolveEase(token: string): TimingFunction {
  const name = token.trim();

  if (name.toLowerCase() === 'linear') {
    throw new EasingError(
      "linear easing is banned by the motion contract (UPGRADE-PLAN §5.1) — " +
        'it is the single clearest tell of generated video',
    );
  }

  const back = BACK.exec(name);
  if (back) return backOut(Number(back[1]));

  const fn = TABLE[name];
  if (!fn) {
    throw new EasingError(
      `unknown easing "${name}"; expected one of ${Object.keys(TABLE).join(', ')} or back.out(n)`,
    );
  }
  return fn;
}
