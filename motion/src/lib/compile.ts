/**
 * Scene spec → render plan.
 *
 * Pure, engine-independent, and the piece worth testing. It resolves brand
 * tokens into concrete values, expands list staggers into per-item delays, and
 * decides motion blur per element — leaving the Motion Canvas layer as a thin
 * interpreter over the result. If the engine is ever swapped, this survives.
 */

import { resolveEase } from './easing';
import type {
  BrandTokens,
  Element,
  Role,
  Scene,
  SceneSpec,
  Transition,
  TypeStyle,
} from './spec';

export class CompileError extends Error {}

/**
 * How far each named entrance travels, in authoring pixels.
 *
 * Motion blur is a function of speed, so the compiler has to know distance.
 * An animation missing from this table is a compile error rather than a
 * silent zero — an unblurred fast move is exactly the artefact §5.2 exists to
 * prevent.
 */
export const TRAVEL_PX: Record<string, number> = {
  'rise-blur': 140,
  'fade-scale': 0,
  'fade': 0,
  'pop': 0,
  'slide-left': 720,
  'slide-right': 720,
  'wipe-up': 300,
};

const ROLE_TYPE: Record<Role, string> = {
  display: 'display',
  headline: 'headline',
  body: 'body',
  caption: 'caption',
  accent: 'headline',
};

const ROLE_COLOR: Record<Role, string> = {
  display: 'ink',
  headline: 'ink',
  body: 'ink_muted',
  caption: 'ink',
  accent: 'accent',
};

export interface PlannedTiming {
  at: number;
  dur: number;
  ease: string;
  anim: string;
}

export interface PlannedBlur {
  enabled: boolean;
  samples: number;
  shutterDeg: number;
  speedPxPerS: number;
}

export type PlannedPayload =
  | { kind: 'text'; content: string }
  | { kind: 'counter'; from: number; to: number; prefix: string; suffix: string; decimals: number }
  | { kind: 'list'; items: { text: string; delay: number }[] }
  | { kind: 'image'; src: string; fit: 'cover' | 'contain' }
  | { kind: 'shape'; shape: string; token: string };

export interface PlannedElement {
  id: string;
  role: Role;
  style: TypeStyle;
  color: string;
  enter: PlannedTiming;
  exit: PlannedTiming | null;
  blur: PlannedBlur;
  payload: PlannedPayload;
  cite: string | null;
}

export interface PlannedScene {
  id: string;
  in: number;
  out: number;
  duration: number;
  layout: string;
  bg: Scene['bg'];
  elements: PlannedElement[];
}

export interface RenderPlan {
  slug: string;
  topic: string;
  fps: number;
  width: number;
  height: number;
  duration: number;
  background: string;
  gradient: string[];
  safe: { top: number; right: number; bottom: number; left: number };
  margin: { x: number; y: number };
  radius: number;
  scenes: PlannedScene[];
}

function colorToken(tokens: BrandTokens, name: string): string {
  const value = tokens.color[name];
  if (typeof value !== 'string') {
    throw new CompileError(`brand colour "${name}" is missing or not a single value`);
  }
  return value;
}

function timing(transition: Transition): PlannedTiming {
  // Resolve now so a bad curve fails at compile time rather than at frame one.
  resolveEase(transition.ease);
  return {
    at: transition.at,
    dur: transition.dur,
    ease: transition.ease,
    anim: transition.anim,
  };
}

function blurFor(tokens: BrandTokens, anim: string, dur: number): PlannedBlur {
  const travel = TRAVEL_PX[anim];
  if (travel === undefined) {
    throw new CompileError(
      `animation "${anim}" has no travel distance in TRAVEL_PX; ` +
        'add one so motion blur can be decided (UPGRADE-PLAN §5.2)',
    );
  }
  const { samples, shutter_deg, threshold_px_per_s } = tokens.motion.motion_blur;
  const speed = dur > 0 ? travel / dur : 0;
  return {
    enabled: speed > threshold_px_per_s,
    samples,
    shutterDeg: shutter_deg,
    speedPxPerS: Math.round(speed),
  };
}

function payloadFor(element: Element, tokens: BrandTokens): PlannedPayload {
  switch (element.type) {
    case 'text':
      return { kind: 'text', content: element.content };
    case 'counter':
      return {
        kind: 'counter',
        from: element.from,
        to: element.to,
        prefix: element.prefix ?? '',
        suffix: element.suffix ?? '',
        decimals: element.decimals ?? 0,
      };
    case 'list': {
      // Siblings entering together read as a slide; staggering reads as
      // choreography (§5.1). The spec may override the brand default.
      const step = (element.stagger_ms ?? tokens.motion.stagger_ms) / 1000;
      return {
        kind: 'list',
        items: element.items.map((text, index) => ({ text, delay: +(index * step).toFixed(3) })),
      };
    }
    case 'image':
      return {
        kind: 'image',
        src: typeof element.src === 'string' ? element.src : element.src.path,
        fit: element.fit ?? 'cover',
      };
    case 'shape':
      return { kind: 'shape', shape: element.shape, token: element.token ?? 'surface' };
  }
}

function compileElement(element: Element, scene: Scene, tokens: BrandTokens): PlannedElement {
  const enter = timing(element.in);
  const exit = element.out ? timing(element.out) : null;

  const enterEnd = enter.at + enter.dur;
  if (enter.at < scene.in - 1e-3 || enterEnd > scene.out + 1e-3) {
    throw new CompileError(
      `${scene.id}/${element.id}: entrance ${enter.at}-${enterEnd} falls outside ` +
        `scene ${scene.in}-${scene.out}`,
    );
  }

  const styleName = ROLE_TYPE[element.role];
  const style = tokens.type[styleName];
  if (!style) throw new CompileError(`brand type style "${styleName}" is missing`);

  return {
    id: element.id,
    role: element.role,
    style,
    color: colorToken(tokens, ROLE_COLOR[element.role]),
    enter,
    exit,
    blur: blurFor(tokens, enter.anim, enter.dur),
    payload: payloadFor(element, tokens),
    cite: element.cite ?? null,
  };
}

export function compile(spec: SceneSpec, tokens: BrandTokens): RenderPlan {
  if (spec.version !== '1.0') {
    throw new CompileError(`unsupported spec version ${spec.version}`);
  }
  if (spec.brand.id !== tokens.id) {
    throw new CompileError(
      `spec was built against brand "${spec.brand.id}" but tokens are "${tokens.id}" — ` +
        'rendering with the wrong brand silently changes the design',
    );
  }

  const gradient = spec.brand ? tokens.color.gradient : undefined;
  const [width, height] = spec.meta.resolution;
  const safe = spec.meta.safe_area;

  return {
    slug: spec.meta.slug,
    topic: spec.meta.topic,
    fps: spec.meta.fps,
    width,
    height,
    duration: spec.meta.duration_s,
    background: colorToken(tokens, 'bg'),
    gradient: Array.isArray(gradient) ? gradient : [colorToken(tokens, 'bg')],
    safe: {
      top: Math.round(safe.top * height),
      right: Math.round(safe.right * width),
      bottom: Math.round(safe.bottom * height),
      left: Math.round(safe.left * width),
    },
    margin: { x: tokens.space.margin_x, y: tokens.space.margin_y },
    radius: tokens.space.radius,
    scenes: spec.scenes.map((scene) => ({
      id: scene.id,
      in: scene.in,
      out: scene.out,
      duration: +(scene.out - scene.in).toFixed(3),
      layout: scene.layout,
      bg: scene.bg,
      elements: scene.elements.map((element) => compileElement(element, scene, tokens)),
    })),
  };
}
