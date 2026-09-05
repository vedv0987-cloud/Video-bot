import { describe, expect, it } from 'vitest';

import { detectPython, PYTHON_MAX_EXCLUSIVE, PYTHON_MIN } from '../src/probe';

describe('detectPython', () => {
  it('finds an interpreter and reports its version', async () => {
    const python = await detectPython();
    expect(python.found).toBe(true);
    expect(python.major).toBe(3);
    expect(typeof python.minor).toBe('number');
  });

  it('agrees with its own supported range', async () => {
    const python = await detectPython();
    const inRange =
      python.minor !== undefined &&
      python.minor >= PYTHON_MIN.minor &&
      python.minor < PYTHON_MAX_EXCLUSIVE.minor;
    expect(python.usableForPipeline).toBe(inRange);
  });

  it('excludes 3.14, which kokoro-onnx and whisperx both refuse', () => {
    // Documented as a range rather than tested against a live 3.14: the pins
    // are upstream facts, and this is the assertion that encodes them.
    expect(PYTHON_MAX_EXCLUSIVE).toEqual({ major: 3, minor: 14 });
  });
});
