import { makeScene2D } from '@motion-canvas/2d';

import spec from '../../data/spec.json';
import tokens from '../../data/brand.json';
import { compile } from '../lib/compile';
import { renderPlan } from '../lib/render';
import type { BrandTokens, SceneSpec } from '../lib/spec';

export default makeScene2D(function* (view) {
  const plan = compile(spec as unknown as SceneSpec, tokens as unknown as BrandTokens);
  yield* renderPlan(view, plan);
});
