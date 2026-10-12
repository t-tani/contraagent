# Theming

Each element keeps its styles in its own shadow root, so your page's CSS cannot
break it and its CSS cannot leak into your page. What you can change is the set
of `--ca-*` custom properties: set them on any ancestor (or on the element),
and every element inside reads them. Unset ones keep the dark defaults. A light
theme:

::code{file="examples/theme.css"}

Every property and its default is declared in `src/styles/base.ts` (`tokens`).
