// What every element's shadow root starts from: box sizing, scrollbars, the
// selection and the focus ring.
import { css } from 'lit';

export const resetStyles = css`
  *, *::before, *::after { box-sizing: border-box; }
  /* a thin bar whose thumb reads against any surface (3:1), the same at rest and under the pointer */
  * { scrollbar-width: thin; scrollbar-color: var(--line-field) transparent; }
  ::selection { background: var(--selection); }
  :focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; }
  button { font: inherit; color: inherit; }
  [hidden] { display: none !important; }
  /* a press answers at once, before what it does shows */
  :is(button, [role='button'], [role='tab'], summary, a[href]):active { opacity: 0.72; }
`;
