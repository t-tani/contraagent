// What the reader did on a page that the URL does not say: how far a list is
// scrolled, which cards are open. Kept in the current history entry, so Back,
// Forward and a reload return to it, and a new entry starts clean.
//
// Stored under one key of `history.state`, merged with whatever else a host
// page keeps there (a router's own state survives).

const NS = 'contraagent';
const WRITE_MS = 200;

type Bag = Record<string, unknown> & { entry?: string };

let pending: Bag | null = null;
/** The entry `pending` belongs to: after Back/Forward it must not land on another one. */
let pendingEntry = '';
let timer: ReturnType<typeof setTimeout> | null = null;

function state(): Record<string, unknown> {
  const s: unknown = globalThis.history?.state;
  return s && typeof s === 'object' ? (s as Record<string, unknown>) : {};
}

function bag(): Bag {
  const mine = state()[NS];
  return mine && typeof mine === 'object' ? (mine as Bag) : {};
}

/** The current entry's id, given one on first use. */
function entry(): string {
  const id = bag().entry;
  if (id) return id;
  const fresh = Math.random().toString(36).slice(2);
  history.replaceState({ ...state(), [NS]: { ...bag(), entry: fresh } }, '');
  return fresh;
}

function write(): void {
  if (timer) clearTimeout(timer);
  timer = null;
  const p = pending;
  pending = null;
  if (!p || !globalThis.history || bag().entry !== pendingEntry) return;
  history.replaceState({ ...state(), [NS]: { ...bag(), ...p } }, '');
}

/** The value remembered under `id` in the current history entry. */
export function recall<T>(id: string): T | undefined {
  if (!globalThis.history) return undefined;
  const fromPending = pending && pendingEntry === bag().entry && id in pending;
  return (fromPending ? pending![id] : bag()[id]) as T | undefined;
}

/** Remember `value` under `id` in the current history entry (written shortly after, batched). */
export function remember(id: string, value: unknown): void {
  if (!globalThis.history) return;
  const e = entry();
  if (pending && pendingEntry !== e) pending = null;
  pendingEntry = e;
  (pending ??= {})[id] = value;
  timer ??= setTimeout(write, WRITE_MS);
}

/** Write what is pending now: before the page pushes a new entry, so it lands on the old one. */
export function flushMemory(): void {
  write();
}

globalThis.addEventListener?.('pagehide', flushMemory);

/** A set of ids remembered under `id` (open cards, folds). */
export class RememberedSet {
  private readonly items: Set<string>;
  constructor(private readonly id: string) {
    this.items = new Set(recall<string[]>(id) ?? []);
  }
  has(x: string): boolean {
    return this.items.has(x);
  }
  set(x: string, on: boolean): void {
    if (on === this.items.has(x)) return;
    if (on) this.items.add(x);
    else this.items.delete(x);
    remember(this.id, [...this.items]);
  }
}

/**
 * A set of ids kept for this browser tab (sessionStorage) rather than one
 * history entry: state that belongs to a thing shown on several entries, such
 * as the tool cards open in a transcript. A reload keeps it.
 */
export class SessionSet {
  private readonly items: Set<string>;
  constructor(private readonly id: string) {
    let saved: unknown = null;
    try {
      saved = JSON.parse(globalThis.sessionStorage?.getItem(`${NS}:${id}`) ?? 'null');
    } catch {
      /* storage blocked or corrupt: start empty */
    }
    this.items = new Set(Array.isArray(saved) ? saved.filter((x): x is string => typeof x === 'string') : []);
  }
  has(x: string): boolean {
    return this.items.has(x);
  }
  set(x: string, on: boolean): void {
    if (on === this.items.has(x)) return;
    if (on) this.items.add(x);
    else this.items.delete(x);
    try {
      globalThis.sessionStorage?.setItem(`${NS}:${this.id}`, JSON.stringify([...this.items]));
    } catch {
      /* storage blocked or full: the state lives until the page goes */
    }
  }
}
