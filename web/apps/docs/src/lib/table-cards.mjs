// A Sätteri hast plugin for the pages' Markdown tables: a table of three columns or more is a list of
// records, which a phone shows as one card per row (src/styles/pages.css). The table gets the class
// `ca-cards`, and every cell after a row's first its column's name (`data-label`), which the card
// shows before the cell. A table of two columns stays a table on every screen, one that scrolls
// sideways inside itself when it is wider than the page (`data-scroll="x"`, as e2e/fit.ts reads it).

const elements = (node, name) => (node.children ?? []).filter((c) => c.type === 'element' && c.tagName === name);

/** @type {import('satteri').HastPluginDefinition} */
export const tableCards = {
  name: 'contraagent-table-cards',
  element: [
    {
      filter: ['table'],
      visit(table, ctx) {
        const head = elements(table, 'thead').flatMap((h) => elements(h, 'tr'))[0];
        const names = head ? elements(head, 'th').map((th) => ctx.textContent(th).trim()) : [];
        if (names.length < 3) {
          ctx.setProperty(table, 'data-scroll', 'x');
          return;
        }
        ctx.setProperty(table, 'className', ['ca-cards']);
        for (const body of elements(table, 'tbody'))
          for (const row of elements(body, 'tr'))
            elements(row, 'td').forEach((td, i) => {
              if (i > 0 && names[i]) ctx.setProperty(td, 'data-label', names[i]);
            });
      },
    },
  ],
};
