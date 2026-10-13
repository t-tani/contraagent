// The words the UI shows for run data, in the reader's terms. The code's own
// terms (stop values, plan states, round, hop, attempt ...) stay in the data and
// in tooltips; what the reader sees comes from here, so every screen says the
// same thing for the same state. The mapping is documented in AGENTS.md
// ("Words the UI shows").
export * from './format.js';
export * from './outcome.js';
export * from './stop.js';
export * from './causes.js';
export * from './attempts.js';
export * from './passes.js';
export * from './credential.js';
export * from './hops.js';
export * from './quota.js';
export * from './contract.js';
export * from './run-line.js';
export * from './hosts.js';
export * from './table.js';
export * from './changes.js';
export * from './units.js';
