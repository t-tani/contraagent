Panel bodies of two more types. `code` (`contraagent.monitor.CodeBody`) is a text
highlighted by its language (`LANGUAGES`, or a file extension), with line numbers from
`start`, highlighted lines and ranges, a path, wrapped or scrolled, a Copy button, and
cut after `CODE_LINES` lines. `tree` (`TreeBody`, `TreeNode`, `TreeLink`) is a list of
nodes the reader folds and opens with the mouse or the keyboard, each with an icon, a
badge and its tone, and either the code shown beside the tree while the node is
selected or a link to a run panel, a task or a body of the same panel (each panel
body's new `anchor`). `@contraagent/elements` adds `<cae-code>`
(`@contraagent/elements/code`) and `<cae-tree>` (`@contraagent/elements/tree`), and its
markdown highlights the same languages.
