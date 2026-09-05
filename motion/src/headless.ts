/**
 * Headless frame rendering.
 *
 * Motion Canvas's own renderer exports through the dev server; this drives
 * PlaybackManager and Stage directly so frames can be pulled from a plain
 * headless browser. Used for stills in CI and for eyeballing a change without
 * opening the editor.
 */

import {
  Logger,
  PlaybackManager,
  PlaybackStatus,
  SharedWebGLContext,
  Stage,
  Vector2,
} from '@motion-canvas/core';

// Self-hosted so a render never depends on a font CDN, and so the same bytes
// produce the same frame on any machine. Variable, because §5.5 animates the
// weight axis rather than only position and opacity.
import '@fontsource-variable/inter';

// Not re-exported from the package root, so reach for it directly.
import { ReadOnlyTimeEvents } from '@motion-canvas/core/lib/scenes/timeEvents';

import project from './project';

declare global {
  interface Window {
    videobotRender: (seconds: number) => Promise<string>;
    videobotDuration: () => number;
  }
}

const WIDTH = Number(new URLSearchParams(location.search).get('w') ?? 2160);
const HEIGHT = Number(new URLSearchParams(location.search).get('h') ?? 3840);
const SCALE = Number(new URLSearchParams(location.search).get('scale') ?? 0.25);
const FPS = Number(new URLSearchParams(location.search).get('fps') ?? 30);

const size = new Vector2(WIDTH, HEIGHT);
// makeProject leaves `logger` optional; the scene constructor requires one.
const logger = project.logger ?? new Logger();
const playback = new PlaybackManager();
const status = new PlaybackStatus(playback);
const sharedWebGLContext = new SharedWebGLContext(logger);

const scenes = project.scenes.map((description) => {
  const scene = new description.klass({
    ...description,
    playback: status,
    logger,
    size,
    resolutionScale: SCALE,
    sharedWebGLContext,
    // The editor uses EditableTimeEvents; a headless render never edits, and
    // the scene constructor requires *some* implementation.
    timeEventsClass: ReadOnlyTimeEvents,
    experimentalFeatures: project.experimentalFeatures,
  });
  scene.variables.updateSignals(project.variables ?? {});
  return scene;
});

playback.fps = FPS;
playback.setup(scenes);

const stage = new Stage();
stage.configure({ size, resolutionScale: SCALE });

// Canvas text silently falls back if the face has not finished loading, and a
// fallback font is the difference between the house style and Helvetica.
const ready = Promise.all([document.fonts.ready, playback.recalculate()]);

window.videobotDuration = () => playback.duration / FPS;

window.videobotRender = async (seconds: number) => {
  await ready;
  await playback.seek(Math.round(seconds * FPS));
  await stage.render(playback.currentScene, playback.previousScene);
  return stage.finalBuffer.toDataURL('image/png');
};
