/**
 * Hardware probes.
 *
 * Everything here measures. Where a measurement is impossible the field is
 * `undefined` and a warning is recorded — never a plausible default, because a
 * guessed core count silently produces a wrong render configuration.
 */

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readdirSync } from 'node:fs';
import { statfs } from 'node:fs/promises';
import { resolve } from 'node:path';
import os from 'node:os';

import type {
  CommandProbe,
  CpuInfo,
  DiskInfo,
  FfmpegInfo,
  MemoryInfo,
  PythonInfo,
} from './types';

const run = promisify(execFile);

/** Never through a shell: arguments stay an array so nothing can be injected. */
export async function exec(
  file: string,
  args: string[] = [],
  timeout = 10_000,
): Promise<{ ok: boolean; stdout: string; stderr: string }> {
  try {
    const { stdout, stderr } = await run(file, args, { timeout, maxBuffer: 8 << 20 });
    return { ok: true, stdout, stderr };
  } catch (error) {
    const err = error as { stdout?: string; stderr?: string; message?: string };
    return { ok: false, stdout: err.stdout ?? '', stderr: err.stderr ?? err.message ?? '' };
  }
}

async function sysctl(key: string): Promise<string | undefined> {
  const { ok, stdout } = await exec('sysctl', ['-n', key]);
  return ok ? stdout.trim() : undefined;
}

/**
 * Rosetta detection.
 *
 * `sysctl sysctl.proc_translated` returns 1 when this process is being
 * translated. It matters more than it looks: Remotion under Rosetta is reported
 * as up to 2x slower, and nothing in the output says so — the render is simply
 * half speed forever.
 */
export async function isEmulated(): Promise<boolean> {
  if (process.platform !== 'darwin') return false;
  return (await sysctl('sysctl.proc_translated')) === '1';
}

export async function detectCpu(): Promise<CpuInfo> {
  const cpus = os.cpus();
  const emulated = await isEmulated();
  const base: CpuInfo = {
    arch: process.arch,
    emulated,
    brand: cpus[0]?.model ?? 'unknown',
    cores: cpus.length,
  };

  if (process.platform !== 'darwin') return base;

  const [brand, perf, eff, physical] = await Promise.all([
    sysctl('machdep.cpu.brand_string'),
    sysctl('hw.perflevel0.logicalcpu'),
    sysctl('hw.perflevel1.logicalcpu'),
    sysctl('hw.physicalcpu'),
  ]);

  return {
    ...base,
    brand: brand ?? base.brand,
    cores: physical ? Number(physical) : base.cores,
    performanceCores: perf ? Number(perf) : undefined,
    efficiencyCores: eff ? Number(eff) : undefined,
    gpuCores: await detectGpuCores(),
  };
}

/**
 * GPU core count, from the display profile.
 *
 * `system_profiler` is slow (seconds) and its shape has changed between macOS
 * releases, so this is best-effort and returns undefined rather than guessing.
 */
async function detectGpuCores(): Promise<number | undefined> {
  const { ok, stdout } = await exec('system_profiler', ['-json', 'SPDisplaysDataType'], 20_000);
  if (!ok) return undefined;
  try {
    const parsed = JSON.parse(stdout) as {
      SPDisplaysDataType?: { sppci_cores?: string; spdisplays_vendor?: string }[];
    };
    const cores = parsed.SPDisplaysDataType?.[0]?.sppci_cores;
    return cores ? Number(cores) : undefined;
  } catch {
    return undefined;
  }
}

export async function detectMemory(): Promise<MemoryInfo> {
  const totalBytes = os.totalmem();
  const unified = process.platform === 'darwin' && process.arch === 'arm64';

  if (process.platform !== 'darwin') {
    return { totalBytes, freeBytes: os.freemem(), unified };
  }

  // os.freemem() on macOS reports only genuinely free pages and reads as
  // alarmingly low; inactive and speculative pages are reclaimable. vm_stat
  // gives the honest number.
  const { ok, stdout } = await exec('vm_stat');
  if (!ok) return { totalBytes, freeBytes: os.freemem(), unified };

  const pageSize = Number(/page size of (\d+) bytes/.exec(stdout)?.[1] ?? 4096);
  const pages = (name: string) =>
    Number(new RegExp(`${name}:\\s+(\\d+)`).exec(stdout)?.[1] ?? 0);

  const reclaimable = pages('Pages free') + pages('Pages inactive') + pages('Pages speculative');
  return { totalBytes, freeBytes: reclaimable * pageSize, unified };
}

export async function detectDisk(path = process.cwd()): Promise<DiskInfo> {
  try {
    const stats = await statfs(path);
    return {
      path,
      totalBytes: stats.blocks * stats.bsize,
      freeBytes: stats.bavail * stats.bsize,
    };
  } catch {
    return { path, totalBytes: 0, freeBytes: 0 };
  }
}

export async function probeCommand(
  candidates: string[],
  args: string[] = ['--version'],
): Promise<CommandProbe> {
  for (const candidate of candidates) {
    const { ok, stdout, stderr } = await exec(candidate, args);
    if (ok) {
      const text = (stdout || stderr).trim();
      return {
        found: true,
        path: candidate,
        version: text.split('\n')[0]?.slice(0, 120),
      };
    }
  }
  return { found: false, error: `none of ${candidates.join(', ')} responded` };
}

function ffmpegCandidates(): string[] {
  const candidates = [
    process.env.FFMPEG_PATH,
    '/opt/homebrew/bin/ffmpeg',
    '/usr/local/bin/ffmpeg',
    '/usr/bin/ffmpeg',
    'ffmpeg',
  ];

  // `pip install imageio-ffmpeg` ships a static build that always carries
  // libx264. Worth finding: on a machine without Homebrew it is often the only
  // complete ffmpeg present.
  for (const root of [
    '/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries',
    '/opt/homebrew/lib/python3.11/site-packages/imageio_ffmpeg/binaries',
  ]) {
    try {
      for (const name of readdirSync(root)) candidates.push(resolve(root, name));
    } catch {
      // absent is the common case
    }
  }
  return candidates.filter((value): value is string => Boolean(value));
}

export async function detectFfmpeg(): Promise<FfmpegInfo> {
  const probe = await probeCommand(ffmpegCandidates(), ['-version']);
  if (!probe.found || !probe.path) {
    return {
      ...probe,
      encoders: [],
      hasX264: false,
      hasVideoToolbox: false,
      videoToolboxWorks: null,
    };
  }

  const { stdout } = await exec(probe.path, ['-hide_banner', '-encoders'], 20_000);
  const encoders = stdout
    .split('\n')
    .map((line) => /^\s*[A-Z.]{6}\s+(\S+)/.exec(line)?.[1])
    .filter((name): name is string => Boolean(name));

  const hasVideoToolbox = encoders.includes('h264_videotoolbox');
  return {
    ...probe,
    encoders,
    hasX264: encoders.includes('libx264'),
    hasVideoToolbox,
    // Listed is not the same as usable: VideoToolbox is compiled in on Macs
    // that cannot actually run it, and the failure only appears at encode time.
    videoToolboxWorks: hasVideoToolbox ? await trialVideoToolbox(probe.path) : null,
  };
}

async function trialVideoToolbox(ffmpeg: string): Promise<boolean> {
  const { ok } = await exec(
    ffmpeg,
    [
      '-hide_banner', '-loglevel', 'error', '-y',
      '-f', 'lavfi', '-i', 'color=c=black:s=320x240:d=0.2:r=10',
      '-c:v', 'h264_videotoolbox', '-f', 'null', '-',
    ],
    30_000,
  );
  return ok;
}

/**
 * The interpreter the content pipeline runs on.
 *
 * Version matters more than presence. `kokoro-onnx` and `whisperx` both pin
 * `python <3.14`, so a machine on 3.14 installs neither — and finds out at
 * `pip install`, several steps into a setup that looked fine.
 */
export const PYTHON_MIN = { major: 3, minor: 11 };
export const PYTHON_MAX_EXCLUSIVE = { major: 3, minor: 14 };

export async function detectPython(): Promise<PythonInfo> {
  // Prefer a version the ML stack accepts, if one is installed alongside.
  const probe = await probeCommand([
    'python3.13', 'python3.12', 'python3.11', 'python3', 'python',
  ]);
  if (!probe.found) return { ...probe, usableForPipeline: false };

  const match = /Python (\d+)\.(\d+)/.exec(probe.version ?? '');
  if (!match) return { ...probe, usableForPipeline: false };

  const major = Number(match[1]);
  const minor = Number(match[2]);
  const atLeastMin =
    major > PYTHON_MIN.major || (major === PYTHON_MIN.major && minor >= PYTHON_MIN.minor);
  const belowMax =
    major < PYTHON_MAX_EXCLUSIVE.major ||
    (major === PYTHON_MAX_EXCLUSIVE.major && minor < PYTHON_MAX_EXCLUSIVE.minor);

  return { ...probe, major, minor, usableForPipeline: atLeastMin && belowMax };
}

const CHROMIUM_CANDIDATES = [
  process.env.CHROMIUM_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/opt/pw-browsers/chromium',
].filter((value): value is string => Boolean(value));

export async function detectChromium(): Promise<CommandProbe> {
  return probeCommand(CHROMIUM_CANDIDATES);
}

export async function osVersion(): Promise<string> {
  if (process.platform === 'darwin') {
    const { ok, stdout } = await exec('sw_vers', ['-productVersion']);
    if (ok) return `macOS ${stdout.trim()}`;
  }
  return `${os.type()} ${os.release()}`;
}
