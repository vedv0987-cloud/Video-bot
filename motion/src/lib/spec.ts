/**
 * TypeScript view of scene-spec.json.
 *
 * Mirrors src/videobot/schema/scene-spec.schema.json. The Python side owns the
 * schema; this is the reader's contract. Keep them in step — a field added
 * there and missed here shows up as `undefined` at render time, not as a type
 * error.
 */

export type Aspect = '9:16' | '1:1' | '16:9';
export type Tier = 'A' | 'B' | 'C';
export type Role = 'display' | 'headline' | 'body' | 'caption' | 'accent';

export interface Transition {
  at: number;
  anim: string;
  ease: string;
  dur: number;
  snap?: 'beat' | 'none';
}

interface ElementBase {
  id: string;
  role: Role;
  in: Transition;
  out: Transition | null;
  cite?: string;
}

export interface TextElement extends ElementBase {
  type: 'text';
  content: string;
}

export interface CounterElement extends ElementBase {
  type: 'counter';
  from: number;
  to: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
}

export interface ListElement extends ElementBase {
  type: 'list';
  items: string[];
  stagger_ms?: number;
}

export interface ImageElement extends ElementBase {
  type: 'image';
  src: string | { path: string };
  fit?: 'cover' | 'contain';
}

export interface ShapeElement extends ElementBase {
  type: 'shape';
  shape: 'plate' | 'rule' | 'dot' | 'ring';
  token?: string;
}

export type Element =
  | TextElement
  | CounterElement
  | ListElement
  | ImageElement
  | ShapeElement;

export type BackgroundKind = 'gradient-mesh' | 'particle-field' | 'grid-lines' | 'solid';

export interface SceneMedia {
  kind: 'image' | 'video';
  src: string;
  credit: string;
  licence: string;
  page?: string;
  /** Seconds into the source clip. Video only. */
  trim?: { from: number; to: number };
  treatment: {
    move: 'ken-burns-in' | 'ken-burns-out' | 'pan-left' | 'pan-right' | 'hold';
    scale_from: number;
    scale_to: number;
  };
}

export interface Scene {
  id: string;
  in: number;
  out: number;
  tier: Tier;
  layout: string;
  bg: { type: BackgroundKind; seed?: number; drift?: number; density?: number };
  words: { from: number; to: number };
  transition: { type: 'cut' | 'dip' | 'push-up' | 'wipe'; dur: number };
  media?: SceneMedia | null;
  elements: Element[];
}

export interface Word {
  w: string;
  t0: number;
  t1: number;
}

export interface SceneSpec {
  version: '1.0';
  meta: {
    topic: string;
    slug: string;
    duration_s: number;
    aspect: Aspect;
    fps: number;
    resolution: [number, number];
    safe_area: { name: string; top: number; right: number; bottom: number; left: number };
  };
  brand: { id: string; digest: string };
  audio: {
    vo: { node: string; digest: string; path: string } | null;
    music: unknown | null;
    beats: number[];
    words: Word[];
    provenance: {
      voice: { backend: string; model: string };
      alignment: { method: string };
      beats: { method: string; bpm: number };
    };
  };
  scenes: Scene[];
  captions: { style: string; max_words: number; safe_area: string };
  citations: { id: string; claim: string; source: string; url?: string; verified: boolean }[];
  compliance: { gate: 'pending' | 'passed' | 'failed'; requires_human_signoff: true; notes?: string[] };
}

export interface TypeStyle {
  family: string;
  fallback?: string[];
  weight: number;
  size: number;
  tracking: number;
  leading: number;
}

export interface BrandTokens {
  id: string;
  name: string;
  color: Record<string, string | string[]>;
  type: Record<string, TypeStyle>;
  space: { unit: number; margin_x: number; margin_y: number; radius: number };
  motion: {
    ease: Record<string, string>;
    duration_ms: Record<string, number>;
    stagger_ms: number;
    motion_blur: { shutter_deg: number; samples: number; threshold_px_per_s: number };
  };
  captions: {
    style: string;
    max_words: number;
    active_color: string;
    idle_color: string;
    outline_px?: number;
  };
  grade?: { lut?: string };
}
