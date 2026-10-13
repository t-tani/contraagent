// What every element's shadow root starts from: box sizing, scrollbars, the
// selection and the focus ring.
import { css } from 'lit';

export const resetStyles = css`
  *, *::before, *::after { box-sizing: border-box; }
  * { scrollbar-width: thin; scrollbar-color: var(--line2) transparent; }
  *:hover { scrollbar-color: var(--text-muted) transparent; }
  ::selection { background: var(--selection); }
  :focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; }
  button { font: inherit; color: inherit; }
  [hidden] { display: none !important; }
`;
