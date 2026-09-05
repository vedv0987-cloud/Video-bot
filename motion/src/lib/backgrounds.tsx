/**
 * Procedural background systems.
 *
 * Photography for health topics is, in the freely-licensed pool, mostly
 * clinical documentation — so the visual language is generated rather than
 * sourced. Three systems, cycled across scenes so a five-scene cut does not
 * read as one flat card repeated.
 *
 * All of them are deliberately quiet. A background that competes with the type
 * is a failure however pretty it is.
 */

import { Circle, Gradient, Layout, Line, Node, Rect } from '@motion-canvas/2d';
import { all, waitFor, type ThreadGenerator } from '@motion-canvas/core';

import { resolveEase } from './easing';
import { mulberry32 } from './random';
import type { PlannedScene, RenderPlan } from './compile';

export interface Background {
  node: Node;
  animate(): ThreadGenerator;
}

function gradientMesh(plan: RenderPlan, scene: PlannedScene): Background {
  const random = mulberry32(scene.bg.seed ?? 1);
  const node = new Layout({});

  node.add(
    new Rect({
      width: plan.width,
      height: plan.height,
      fill: new Gradient({
        type: 'linear',
        from: [0, -plan.height / 2],
        to: [0, plan.height / 2],
        stops: plan.gradient.map((color, index) => ({
          offset: plan.gradient.length === 1 ? index : index / (plan.gradient.length - 1),
          color,
        })),
      }),
    }),
  );

  // Large, heavily blurred blobs in the accent colour. At this radius and
  // opacity they read as depth in the ground, not as shapes.
  const blobs = Array.from({ length: 3 }, (_, index) => {
    const blob = new Circle({
      size: plan.width * (0.9 + random() * 0.6),
      x: (random() - 0.5) * plan.width,
      y: (random() - 0.5) * plan.height * 0.8,
      fill: index === 0 ? plan.accent : plan.accentAlt,
      opacity: 0.1,
    });
    blob.filters.blur(plan.width * 0.16);
    node.add(blob);
    return blob;
  });

  return {
    node,
    *animate() {
      const ease = resolveEase('sine.inOut');
      yield* all(
        ...blobs.map((blob, index) =>
          all(
            blob.position(
              [blob.position.x() + (index % 2 ? 1 : -1) * plan.width * 0.14, blob.position.y() - plan.height * 0.06],
              scene.duration,
              ease,
            ),
            blob.scale(1.14, scene.duration, ease),
          ),
        ),
      );
    },
  };
}

function particleField(plan: RenderPlan, scene: PlannedScene): Background {
  const random = mulberry32(scene.bg.seed ?? 1);
  const node = new Layout({});

  node.add(
    new Rect({
      width: plan.width,
      height: plan.height,
      fill: new Gradient({
        type: 'linear',
        from: [0, -plan.height / 2],
        to: [0, plan.height / 2],
        stops: plan.gradient.map((color, index) => ({
          offset: plan.gradient.length === 1 ? index : index / (plan.gradient.length - 1),
          color,
        })),
      }),
    }),
  );

  const count = Math.round(70 * (scene.bg.density ?? 1));
  const dots = Array.from({ length: count }, () => {
    const size = plan.width * (0.003 + random() * 0.009);
    const dot = new Circle({
      size,
      x: (random() - 0.5) * plan.width,
      y: (random() - 0.5) * plan.height,
      fill: random() > 0.75 ? plan.accent : plan.inkMuted,
      opacity: 0.1 + random() * 0.35,
    });
    node.add(dot);
    return { dot, rise: plan.height * (0.05 + random() * 0.12) };
  });

  return {
    node,
    *animate() {
      const ease = resolveEase('sine.inOut');
      // A slow upward drift: the field reads as suspended particles rather
      // than as a static texture.
      yield* all(
        ...dots.map(({ dot, rise }) => dot.position.y(dot.position.y() - rise, scene.duration, ease)),
      );
    },
  };
}

function gridLines(plan: RenderPlan, scene: PlannedScene): Background {
  const node = new Layout({});

  node.add(
    new Rect({
      width: plan.width,
      height: plan.height,
      fill: new Gradient({
        type: 'linear',
        from: [0, -plan.height / 2],
        to: [0, plan.height / 2],
        stops: plan.gradient.map((color, index) => ({
          offset: plan.gradient.length === 1 ? index : index / (plan.gradient.length - 1),
          color,
        })),
      }),
    }),
  );

  const spacing = plan.height / 16;
  const rows = Math.ceil(plan.height / spacing) + 2;
  const lines = Array.from({ length: rows }, (_, index) => {
    const line = new Line({
      points: [
        [-plan.width / 2, 0],
        [plan.width / 2, 0],
      ],
      y: -plan.height / 2 + index * spacing,
      stroke: plan.inkMuted,
      lineWidth: 2,
      opacity: 0.08,
    });
    node.add(line);
    return line;
  });

  return {
    node,
    *animate() {
      // Parallax by exactly one row, so the loop is seamless.
      yield* all(
        ...lines.map((line) =>
          line.position.y(line.position.y() + spacing, scene.duration, resolveEase('sine.inOut')),
        ),
      );
    },
  };
}

export function buildBackground(plan: RenderPlan, scene: PlannedScene): Background {
  switch (scene.bg.type) {
    case 'particle-field':
      return particleField(plan, scene);
    case 'grid-lines':
      return gridLines(plan, scene);
    case 'solid':
      return {
        node: new Rect({ width: plan.width, height: plan.height, fill: plan.background }),
        *animate() {
          yield* waitFor(scene.duration);
        },
      };
    default:
      return gradientMesh(plan, scene);
  }
}
