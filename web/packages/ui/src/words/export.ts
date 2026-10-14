// Words for an export (`contraagent monitor export`, `Info.export`): the monitor
// read from files, with no server.
import type { ExportInfo } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { listText, localTime } from './format.js';

/** The header's mark of an export: when it was written. */
export const exportedLabel = (e: ExportInfo): string =>
  msg(str`Exported ${localTime(e.exported_at, true)}`, { desc: 'The monitor shows files written at this time, not a live server' });

/** A view an export does not hold, in words. */
function leftOutLabel(view: string): string {
  if (view === 'transcripts') return msg('transcripts');
  if (view === 'processes') return msg('processes');
  return view;
}

/** What the export does not hold, for the mark's tooltip: "Not in this export: transcripts, processes". */
export const exportTip = (e: ExportInfo): string => msg(str`Not in this export: ${listText(e.left_out.map(leftOutLabel))}`);

/** Beside an empty view: what it would show is not in the export. */
export const notInExport = (): string => msg('not in this export');
