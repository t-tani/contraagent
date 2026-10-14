// Pure functions from contraagent's run data to what the generic elements of
// `@contraagent/elements` take: the lists' filters, the columns of the tasks
// list and the history, the figures' tiles, the timeline's lanes, a checked
// file's rows, the pipeline graph's layers and loops' passes, and a transcript's
// sections.
export * from './filters.js';
export * from './task-columns.js';
export * from './journal-columns.js';
export * from './kpi-tiles.js';
export * from './lanes.js';
export * from './check-rows.js';
export * from './model-shares.js';
export { graphFromPlan, graphInput, matrixFromPlan, matrixInput, type GraphWordsContext } from './graph/input.js';
export { autoLayer, layerGraph, parentLayer, resolveLayer, splitLayer } from './graph/layer.js';
export { passMatrix, sortRows as sortPassRows, type MatrixSort, type PassMatrix } from './graph/matrix.js';
export { markSel, parseSelection, type Selected } from './graph/selection.js';
export { taskStateStyles } from './graph/words.js';
export { compound, chooseOpen, doi, interest, notable, placeKey, placeStats, towardOf, type Compound, type OpenChoice, type PlaceStats } from './graph/compound.js';
export { LOOP_SEGMENT, type FlowBox, type GraphNode, type LayerGraph, type LayerMark, type LayerModel, type LoopBox } from './graph/types.js';
export * from './transcript/index.js';
