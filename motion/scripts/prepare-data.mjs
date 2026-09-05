/**
 * Copy a spec and its brand tokens into data/ for the renderer to import.
 *
 *   node scripts/prepare-data.mjs ../output/dehydration/scene-spec.json
 *
 * Vite imports these at build time, so they are staged as files rather than
 * read at runtime. `$schema` is stripped from the tokens for the same reason
 * the Python side strips it before hashing: it is an editor affordance, not
 * part of the design.
 */

import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { basename } from 'node:path';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const specPath = process.argv[2];
if (!specPath) {
  console.error('usage: node scripts/prepare-data.mjs <path-to-scene-spec.json> [brand.json]');
  process.exit(2);
}

const spec = JSON.parse(await readFile(resolve(specPath), 'utf8'));
const brandPath = process.argv[3] ?? resolve(root, `../brand/${spec.brand.id}.json`);
const tokens = JSON.parse(await readFile(brandPath, 'utf8'));
delete tokens.$schema;

if (tokens.id !== spec.brand.id) {
  console.error(`spec expects brand "${spec.brand.id}" but ${brandPath} is "${tokens.id}"`);
  process.exit(1);
}

await mkdir(resolve(root, 'data'), { recursive: true });

// Media lives in the pipeline cache as absolute paths; a browser can only load
// what Vite serves, so stage the files under data/ and rewrite the references.
const mediaDir = resolve(root, 'data/media');
await mkdir(mediaDir, { recursive: true });
let staged = 0;
for (const scene of spec.scenes) {
  if (!scene.media?.src) continue;
  const name = basename(scene.media.src);
  await copyFile(resolve(dirname(resolve(specPath)), '..', '..', scene.media.src).replace(/output\/[^/]+\/\.\.\/\.\.\//, ''), resolve(mediaDir, name)).catch(async () => {
    await copyFile(scene.media.src, resolve(mediaDir, name));
  });
  scene.media.src = `/data/media/${name}`;
  staged += 1;
}
await writeFile(resolve(root, 'data/spec.json'), JSON.stringify(spec, null, 2));
await writeFile(resolve(root, 'data/brand.json'), JSON.stringify(tokens, null, 2));
console.log(
  `staged ${spec.meta.slug} (${spec.scenes.length} scenes, ${spec.meta.duration_s}s, ` +
    `${staged} image${staged === 1 ? '' : 's'}) with brand ${tokens.id}`,
);
