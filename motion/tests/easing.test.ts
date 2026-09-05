import { describe, expect, it } from 'vitest';

import { backOut, EasingError, resolveEase } from '../src/lib/easing';

describe('easing', () => {
  it('resolves the curves the brand file names', () => {
    for (const token of ['expo.out', 'cubic.in', 'cubic.out', 'sine.inOut', 'back.out(1.4)']) {
      expect(typeof resolveEase(token)).toBe('function');
    }
  });

  it('rejects linear, matching the Python validator', () => {
    expect(() => resolveEase('linear')).toThrow(EasingError);
    expect(() => resolveEase('  LINEAR ')).toThrow(EasingError);
  });

  it('rejects an unknown curve rather than silently falling back', () => {
    expect(() => resolveEase('bounce.out')).toThrow(/unknown easing/);
  });

  it('honours the overshoot parameter', () => {
    // Larger overshoot must travel further past 1 at its peak.
    const gentle = backOut(1.0);
    const strong = backOut(2.5);
    const peak = (fn: (v: number) => number) =>
      Math.max(...Array.from({ length: 50 }, (_, i) => fn(0.5 + i / 100)));
    expect(peak(strong)).toBeGreaterThan(peak(gentle));
  });

  it('starts at 0 and ends at 1', () => {
    for (const token of ['expo.out', 'cubic.in', 'back.out(1.4)']) {
      const fn = resolveEase(token);
      expect(fn(0)).toBeCloseTo(0, 5);
      expect(fn(1)).toBeCloseTo(1, 5);
    }
  });
});
