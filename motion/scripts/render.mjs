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

// Grain and loudness live here, not in the engine: ffmpeg's noise filter is
// better than anything drawn on a canvas, and EBU R128 needs the final mix.
const video = 'noise=alls=5:allf=t+u,format=yuv420p';
const args = [
  '-y', '-hide_banner', '-loglevel', 'warning',
  '-framerate', String(fps),
  '-i', resolve(frameDir, '%06d.png'),
  ...(hasAudio ? ['-i', voPath] : []),
  '-vf', video,
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
