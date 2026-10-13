// An element's visible words. Each element takes `strings: Partial<XStrings>`
// and falls back to its English defaults (`DEFAULT_X_STRINGS`) for a word it is
// not given; a word with a number is a function, so plural rules and word order
// belong to the host.

/** `given` over `defaults`: a word left out (or undefined) keeps its default. */
export function withDefaults<T extends object>(defaults: Readonly<T>, given: Partial<T> | null | undefined): T {
  const out = { ...defaults };
  if (given) for (const [k, v] of Object.entries(given)) if (v !== undefined) (out as Record<string, unknown>)[k] = v;
  return out;
}
