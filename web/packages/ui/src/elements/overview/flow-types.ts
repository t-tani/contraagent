// Where a plan's tasks came from in the flow's code, as the monitor's API types it:
// each plan node's origin (`flow`, with each frame's loops and passes; `created_from`, `flow_call`) and the
// plan's flow calls. Every origin field is optional on the wire (absent for a task
// no flow created), so the readers in `logic.ts` check them before use.
export type { FlowCallNode, FlowFrame, FlowLoop, Plan as FlowPlan, PlanNode as FlowPlanNode } from '@contraagent/api';
