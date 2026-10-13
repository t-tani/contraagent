// Layout: the 12-column grid, a panel, a section heading, an empty state, a
// short clickable row.
import { css } from 'lit';

export const layoutStyles = css`
  .g12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; }
  .c12 { grid-column: span 12; }
  .c7 { grid-column: span 7; }
  .c5 { grid-column: span 5; }
  @media (max-width: 1150px) {
    .c7, .c5 { grid-column: span 12; }
  }
  .panel { background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: var(--radius-lg); padding: 14px 16px; min-width: 0; box-shadow: 0 10px 28px color-mix(in srgb, var(--shadow) 40%, transparent); }
  .panel > h3 { margin: 0 0 12px; display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 600; color: var(--text-2); }
  .panel > h3 .r { margin-left: auto; font-weight: 400; font-size: 11.5px; color: var(--text-muted); }
  .sect-h { margin: 14px 0 8px; font-size: var(--font-size-md); color: var(--text-2); font-weight: 600; }
  .sect-h .meta { margin-left: 8px; font-weight: 400; }

  .blank { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 60px 16px; color: var(--text-muted); text-align: center; }
  .blank .ic { font-size: 30px; opacity: 0.55; }
  .blank b { color: var(--text-2); font-weight: 600; }
  .blank a.lnk { text-decoration: underline; }
  .blank.small { padding: 24px; }

  /* a short clickable row (failures, launches) */
  .fl { padding: 7px 10px; border-radius: var(--radius-md); cursor: pointer; display: grid; grid-template-columns: auto 1fr auto; gap: 2px 10px; align-items: baseline; }
  .fl > .meta:last-child { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
  .fl:hover { background: var(--raise); }
`;
