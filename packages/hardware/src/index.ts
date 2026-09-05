import {
  detectChromium,
  detectCpu,
  detectDisk,
  detectFfmpeg,
  detectMemory,
  osVersion,
  probeCommand,
} from './probe';
import type { HardwareReport } from './types';

export * from './types';
export { planResources, canRender } from './budget';
export { exec } from './probe';

export async function detect(diskPath?: string): Promise<HardwareReport> {
  const [os_, cpu, memory, disk, python, chromium, ffmpeg] = await Promise.all([
    osVersion(),
    detectCpu(),
    detectMemory(),
    detectDisk(diskPath),
    probeCommand(['python3', 'python']),
    detectChromium(),
    detectFfmpeg(),
  ]);

  const warnings: string[] = [];
  if (cpu.emulated) {
    warnings.push(
      'Node is running under Rosetta. Remotion renders up to 2x slower and nothing ' +
        'else will tell you. Install an arm64 build of Node.',
    );
  }
  if (!ffmpeg.found) warnings.push('ffmpeg not found — rendering is impossible');
  else if (!ffmpeg.hasX264) {
    warnings.push(
      'ffmpeg has no libx264. Delivery encoding will fall back to hardware, which ' +
        'costs quality per bit. brew install ffmpeg',
    );
  }
  if (ffmpeg.hasVideoToolbox && ffmpeg.videoToolboxWorks === false) {
    warnings.push('h264_videotoolbox is compiled in but failed a trial encode');
  }
  if (!chromium.found) {
    warnings.push('no Chromium found — Remotion will download its own on first render');
  }
  if (!python.found) warnings.push('python3 not found — the content pipeline cannot run');

  return {
    platform: process.platform,
    osVersion: os_,
    appleSilicon: process.platform === 'darwin' && process.arch === 'arm64',
    cpu,
    memory,
    disk,
    node: { found: true, path: process.execPath, version: process.version },
    python,
    chromium,
    ffmpeg,
    warnings,
    measuredAt: new Date().toISOString(),
  };
}
