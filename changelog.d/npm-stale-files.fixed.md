The npm packages hold only the files their sources build. A package built in a checkout
that had built it before also carried the outputs of source files that no longer exist
(in 0.1.0, old modules of `@contraagent/ui` such as `dist/core/route.js`); each package's
build now starts from an empty `dist/`.
