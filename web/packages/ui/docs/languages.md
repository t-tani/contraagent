# Languages

Every element speaks English and Japanese, and switches in place, without a
reload, with Lit Localize.

## How the language is chosen

In the monitor, the switch in the header (`English` / `日本語`) changes the
language and remembers it for the next visit. With no choice made yet, the
monitor follows the browser's languages, then falls back to English.

`<ca-monitor locale="ja">` fixes the language for an embedded monitor. In
your own page, set it for every element at once:

```ts
import { setLocale, chooseLocale } from '@contraagent/ui/localize';

await setLocale('ja');     // this page only
await chooseLocale('ja');  // and remember it, as the monitor's switch does
```

## Setting up Lit Localize

Importing the package does not configure Lit Localize. `configureLocales()`
does, once per page; `<ca-monitor>` calls it when it connects, and `setLocale`
calls it first if nothing has. Until then the elements speak English. A
language's text is a module of its own, loaded the first time the language is
chosen; `<ca-monitor>` draws its first view after it is loaded.

Lit Localize can be configured only once per page. On a page whose own code
configured it first, `configureLocales()` returns `false`: the elements stay
in English and `<ca-monitor>` shows no language switch.

What is translated is the monitor's own wording: labels, headings, tooltips and
causes, and the words for a run's codes (a stop such as `completed` shows as
"done"; a code the monitor does not know shows as "unknown (<code>)"). Dates
and times follow the language too (`Oct 12, 10:38:40`, `10月12日 10:38:40`). What
a run wrote stays as it is: kind and unit names, model and role names, file
paths, failure reasons, and the transcripts.

## Adding a language

The English text is written in the sources, wrapped in `msg()`. Translations
live in one XLIFF file per language (`xliff/<locale>.xlf`), and a typed module is
generated from each. A new language is one more code in `targetLocales` of
`lit-localize.json`, its name in `LOCALE_NAMES`, and a loader for its generated module:

::code{file="../src/core/i18n.ts" from="/** Each locale's name" to="let localization"}
