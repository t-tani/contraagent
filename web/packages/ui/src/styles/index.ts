// The stylesheets the elements share, one job each. `base` is what every element
// starts from; the others are opt-in, for the elements that show what they style.
import type { CSSResult } from 'lit';
import { chipStyles } from './chips.js';
import { layoutStyles } from './layout.js';
import { motionStyles } from './motion.js';
import { resetStyles } from './reset.js';
import { statusStyles } from './status.js';
import { textStyles } from './text.js';
import { tokenStyles } from './tokens.js';

export { chipStyles, layoutStyles, motionStyles, resetStyles, statusStyles, textStyles, tokenStyles };
export { prose } from './prose.js';
export { meterStyles } from './meter.js';
export { legendStyles } from './legend.js';
export { executorIconStyles } from './executor-icon.js';
export { factStyles } from './facts.js';

/** Every element's styles, in cascade order: the tokens, then the shared rules. */
export const base: CSSResult[] = [tokenStyles, resetStyles, textStyles, statusStyles, chipStyles, layoutStyles, motionStyles];
