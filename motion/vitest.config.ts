import { defineConfig } from 'vitest/config';

// Deliberately separate from vite.config.ts: the compiler tests are pure and
// must not need the Motion Canvas build pipeline to run.
export default defineConfig({
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
});
