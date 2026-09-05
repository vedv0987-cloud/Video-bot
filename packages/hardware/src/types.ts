/** What a hardware probe reports. Every field is measured or explicitly unknown. */

export interface CommandProbe {
  found: boolean;
  path?: string;
  version?: string;
  error?: string;
}

export interface CpuInfo {
  arch: string;
  /** True when Node is running under Rosetta translation. */
  emulated: boolean;
  brand: string;
  cores: number;
  performanceCores?: number;
  efficiencyCores?: number;
  gpuCores?: number;
}

export interface MemoryInfo {
  totalBytes: number;
  freeBytes: number;
  /** Apple Silicon shares one pool between CPU and GPU. */
  unified: boolean;
}

export interface DiskInfo {
  path: string;
  totalBytes: number;
  freeBytes: number;
}

export interface FfmpegInfo extends CommandProbe {
  encoders: string[];
  hasX264: boolean;
  /** Apple hardware H.264. Present in the build *and* usable — we trial-encode. */
  hasVideoToolbox: boolean;
  videoToolboxWorks: boolean | null;
}

export interface HardwareReport {
  platform: NodeJS.Platform;
  osVersion: string;
  appleSilicon: boolean;
  cpu: CpuInfo;
  memory: MemoryInfo;
  disk: DiskInfo;
  node: CommandProbe;
  python: CommandProbe;
  chromium: CommandProbe;
  ffmpeg: FfmpegInfo;
  warnings: string[];
  measuredAt: string;
}

export interface ResourceBudget {
  /** Whole video renders at once. Rarely more than one is a win. */
  concurrentRenders: number;
  /** Workers inside a single Remotion render. Benchmark before trusting. */
  renderConcurrency: number;
  ffmpegProcesses: number;
  ttsProcesses: number;
  assetDownloads: number;
  imageProcessing: number;
  /** Refuse to start a render below these. */
  minFreeMemoryBytes: number;
  minFreeDiskBytes: number;
  /** Which encoder to reach for, per purpose. */
  previewEncoder: string;
  deliveryEncoder: string;
  reasons: string[];
}
