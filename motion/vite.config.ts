import { defineConfig } from 'vite';
import mc from '@motion-canvas/vite-plugin';

// The plugin ships as CommonJS with no `exports` map, so under ESM the default
// export arrives wrapped. Unwrap rather than switching the project to CJS.
const motionCanvas = ((mc as unknown as { default?: typeof mc }).default ?? mc) as typeof mc;

export default defineConfig({
  plugins: [motionCanvas()],
});
