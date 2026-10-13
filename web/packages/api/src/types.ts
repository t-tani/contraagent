// Names for the generated schema types. `schema.ts` is generated from the
// monitor's OpenAPI document (`pnpm gen`); everything here is an alias of it.
import type { components } from './schema.js';

type S = components['schemas'];

export type { components, paths } from './schema.js';

/** A JSON object whose keys a domain chooses (a panel's body, a contract file's content). */
export type JsonObject = Record<string, unknown>;

export type Info = S['Info'];
export type PanelInfo = S['PanelInfo'];
export type RunSummary = S['RunSummary'];
export type Hosts = S['Hosts'];
export type HostSummary = S['HostSummary'];
export type AccountQuota = S['AccountQuota'];

export type JournalRow = S['JournalRow'];
/** How one attempt ended (`JournalRow.stop`): a `Stop` of the Python package, or `skipped`. */
export type Stop = JournalRow['stop'];
export type Hop = S['Hop'];
export type TokenUsage = S['TokenUsage'];
export type QuotaReading = S['QuotaReading'];
export type JournalPage = S['JournalPage'];

export type Executor = NonNullable<S['PlanNode']['executor']>;

export type Plan = S['Plan'];
export type PlanNode = S['PlanNode'];
export type PlanGroup = S['PlanGroup'];
export type TaskState = PlanNode['state'];
export type FlowFrame = S['FlowFrame'];
export type FlowLoop = S['FlowLoop'];
export type FlowCallNode = S['FlowCallNode'];
export type FlowCallState = FlowCallNode['state'];

export type Outputs = S['Outputs'];
export type OutputTally = S['OutputTally'];
export type ContractRecord = S['ContractRecord'];
export type ContractSpec = S['ContractSpec'];
export type ContractField = S['ContractField'];
export type ContractStatus = NonNullable<ContractSpec['status']>;
export type FileView = S['FileView'];

export type TaskDefinition = S['TaskDefinition'];
export type DefinitionFile = S['DefinitionFile'];

export type CursorView = S['CursorView'];
export type UnitPosition = S['UnitPosition'];

export type Procs = S['Procs'];
export type ProcNode = S['ProcNode'];
export type AgentProcess = S['AgentProcess'];
export type InflightPythonTask = S['InflightPythonTask'];

export type TaskDetail = S['TaskDetail'];
export type TaskLaunch = S['TaskLaunch'];
export type TaskIO = S['TaskIO'];
export type UpstreamTask = S['UpstreamTask'];
export type DownstreamTask = S['DownstreamTask'];

// --- transcripts -----------------------------------------------------------

export type StreamPage = S['StreamPage'];
export type LaunchEvent = S['LaunchEvent'];
export type MessageUpdateEvent = S['MessageUpdateEvent'];
export type ToolStartEvent = S['ToolStartEvent'];
export type ToolEndEvent = S['ToolEndEvent'];
export type ToolCallEchoEvent = S['ToolCallEchoEvent'];
export type ToolResultEchoEvent = S['ToolResultEchoEvent'];
/** Named apart from the DOM's `MessageEvent`. */
export type TranscriptMessageEvent = S['MessageEvent'];
export type NoticeEvent = S['NoticeEvent'];
export type RetryEvent = S['RetryEvent'];
export type OtherEvent = S['OtherEvent'];

/** One transcript event as the wire carries it: a known model, or an `OtherEvent`. */
export type TranscriptEvent = StreamPage['events'][number];

/** The transcript events the monitor renders, discriminated by `type`. */
export type KnownTranscriptEvent =
  | LaunchEvent
  | MessageUpdateEvent
  | ToolStartEvent
  | ToolEndEvent
  | ToolCallEchoEvent
  | ToolResultEchoEvent
  | TranscriptMessageEvent
  | NoticeEvent
  | RetryEvent;

const KNOWN_TYPES: ReadonlySet<string> = new Set<KnownTranscriptEvent['type']>([
  'launch',
  'message_update',
  'tool_execution_start',
  'tool_execution_update',
  'tool_execution_end',
  'acall',
  'aresult',
  'message_start',
  'message_end',
  'turn_end',
  'notice',
  'auto_retry_start',
]);

/** The event as one of the known models, or null for any other `type`. */
export function knownEvent(e: TranscriptEvent): KnownTranscriptEvent | null {
  return KNOWN_TYPES.has(e.type) ? (e as KnownTranscriptEvent) : null;
}

// --- live feeds --------------------------------------------------------------

/** One message of `/events?run=`: `event` is the SSE event name, `data` its parsed JSON. */
export type RunMessage = S['RunEvent'];
// `PanelMessage` is the one whose `event` is a plain string; every other row
// would also fit its shape, so it is told apart by that, not with `Exclude`.
type FixedRunMessage = RunMessage extends infer M
  ? M extends { event: infer E }
    ? string extends E
      ? never
      : M
    : never
  : never;
export type PanelEventName = `panel:${string}`;
/** A panel's message, with its event name typed. */
export interface PanelMessage {
  event: PanelEventName;
  data: JsonObject;
}
/** A run feed message with every `event` name a literal (or `panel:<name>`). */
export type RunFeedMessage = FixedRunMessage | PanelMessage;
/** The SSE event names with a fixed meaning, and what each one carries. */
export type RunEventData = { [M in FixedRunMessage as M['event']]: M['data'] };
export type RunEventName = keyof RunEventData;

export type StreamMessage = S['StreamMessage'];
