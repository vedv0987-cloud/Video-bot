/**
 * Render the current spec to an MP4.
 *
 * Frames come out of headless Chromium one at a time and go to disk; ffmpeg
 * conforms, grades and encodes them with the voiceover. Grain and loudness
 * normalisation happen here rather than in the engine, because ffmpeg does
 * both better and at the right point in the chain.
 *
 *   node scripts/render.mjs [--scale 0.5] [--seconds 6] [--fps 30] [--out path.mp4]
 */

import { createServer } from 'vite';
import { chromium } from 'playwright';
import { spawn, spawnSync } from 'node:child_process';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const repo = resolve(root, '..');

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index === -1 ? fallback : process.argv[index + 1];
}

/**
 * A *full* ffmpeg. Playwright bundles a minimal build with no libx264, which
 * fails only at the encode step after every frame has been rendered — so
 * candidates are ordered by how likely they are to be complete, and the one
 * chosen is verified before any work is done.
 */
const FFMPEG_CANDIDATES = [
  process.env.FFMPEG_PATH,
  '/opt/homebrew/bin/ffmpeg',
  '/usr/local/bin/ffmpeg',
  '/usr/bin/ffmpeg',
  // pip install imageio-ffmpeg — a static build that always has libx264.
  ...(() => {
    const dir = '/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries';
    try {
      return readdirSync(dir).map((name) => resolve(dir, name));
    } catch {
      return [];
    }
  })(),
].filter((path) => path && existsSync(path));

function hasX264(binary) {
  const probe = spawnSync(binary, ['-hide_banner', '-encoders'], { encoding: 'utf8' });
  return probe.status === 0 && probe.stdout.includes('libx264');
}

const FFMPEG = FFMPEG_CANDIDATES.find(hasX264);
if (!FFMPEG) {
  console.error(
    'no ffmpeg with libx264 found. Install one:\n' +
      '  macOS:  brew install ffmpeg\n' +
      '  any:    pip install imageio-ffmpeg\n' +
      'or set FFMPEG_PATH.',
  );
  process.exit(2);
}

const spec = JSON.parse(readFileSync(resolve(root, 'data/spec.json'), 'utf8'));
const [width, height] = spec.meta.resolution;
const fps = Number(arg('fps', spec.meta.fps));
const scale = Number(arg('scale', '0.5'));
const duration = Math.min(Number(arg('seconds', spec.meta.duration_s)), spec.meta.duration_s);
const frameCount = Math.max(1, Math.round(duration * fps));

const outPath = resolve(root, arg('out', `../output/${spec.meta.slug}/${spec.meta.slug}-9x16.mp4`));
const frameDir = resolve(root, '.frames');

const [outW, outH] = [Math.round(width * scale), Math.round(height * scale)];
console.log(`${frameCount} frames · ${outW}x${outH} · ${fps}fps · ${duration.toFixed(2)}s`);

const server = await createServer({ root, configFile: resolve(root, 'vite.config.ts'), logLevel: 'error' });
await server.listen();
const port = server.config.server.port ?? server.httpServer.address().port;

const executablePath = process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium';
const browser = await chromium.launch({
  executablePath: existsSync(executablePath) ? executablePath : undefined,
  args: ['--no-sandbox', '--use-gl=swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 600, height: 400 } });
page.on('pageerror', (error) => console.error('page error:', error.message));

await page.goto(
  `http://localhost:${port}/headless.html?w=${width}&h=${height}&scale=${scale}&fps=${fps}`,
  { waitUntil: 'load' },
);
await page.waitForFunction(() => typeof window.videobotRender === 'function', null, { timeout: 60_000 });

const family = JSON.parse(readFileSync(resolve(root, 'data/brand.json'), 'utf8')).type.display.family;
if (!(await page.evaluate((f) => document.fonts.check(`700 100px "${f}"`), family))) {
  console.error(`WARNING: "${family}" did not load — frames will be in a fallback face`);
}

await rm(frameDir, { recursive: true, force: true });
await mkdir(frameDir, { recursive: true });

const started = Date.now();
for (let frame = 0; frame < frameCount; frame += 1) {
  const dataUrl = await page.evaluate((t) => window.videobotRender(t), frame / fps);
  await writeFile(
    resolve(frameDir, `${String(frame + 1).padStart(6, '0')}.png`),
    Buffer.from(dataUrl.split(',')[1], 'base64'),
  );
  if (frame % 30 === 0 || frame === frameCount - 1) {
    const done = frame + 1;
    const rate = done / ((Date.now() - started) / 1000);
    process.stdout.write(
      `\r  frames ${done}/${frameCount}  ${rate.toFixed(1)}/s  eta ${Math.round((frameCount - done) / rate)}s   `,
    );
  }
}
process.stdout.write('\n');

await browser.close();
await server.close();

await mkdir(dirname(outPath), { recursive: true });

const voPath = spec.audio?.vo?.path ? resolve(repo, spec.audio.vo.path) : null;
const hasAudio = voPath && existsSync(voPath);

/**
 * Footage, laid in under the graphics.
 *
 * Not drawn by the engine: Motion Canvas's Video node hangs this renderer,
 * because frames are pulled by seeking and screenshotting and an
 * HTMLVideoElement never becomes ready under that loop. ffmpeg decodes video
 * properly and is already in the chain, so footage scenes render transparent
 * and the clips go in here.
 *
 * Each clip is scaled to cover the frame, cropped to it, trimmed to its
 * scene's length, and shifted to the scene's start. The graphics sequence goes
 * over the top; its alpha is what lets the footage show through.
 */
function footageFilter(scenes, width, height, duration) {
  const clips = scenes
    .map((scene, index) => ({ scene, index }))
    .filter(({ scene }) => scene.media?.kind === 'video' && scene.media.src)
    .filter(({ scene }) => scene.in < duration);
  if (clips.length === 0) return { inputs: [], filter: null };

  const inputs = [];
  const parts = [`color=c=black:s=${width}x${height}:r=${fps}:d=${duration}[bed0]`];

  clips.forEach(({ scene }, order) => {
    const span = Math.max(0.04, Math.min(scene.out, duration) - scene.in);
    const from = scene.media.trim?.from ?? 0;
    inputs.push('-i', resolve(root, scene.media.src.replace(/^\//, '')));
    // The clip is shorter than the scene often enough to matter; looping the
    // input rather than the filter keeps a scene from freezing on a last frame.
    parts.push(
      `[${order + 1}:v]trim=start=${from.toFixed(3)}:duration=${span.toFixed(3)},` +
        `setpts=PTS-STARTPTS,scale=${width}:${height}:force_original_aspect_ratio=increase,` +
        `crop=${width}:${height},fps=${fps},format=rgba[clip${order}]`,
    );
    parts.push(
      `[bed${order}][clip${order}]overlay=enable='between(t,${scene.in.toFixed(3)},` +
        `${Math.min(scene.out, duration).toFixed(3)})':x=0:y=0:shortest=0[bed${order + 1}]`,
    );
  });

  parts.push(`[bed${clips.length}][0:v]overlay=x=0:y=0:shortest=1,noise=alls=5:allf=t+u,format=yuv420p[v]`);
  return { inputs, filter: parts.join(';') };
}

const composite = footageFilter(spec.scenes ?? [], outW, outH, duration);

// Grain and loudness live here, not in the engine: ffmpeg's noise filter is
// better than anything drawn on a canvas, and EBU R128 needs the final mix.
const video = 'noise=alls=5:allf=t+u,format=yuv420p';
const args = [
  '-y', '-hide_banner', '-loglevel', 'warning',
  '-framerate', String(fps),
  '-i', resolve(frameDir, '%06d.png'),
  ...composite.inputs,
  ...(hasAudio ? ['-i', voPath] : []),
  ...(composite.filter ? ['-filter_complex', composite.filter, '-map', '[v]'] : ['-vf', video]),
  ...(composite.filter && hasAudio ? ['-map', `${composite.inputs.length / 2 + 1}:a`] : []),
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
  '-movflags', '+faststart',
  ...(hasAudio
    ? ['-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-shortest']
    : ['-an']),
  outPath,
];

console.log(`encoding${hasAudio ? ' with voiceover' : ' (no audio track)'}…`);
await new Promise((ok, fail) => {
  const proc = spawn(FFMPEG, args, { stdio: ['ignore', 'inherit', 'inherit'] });
  proc.on('close', (code) => (code === 0 ? ok() : fail(new Error(`ffmpeg exited ${code}`))));
});

await rm(frameDir, { recursive: true, force: true });
console.log(`\n${outPath}`);
