import type { Plugin } from 'vite';

/** `code` with the `desc` option of every `msg()` call taken out. */
export function stripMsgDesc(code: string, fileName?: string): string;
/** The Vite plugin: takes the `desc` option out of the `msg()` calls of the packages' sources. */
export function stripMsgDescs(): Plugin;
