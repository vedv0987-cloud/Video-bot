/**
 * Turning a hardware report into a resource budget.
 *
 * Every number here is a *starting point with a stated reason*, not a tuned
 * value. The benchmark harness replaces `renderConcurrency` with a measurement;
 * until it has run, the log says the value was derived rather than measured.
 *
 * The governing constraint on the target machine is 16 GB of unified memory
 * shared with the GPU, and a passively cooled chassis that throttles under
 * sustained load. More parallelism is not more throughput here.
 */

import type { HardwareReport, ResourceBudget } from './types';

const GB = 1024 ** 3;

/** Chromium page + decoded frames for one Remotion worker, observed order of magnitude. */
const MEMORY_PER_RENDER_WORKER = 1.1 * GB;
const OS_HEADROOM = 5 * GB;
/** Left unclaimed so a render does not consume the last of free memory. */
const RENDER_SAFETY_MARGIN = 1.5 * GB;

const gbLabel = (bytes: number) => `${(bytes / GB).toFixed(1)} GB`;

export function planResources(report: HardwareReport): ResourceBudget {
  const reasons: string[] = [];
  const { cores, performanceCores, emulated } = report.cpu;
  const totalGb = report.memory.totalBytes / GB;

  // Two memory ceilings, and they answer different questions.
  //
  // Capacity is what the machine could sustain with nothing else running.
  // Headroom is what fits *right now*, given whatever is already open. Sizing
  // from capacity alone is how a budget recommends four workers on a machine
  // with four gigabytes free and then swaps it to a halt.
  const capacityCeiling = Math.max(
    1,
    Math.floor((report.memory.totalBytes - OS_HEADROOM) / MEMORY_PER_RENDER_WORKER),
  );
  const headroomCeiling = Math.max(
    1,
    Math.floor((report.memory.freeBytes - RENDER_SAFETY_MARGIN) / MEMORY_PER_RENDER_WORKER),
  );

  // Performance cores do the work; efficiency cores make a render slower when
  // frames are distributed evenly across a heterogeneous CPU.
  const coreCeiling = Math.max(1, performanceCores ?? Math.ceil(cores / 2));

  const capacityConcurrency = Math.max(1, Math.min(capacityCeiling, coreCeiling));
  let renderConcurrency = Math.max(1, Math.min(headroomCeiling, capacityConcurrency));

  reasons.push(
    `render concurrency ${renderConcurrency}: min(free memory fits ${headroomCeiling}, ` +
      `total memory supports ${capacityCeiling}, performance cores ${coreCeiling}) — ` +
      `provisional until benchmarked`,
  );
  if (renderConcurrency < capacityConcurrency) {
    reasons.push(
      `this machine could run ${capacityConcurrency} workers with memory free; ` +
        `${gbLabel(report.memory.totalBytes - report.memory.freeBytes)} is currently in ` +
        `use, so closing applications before a render is worth more than any setting here`,
    );
  }

  if (emulated) {
    renderConcurrency = Math.max(1, Math.floor(renderConcurrency / 2));
    reasons.push(
      'halved: Node is running under Rosetta translation, which is reported to cost ' +
        'up to 2x render speed. Install an arm64 Node before benchmarking',
    );
  }

  if (totalGb <= 8) {
    reasons.push('8 GB or less: previews only, expect swapping on 1080p renders');
  }

  const videoToolbox = report.ffmpeg.videoToolboxWorks === true;
  if (!videoToolbox && report.ffmpeg.hasVideoToolbox) {
    reasons.push('h264_videotoolbox is present but failed a trial encode — not used');
  }

  return {
    // A second simultaneous render doubles peak memory for sub-linear gain, and
    // on a fanless chassis it mostly buys thermal throttling.
    concurrentRenders: 1,
    renderConcurrency,
    capacityConcurrency,
    ffmpegProcesses: 2,
    // Model load dominates TTS cost; parallel loads thrash a shared memory pool.
    ttsProcesses: 1,
    assetDownloads: 4,
    imageProcessing: Math.max(2, Math.min(4, Math.floor(cores / 3))),
    minFreeMemoryBytes: 3 * GB,
    minFreeDiskBytes: 10 * GB,
    // With no usable ffmpeg there is no encoder to recommend. Naming one anyway
    // would read as a working configuration.
    previewEncoder: pickEncoder(report, videoToolbox ? 'h264_videotoolbox' : 'libx264'),
    // Software encoding wins on quality per bit, and delivery renders are not
    // interactive. Benchmark may overturn this; it is a hypothesis.
    deliveryEncoder: pickEncoder(report, report.ffmpeg.hasX264 ? 'libx264' : 'h264_videotoolbox'),
    reasons,
  };
}

function pickEncoder(report: HardwareReport, preferred: string): string {
  if (!report.ffmpeg.found) return 'unavailable';
  if (preferred === 'libx264' && report.ffmpeg.hasX264) return preferred;
  if (preferred === 'h264_videotoolbox' && report.ffmpeg.videoToolboxWorks === true) {
    return preferred;
  }
  if (report.ffmpeg.hasX264) return 'libx264';
  if (report.ffmpeg.videoToolboxWorks === true) return 'h264_videotoolbox';
  return 'unavailable';
}

/** Whether a render may start right now. Fail fast beats swapping to a halt. */
export function canRender(
  report: HardwareReport,
  budget: ResourceBudget,
): { ok: boolean; blockers: string[] } {
  const blockers: string[] = [];
  const gb = (bytes: number) => (bytes / GB).toFixed(1);

  if (!report.ffmpeg.found) blockers.push('ffmpeg not found');
  else if (!report.ffmpeg.hasX264 && !report.ffmpeg.hasVideoToolbox) {
    blockers.push('ffmpeg has neither libx264 nor h264_videotoolbox');
  }
  if (report.memory.freeBytes < budget.minFreeMemoryBytes) {
    blockers.push(
      `only ${gb(report.memory.freeBytes)} GB memory free, need ` +
        `${gb(budget.minFreeMemoryBytes)} GB`,
    );
  }
  if (report.disk.freeBytes < budget.minFreeDiskBytes) {
    blockers.push(
      `only ${gb(report.disk.freeBytes)} GB disk free, need ${gb(budget.minFreeDiskBytes)} GB`,
    );
  }
  return { ok: blockers.length === 0, blockers };
}
