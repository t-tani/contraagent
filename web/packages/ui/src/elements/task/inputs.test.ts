import type { ContractSpec, UpstreamTask } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { inputView } from './inputs.js';

const spec = (path: string, io: 'input' | 'output', extra: Partial<ContractSpec> = {}): ContractSpec => ({
  io, path, schema_name: 'S', file: { exists: true }, fields: [], ...extra,
});
const task = (key: string, outputs: ContractSpec[]): UpstreamTask => ({ key, kind: key.split('-')[0] ?? key, unit: 'u', executor: 'agent', outputs });

describe('inputView', () => {
  it('lists every file the task reads with the earlier task that writes it, or none for a file from before the run', () => {
    const prepare = task('prepare-u', [spec('out/prepare/u.json', 'output', { status: 'valid' })]);
    const { files } = inputView({ inputs: [spec('out/prepare/u.json', 'input'), spec('data/seed.json', 'input')], upstream: [prepare] });
    expect(files.map((f) => [f.spec.path, f.from?.key ?? null, f.out?.status ?? null])).toEqual([
      ['out/prepare/u.json', 'prepare-u', 'valid'],
      ['data/seed.json', null, null],
    ]);
  });

  it('keeps under each earlier task only the output files the task does not read, and counts the others', () => {
    const summarize = task('summarize-u', [spec('out/summarize/u.json', 'output', { status: 'valid' }), spec('out/summarize/u.md', 'output', { status: 'valid' })]);
    // It waits for check-u but reads none of its files.
    const check = task('check-u', [spec('out/check/u.json', 'output', { status: 'valid' })]);
    const { earlier } = inputView({ inputs: [spec('out/summarize/u.json', 'input')], upstream: [summarize, check] });
    expect(earlier.map((e) => [e.task.key, e.read, e.rest.map((o) => o.path)])).toEqual([
      ['summarize-u', 1, ['out/summarize/u.md']],
      ['check-u', 0, ['out/check/u.json']],
    ]);
  });

  it('puts first an earlier task whose output is missing (a task that did not start for it)', () => {
    const ok = task('a-u', [spec('out/a/u.json', 'output', { status: 'valid' })]);
    const failed = task('prepare-u', [spec('out/prepare/u.json', 'output', { status: 'failed', file: { exists: false } })]);
    const v = inputView({ inputs: [spec('out/prepare/u.json', 'input', { file: { exists: false }, required: true })], upstream: [ok, failed] });
    expect(v.earlier.map((e) => e.task.key)).toEqual(['prepare-u', 'a-u']);
    expect(v.files[0]?.out?.status).toBe('failed');
  });
});
