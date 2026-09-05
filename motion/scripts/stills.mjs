/**
 * Render still frames from the current spec.
 *
 * A cheap way to see whether the design is right before committing to a full
 * video render: type, colour, layout and composition all show up in a still.
 *
 *   node scripts/stills.mjs [--at 0.6,3.2,9.5] [--scale 0.25] [--out ../output/<slug>/stills]
 */

import { createServer } from 'vite';
import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index === -1 ? fallback : process.argv[index + 1];
}

const spec = JSON.parse(readFileSync(resolve(root, 'data/spec.json'), 'utf8'));
const [width, height] = spec.meta.resolution;
const scale = Number(arg('scale', '0.25'));
const outDir = resolve(root, arg('out', `../output/${spec.meta.slug}/stills`));

// Default to a moment inside each scene where everything has landed but
// nothing has begun leaving.
const times = arg('at')
  ? arg('at').split(',').map(Number)
  : spec.scenes.map((scene) => +(scene.in + (scene.out - scene.in) * 0.55).toFixed(2));

const server = await createServer({ root, configFile: resolve(root, 'vite.config.ts'), logLevel: 'warn' });
await server.listen();
const port = server.config.server.port ?? server.httpServer.address().port;

// This environment ships a pinned Chromium that will not match whatever
// build the installed Playwright expects; point at it rather than downloading
// a second copy. CHROMIUM_PATH overrides for other machines.
const executablePath = process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium';
const browser = await chromium.launch({
  executablePath: existsSync(executablePath) ? executablePath : undefined,
  args: ['--no-sandbox', '--use-gl=swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
page.on('pageerror', (error) => console.error('page error:', error.message));

const url = `http://localhost:${port}/headless.html?w=${width}&h=${height}&scale=${scale}&fps=${spec.meta.fps}`;
await page.goto(url, { waitUntil: 'load' });
await page.waitForFunction(() => typeof window.videobotRender === 'function', null, { timeout: 30_000 });

// Canvas text falls back silently. Say so loudly instead: a fallback font is
// the difference between the house style and Helvetica.
const family = spec.brand.id ? JSON.parse(readFileSync(resolve(root, 'data/brand.json'), 'utf8')).type.display.family : '';
const fontOk = await page.evaluate((f) => document.fonts.check(`700 100px "${f}"`), family);
console.log(fontOk ? `font: ${family} loaded` : `WARNING: "${family}" did not load — frames will be in a fallback face`);

await mkdir(outDir, { recursive: true });
for (const [index, seconds] of times.entries()) {
  const dataUrl = await page.evaluate((t) => window.videobotRender(t), seconds);
  const name = `${String(index + 1).padStart(2, '0')}-${seconds.toFixed(2)}s.png`;
  await writeFile(resolve(outDir, name), Buffer.from(dataUrl.split(',')[1], 'base64'));
  console.log(`  ${name}`);
}

console.log(`\n${times.length} still(s) → ${outDir}`);
await browser.close();
await server.close();
