`@contraagent/elements` and `@contraagent/ui` change with the monitor's form:

- An element with no theme shows contraagent Light or contraagent Dark as the `color-scheme` of its page says (it showed contraagent Dark, with light text on a page of any colour), and sets no `color-scheme` of its own.
- `DEFAULT_THEME` → `DEFAULT_CHOICE`, which is `system`; `THEME_CHOICES` starts with it, and `resolveTheme` follows the colour scheme for anything that is not a theme.
- The type scale is in rem and starts at 12px: `--ca-font-size-xs` 0.75rem, `-sm` 0.8125rem (the monitor's text), `-md` 0.875rem, `-lg` 1rem, `-xl` 1.25rem, `-2xl` 1.75rem (they were 10, 11, 12, 13, 15 and 28px). `--ca-radius-md` is 6px and `--ca-radius-lg` 10px (8 and 12px).
- `--ca-line-field` is new: the edge of a text field, at 3:1 against the surfaces.
- `<cae-segmented>` is a track with the chosen option raised on it; `--cae-segmented-divider` is removed.
- `<cae-layered-graph>` draws on its host's surface; `--cae-graph-frame` sets a surface of its own.
- `<cae-stat-tiles>` draws figures with a line between two of a row, without a box per tile. The line stands in the middle of `--cae-stat-tiles-gap` (32px by default, 12px before): set the space with that property, not with `gap` on the `tiles` part.
- `TranscriptTag.bare` shows a tag's value without its label, which a screen reader still reads.
- `<ca-theme-switch>` → `<ca-settings>`, which also holds the language (`ca-choose-locale`, new) and the keys; `<ca-clock>` is removed.
