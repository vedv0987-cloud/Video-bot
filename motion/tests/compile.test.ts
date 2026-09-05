import { describe, expect, it } from 'vitest';

import { compile, CompileError, TRAVEL_PX } from '../src/lib/compile';
import { spec, tokens } from './fixtures';

describe('compile', () => {
  it('produces a plan from a valid spec', () => {
    const plan = compile(spec(), tokens);
    expect(plan.slug).toBe('dehydration');
    expect(plan.scenes).toHaveLength(1);
    expect(plan.scenes[0].duration).toBe(6);
  });

  it('refuses a spec built against a different brand', () => {
    const wrong = spec();
    wrong.brand.id = 'other-brand';
    expect(() => compile(wrong, tokens)).toThrow(/brand/);
  });

  it('rejects linear easing at compile time, not at frame one', () => {
    const bad = spec();
    bad.scenes[0].elements[0].in.ease = 'linear';
    expect(() => compile(bad, tokens)).toThrow(/linear/);
  });

  it('rejects an animation with no known travel distance', () => {
    const bad = spec();
    bad.scenes[0].elements[0].in.anim = 'teleport';
    expect(() => compile(bad, tokens)).toThrow(CompileError);
  });

  it('rejects an element that animates outside its scene', () => {
    const bad = spec();
    bad.scenes[0].elements[0].in.at = 5.9;
    bad.scenes[0].elements[0].in.dur = 0.4;
    expect(() => compile(bad, tokens)).toThrow(/outside/);
  });

  it('resolves the safe area into authoring pixels', () => {
    const plan = compile(spec(), tokens);
    expect(plan.safe).toEqual({ top: 461, right: 130, bottom: 768, left: 130 });
  });

  it('maps roles onto brand type styles and colours', () => {
    const plan = compile(spec(), tokens);
    const element = plan.scenes[0].elements[0];
    expect(element.style.size).toBe(tokens.type.display.size);
    expect(element.color).toBe(tokens.color.ink);
  });

  describe('motion blur', () => {
    it('is off for a short rise', () => {
      // 140px over 0.4s = 350 px/s, below the 600 threshold.
      const plan = compile(spec(), tokens);
      expect(plan.scenes[0].elements[0].blur.enabled).toBe(false);
      expect(plan.scenes[0].elements[0].blur.speedPxPerS).toBe(350);
    });

    it('is on for a fast slide', () => {
      const fast = spec();
      fast.scenes[0].elements[0].in.anim = 'slide-left';
      const plan = compile(fast, tokens);
      expect(plan.scenes[0].elements[0].blur.enabled).toBe(true);
      expect(plan.scenes[0].elements[0].blur.speedPxPerS).toBe(TRAVEL_PX['slide-left'] / 0.4);
    });

    it('carries the shutter and sample count from the brand', () => {
      const plan = compile(spec(), tokens);
      expect(plan.scenes[0].elements[0].blur.samples).toBe(6);
      expect(plan.scenes[0].elements[0].blur.shutterDeg).toBe(180);
    });
  });

  describe('list reveal', () => {
    function listSpec(staggerMs?: number) {
      const s = spec();
      s.scenes[0].layout = 'list-reveal';
      s.scenes[0].elements = [
        {
          type: 'list',
          id: 'points',
          role: 'body',
          items: ['one', 'two', 'three'],
          ...(staggerMs === undefined ? {} : { stagger_ms: staggerMs }),
          in: { at: 0.35, anim: 'rise-blur', ease: 'expo.out', dur: 0.4 },
          out: { at: 5.3, anim: 'fade-scale', ease: 'cubic.in', dur: 0.22 },
        },
      ];
      return s;
    }

    it('expands the brand stagger into per-item delays', () => {
      const plan = compile(listSpec(), tokens);
      const payload = plan.scenes[0].elements[0].payload;
      expect(payload.kind).toBe('list');
      if (payload.kind !== 'list') throw new Error('unreachable');
      expect(payload.items.map((i) => i.delay)).toEqual([0, 0.075, 0.15]);
    });

    it('lets the spec override the brand stagger', () => {
      const plan = compile(listSpec(200), tokens);
      const payload = plan.scenes[0].elements[0].payload;
      if (payload.kind !== 'list') throw new Error('unreachable');
      expect(payload.items.map((i) => i.delay)).toEqual([0, 0.2, 0.4]);
    });
  });

  it('carries a citation reference through to the plan', () => {
    const cited = spec();
    cited.scenes[0].elements[0].cite = 'c1';
    expect(compile(cited, tokens).scenes[0].elements[0].cite).toBe('c1');
  });
});
