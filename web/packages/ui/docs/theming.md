# Theming

The elements take their colours, fonts, type scale and corners from the
`--ca-*` custom properties and the built-in themes of `@contraagent/elements`:
[its theming page](../../elements/docs/theming.md) lists them, what each colour
means, and how to build a theme of your own. Importing `@contraagent/ui` adds
the themes' rules to the page's document, so `data-ca-theme` on any ancestor
picks a theme.

## The monitor's theme

In the monitor, the header's theme control changes the theme and remembers it
in this browser. `System` follows the system's colour scheme (contraagent Dark
or contraagent Light). With no choice made, the monitor shows contraagent Dark.

`<ca-monitor theme="nord">` fixes the theme of an embedded monitor; it also
takes `system`. The theme it shows is reflected as `data-ca-theme` on the
element (and on `<html>`, with `history="url"`).
