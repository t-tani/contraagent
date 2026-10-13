import { describe, expect, it } from 'vitest';
import { stripMsgDesc } from './strip-msg-desc.mjs';

describe('stripMsgDesc', () => {
  it('drops the options object when desc is its only option', () => {
    expect(stripMsgDesc("msg('up', { desc: 'A host whose reports keep arriving' })")).toBe("msg('up')");
    expect(stripMsgDesc('msg(str`${n} runs`, {\n  desc: `runs`,\n})')).toBe('msg(str`${n} runs`)');
  });

  it('keeps the other options', () => {
    expect(stripMsgDesc("msg('Status', { id: 'status', desc: 'The status of a task' })")).toBe("msg('Status', { id: 'status' })");
    expect(stripMsgDesc("msg('Runs', { desc: 'A column', id: 'col-runs' })")).toBe("msg('Runs', { id: 'col-runs' })");
  });

  it('leaves other calls and msg calls without desc as they are', () => {
    const code = "msg('a'); msg('b', { id: 'b' }); other('c', { desc: 'd' }); const o = { desc: 'e' };";
    expect(stripMsgDesc(code)).toBe(code);
  });

  it('strips desc in a msg call nested in a template', () => {
    expect(stripMsgDesc("html`<b>${msg('x', { desc: 'y' })}</b>`")).toBe("html`<b>${msg('x')}</b>`");
  });
});
