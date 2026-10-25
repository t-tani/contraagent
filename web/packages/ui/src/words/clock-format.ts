// The one time format of rows and chips (`localTime`), made once per language.

const formats = new Map<string, Intl.DateTimeFormat>();

/** The time of day `10:38:40`, or with the date `Oct 12, 10:38:40`, as `locale` writes it. */
export function clockFormat(locale: string, withDate: boolean): Intl.DateTimeFormat {
  const id = `${locale}|${withDate}`;
  let f = formats.get(id);
  if (!f) {
    f = new Intl.DateTimeFormat(locale, {
      ...(withDate ? { month: 'short', day: 'numeric' } : {}),
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    });
    formats.set(id, f);
  }
  return f;
}
