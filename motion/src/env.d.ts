/**
 * The Motion Canvas vite plugin rewrites `*?scene` imports at build time and
 * ships no ambient declaration for them, so we state the shape here.
 */
declare module '*?scene' {
  import type { FullSceneDescription } from '@motion-canvas/core';
  const scene: FullSceneDescription;
  export default scene;
}
