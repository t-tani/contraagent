// The words of a `<cae-data-table>`.
import type { DataTableStrings } from '@contraagent/elements/data-table';
import { msg } from '@lit/localize';

/** A table's words; `empty` is what it shows with no rows. */
export const tableStrings = (empty: string): Required<DataTableStrings> => ({
  empty,
  sortAscending: msg('Sort ascending'),
  sortDescending: msg('Sort descending'),
});
