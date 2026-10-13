# Strings

An element shows words: a button's name, an empty state, a count. It takes
them from its `strings` property, a partial set of its `XStrings` interface,
and uses its English default (`DEFAULT_X_STRINGS`) for each word it is not
given. A word with a number is a function of the number, so the host decides
plural forms and word order. Nothing here depends on a localization library:
the host translates.

::code{file="../src/markdown/cae-markdown.ts" from="export interface MarkdownStrings" to="export const DEFAULT_MARKDOWN_STRINGS"}

```ts
markdown.strings = { showRendered: 'プレビューを表示', showSource: 'ソースを表示' };
```

`withDefaults(defaults, given)` merges the two, as each element does.
