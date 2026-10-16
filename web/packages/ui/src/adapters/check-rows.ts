// A checked file's fields as the rows of `<cae-check-table>`: each field of its
// schema against what the file holds, and the fields the schema does not name.
// Pure.
import type { ContractSpec } from '@contraagent/api';
import type { CheckRow, CheckTableStrings } from '@contraagent/elements/check-table';
import { msg, str } from '@lit/localize';

/** Whether a value has a schema's type; true for a type this check cannot judge (the model's own check judges it). */
export function typeOk(t: string, v: unknown): boolean {
  if (t.startsWith('list[') || t === 'array') return Array.isArray(v);
  if (t === 'string') return typeof v === 'string';
  if (t === 'integer') return Number.isInteger(v);
  if (t === 'number') return typeof v === 'number';
  if (t === 'boolean') return typeof v === 'boolean';
  if (t === 'object') return v !== null && typeof v === 'object' && !Array.isArray(v);
  return true;
}

/** A `RootModel[str]`-style schema: the model wraps one value of the given type. */
export const rootOf = (name: string): string | null => /^RootModel\[(.+)\]$/.exec(name)?.[1] ?? null;

/** A rows schema (`Rows[Finding]`): the model of one line. */
export const rowOf = (name: string): string | null => /^Rows\[(.+)\]$/.exec(name)?.[1] ?? null;

/** The file as a JSON object, or null (no file, not JSON, or another JSON value). */
export function contentObject(o: ContractSpec): Record<string, unknown> | null {
  const c = o.file.content;
  return o.file.exists && c !== null && typeof c === 'object' && !Array.isArray(c) ? (c as Record<string, unknown>) : null;
}

/**
 * A row per field of the schema, then a row per field the file has that the
 * schema does not name. Without a file, the fields with no values or verdicts;
 * with a file that is not a JSON object, the fields with no verdicts. Null for
 * a text result (a text file, or one JSON value), which has no fields to check.
 */
export function checkRowsFromContract(o: ContractSpec): CheckRow[] | null {
  if (!o.fields.length && (o.schema_name === 'text' || rootOf(o.schema_name) !== null)) return null;
  const obj = contentObject(o);
  const rows: CheckRow[] = o.fields.map((x) => {
    const base = { name: x.name, expected: x.type, optional: !x.required };
    if (!obj) return { ...base, hasValue: false, verdict: 'none', verdictLabel: '' };
    if (!(x.name in obj))
      return x.required
        ? { ...base, hasValue: false, verdict: 'fail', verdictLabel: msg('missing'), tip: msg('A required field that is not in the file') }
        : { ...base, hasValue: false, verdict: 'none', verdictLabel: msg('absent (optional)') };
    const value = obj[x.name];
    return typeOk(x.type, value)
      ? { ...base, hasValue: true, value, verdict: 'pass', verdictLabel: msg('passed') }
      : { ...base, hasValue: true, value, verdict: 'fail', verdictLabel: msg('wrong type'), tip: msg(str`Expected ${x.type}`) };
  });
  const extra = obj ? Object.keys(obj).filter((k) => !o.fields.some((x) => x.name === k)) : [];
  return [
    ...rows,
    ...extra.map(
      (k): CheckRow => ({
        name: k,
        expected: msg('not in the schema'),
        extra: true,
        hasValue: true,
        value: obj?.[k],
        verdict: 'warn',
        verdictLabel: msg('extra field'),
        tip: msg('Not in the schema'),
      }),
    ),
  ];
}

/** The check table's words. */
export function checkTableStrings(): CheckTableStrings {
  return {
    name: msg('Field'),
    expected: msg('Expected'),
    actual: msg('In the file'),
    verdict: msg('Check'),
    optional: msg('optional'),
    items: (n) => (n === 1 ? msg('1 item') : msg(str`${n} items`)),
    object: msg('object'),
  };
}
