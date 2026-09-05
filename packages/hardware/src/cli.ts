#!/usr/bin/env node
/**
 * `npm run hardware` — measure this machine and print the render budget.
 *
 * Run it on the target Mac before trusting any default in the plan.
 */

import { canRender, detect, planResources } from './index';

const GB = 1024 ** 3;
const gb = (bytes: number) => `${(bytes / GB).toFixed(1)} GB`;

const json = process.argv.includes('--json');
const report = await detect();
const budget = planResources(report);
const gate = canRender(report, budget);

if (json) {
  console.log(JSON.stringify({ report, budget, gate }, null, 2));
  process.exit(gate.ok ? 0 : 1);
}

const { cpu, memory, disk, ffmpeg } = report;
const cores = [
  `${cpu.cores} cores`,
  cpu.performanceCores ? `${cpu.performanceCores}P/${cpu.efficiencyCores}E` : null,
  cpu.gpuCores ? `${cpu.gpuCores}-core GPU` : null,
].filter(Boolean).join(' · ');

console.log(`\n  MACHINE`);
console.log(`  ${cpu.brand}`);
console.log(`  ${cores}${cpu.emulated ? '  ⚠️  UNDER ROSETTA' : ''}`);
console.log(`  ${gb(memory.totalBytes)} ${memory.unified ? 'unified' : 'RAM'}, ${gb(memory.freeBytes)} free`);
console.log(`  ${gb(disk.freeBytes)} free of ${gb(disk.totalBytes)}`);
console.log(`  ${report.osVersion} · node ${report.node.version} · ${report.python.version ?? 'no python'}`);

console.log(`\n  FFMPEG`);
if (ffmpeg.found) {
  console.log(`  ${ffmpeg.path}`);
  console.log(`  ${ffmpeg.version}`);
  console.log(`  libx264 ${ffmpeg.hasX264 ? '✓' : '✗'}   videotoolbox ${
    ffmpeg.videoToolboxWorks === true ? '✓ verified'
      : ffmpeg.hasVideoToolbox ? '✗ present but failed trial encode' : '✗'
  }`);
} else {
  console.log(`  not found`);
}

console.log(`\n  RENDER BUDGET`);
console.log(`  concurrent renders    ${budget.concurrentRenders}`);
console.log(`  render concurrency    ${budget.renderConcurrency}`);
console.log(`  ffmpeg processes      ${budget.ffmpegProcesses}`);
console.log(`  tts processes         ${budget.ttsProcesses}`);
console.log(`  asset downloads       ${budget.assetDownloads}`);
console.log(`  preview encoder       ${budget.previewEncoder}`);
console.log(`  delivery encoder      ${budget.deliveryEncoder}`);
for (const reason of budget.reasons) console.log(`    · ${reason}`);

if (report.warnings.length) {
  console.log(`\n  WARNINGS`);
  for (const warning of report.warnings) console.log(`  ⚠️  ${warning}`);
}

console.log(`\n  ${gate.ok ? '✓ ready to render' : '✗ cannot render:'}`);
for (const blocker of gate.blockers) console.log(`    ${blocker}`);
console.log();
