/**
 * Seeded pseudo-random numbers.
 *
 * Backgrounds are generated, not authored, so they need randomness — but a
 * render must be reproducible, and `Math.random` would make every frame of
 * every run different. mulberry32: small, fast, good enough for scatter.
 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
