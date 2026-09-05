import type { BrandTokens, SceneSpec } from '../src/lib/spec';

export const tokens: BrandTokens = {
  id: 'health-v2',
  name: 'Health v2',
  color: {
    bg: '#0b1220',
    surface: '#111c2e',
    ink: '#f2f6ff',
    ink_muted: '#9aa9c4',
    accent: '#38e0a6',
    accent_alt: '#4c8dff',
    gradient: ['#0b1220', '#16304a'],
  },
  type: {
    display: { family: 'Inter', weight: 800, size: 148, tracking: -0.022, leading: 1.02 },
    headline: { family: 'Inter', weight: 700, size: 96, tracking: -0.015, leading: 1.12 },
    body: { family: 'Inter', weight: 500, size: 62, tracking: -0.005, leading: 1.32 },
    caption: { family: 'Inter', weight: 800, size: 84, tracking: -0.01, leading: 1.15 },
  },
  space: { unit: 16, margin_x: 192, margin_y: 260, radius: 56 },
  motion: {
    ease: {
      entrance: 'expo.out',
      exit: 'cubic.in',
      emphasis: 'back.out(1.4)',
      counter: 'expo.out',
      ambient: 'sine.inOut',
    },
    duration_ms: { entrance: 400, exit: 220, emphasis: 300, counter: 1050, ambient: 12000 },
    stagger_ms: 75,
    motion_blur: { shutter_deg: 180, samples: 6, threshold_px_per_s: 600 },
  },
  captions: {
    style: 'karaoke-pop',
    max_words: 3,
    active_color: '#38e0a6',
    idle_color: '#f2f6ff',
  },
};

export function spec(overrides: Partial<SceneSpec> = {}): SceneSpec {
  return {
    version: '1.0',
    meta: {
      topic: 'dehydration',
      slug: 'dehydration',
      duration_s: 6,
      aspect: '9:16',
      fps: 30,
      resolution: [2160, 3840],
      safe_area: { name: 'social-9x16', top: 0.12, right: 0.06, bottom: 0.2, left: 0.06 },
    },
    brand: { id: 'health-v2', digest: 'abcdef1234567890' },
    audio: {
      vo: null,
      music: null,
      beats: [],
      words: [
        { w: 'You', t0: 0.4, t1: 0.7 },
        { w: 'are', t0: 0.76, t1: 1.0 },
        { w: 'water.', t0: 1.06, t1: 1.6 },
      ],
      provenance: {
        voice: { backend: 'null', model: 'silence' },
        alignment: { method: 'estimated' },
        beats: { method: 'fixed-tempo', bpm: 92 },
      },
    },
    scenes: [
      {
        id: 'hook',
        in: 0,
        out: 6,
        tier: 'A',
        layout: 'statement-center',
        bg: { type: 'gradient-mesh', seed: 1, drift: 0.02, density: 1 },
        words: { from: 0, to: 2 },
        transition: { type: 'cut', dur: 0 },
        media: null,
        elements: [
          {
            type: 'text',
            id: 'lead',
            role: 'display',
            content: 'You are mostly water.',
            in: { at: 0.35, anim: 'rise-blur', ease: 'expo.out', dur: 0.4 },
            out: { at: 5.3, anim: 'fade-scale', ease: 'cubic.in', dur: 0.22 },
          },
        ],
      },
    ],
    captions: { style: 'karaoke-pop', max_words: 3, safe_area: 'social-9x16' },
    citations: [],
    compliance: { gate: 'pending', requires_human_signoff: true },
    ...overrides,
  };
}
