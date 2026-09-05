import { describe, expect, it } from 'vitest';

import { canRender, planResources } from '../src/budget';
import type { HardwareReport } from '../src/types';

const GB = 1024 ** 3;

function report(overrides: Partial<HardwareReport> = {}): HardwareReport {
  return {
    platform: 'darwin',
    osVersion: 'macOS 26.6.2',
    appleSilicon: true,
    cpu: {
      arch: 'arm64',
      emulated: false,
      brand: 'Apple M5',
      cores: 10,
      performanceCores: 4,
      efficiencyCores: 6,
      gpuCores: 8,
    },
    memory: { totalBytes: 16 * GB, freeBytes: 8 * GB, unified: true },
    disk: { path: '/', totalBytes: 460 * GB, freeBytes: 286 * GB },
    node: { found: true, version: 'v22.0.0' },
    python: { found: true, version: 'Python 3.11' },
    chromium: { found: true },
    ffmpeg: {
      found: true,
      encoders: ['libx264', 'h264_videotoolbox'],
      hasX264: true,
      hasVideoToolbox: true,
      videoToolboxWorks: true,
    },
    warnings: [],
    measuredAt: '2026-09-05T00:00:00Z',
    ...overrides,
  };
}

describe('planResources', () => {
  it('bounds concurrency by performance cores, not total cores', () => {
    // 10 cores but 4 performance: efficiency cores make a render slower when
    // frames are handed out evenly across a heterogeneous CPU.
    expect(planResources(report()).renderConcurrency).toBe(4);
  });

  it('bounds concurrency by memory when memory is the tighter constraint', () => {
    const small = report({
      memory: { totalBytes: 8 * GB, freeBytes: 4 * GB, unified: true },
    });
    expect(planResources(small).renderConcurrency).toBeLessThan(4);
  });

  it('never drops below one worker', () => {
    const tiny = report({ memory: { totalBytes: 4 * GB, freeBytes: 1 * GB, unified: true } });
    expect(planResources(tiny).renderConcurrency).toBeGreaterThanOrEqual(1);
  });

  it('halves concurrency under Rosetta and says why', () => {
    const rosetta = report({ cpu: { ...report().cpu, emulated: true } });
    const plan = planResources(rosetta);
    expect(plan.renderConcurrency).toBe(2);
    expect(plan.reasons.join(' ')).toMatch(/Rosetta/);
  });

  it('keeps whole-video renders at one', () => {
    // A second simultaneous render doubles peak memory for sub-linear gain, and
    // on a fanless chassis mostly buys throttling.
    expect(planResources(report()).concurrentRenders).toBe(1);
  });

  it('explains every derived number', () => {
    expect(planResources(report()).reasons.length).toBeGreaterThan(0);
  });

  describe('encoder selection', () => {
    it('prefers software for delivery and hardware for preview', () => {
      const plan = planResources(report());
      expect(plan.deliveryEncoder).toBe('libx264');
      expect(plan.previewEncoder).toBe('h264_videotoolbox');
    });

    it('does not recommend videotoolbox that failed its trial encode', () => {
      const plan = planResources(
        report({
          ffmpeg: { ...report().ffmpeg, videoToolboxWorks: false },
        }),
      );
      expect(plan.previewEncoder).toBe('libx264');
      expect(plan.reasons.join(' ')).toMatch(/failed a trial encode/);
    });

    it('reports no encoder at all when ffmpeg is missing', () => {
      // Naming an encoder here would read as a working configuration.
      const plan = planResources(
        report({
          ffmpeg: {
            found: false,
            encoders: [],
            hasX264: false,
            hasVideoToolbox: false,
            videoToolboxWorks: null,
          },
        }),
      );
      expect(plan.previewEncoder).toBe('unavailable');
      expect(plan.deliveryEncoder).toBe('unavailable');
    });

    it('falls back to hardware when there is no libx264', () => {
      const plan = planResources(
        report({
          ffmpeg: {
            found: true,
            encoders: ['h264_videotoolbox'],
            hasX264: false,
            hasVideoToolbox: true,
            videoToolboxWorks: true,
          },
        }),
      );
      expect(plan.deliveryEncoder).toBe('h264_videotoolbox');
    });
  });
});

describe('canRender', () => {
  it('passes on a healthy machine', () => {
    const machine = report();
    expect(canRender(machine, planResources(machine)).ok).toBe(true);
  });

  it('blocks with no ffmpeg', () => {
    const machine = report({
      ffmpeg: { found: false, encoders: [], hasX264: false, hasVideoToolbox: false, videoToolboxWorks: null },
    });
    const gate = canRender(machine, planResources(machine));
    expect(gate.ok).toBe(false);
    expect(gate.blockers.join(' ')).toMatch(/ffmpeg/);
  });

  it('blocks rather than swapping the machine to a halt', () => {
    const machine = report({
      memory: { totalBytes: 16 * GB, freeBytes: 1 * GB, unified: true },
    });
    const gate = canRender(machine, planResources(machine));
    expect(gate.ok).toBe(false);
    expect(gate.blockers.join(' ')).toMatch(/memory free/);
  });

  it('blocks when the disk cannot hold a render', () => {
    const machine = report({ disk: { path: '/', totalBytes: 460 * GB, freeBytes: 2 * GB } });
    const gate = canRender(machine, planResources(machine));
    expect(gate.ok).toBe(false);
    expect(gate.blockers.join(' ')).toMatch(/disk free/);
  });
});
