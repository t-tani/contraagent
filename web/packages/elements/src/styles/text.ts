// Text: code, captions, words read only by screen readers, line breaks in a
// tight box, links.
import { css } from 'lit';

export const textStyles = css`
  .jmono, code, .mono { font-family: var(--mono); }
  /* read by screen readers, not shown: the word beside a status mark or an icon */
  .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .jmono { font-size: 11.5px; }
  .meta { color: var(--text-muted); font-size: var(--font-size-sm); }
  /* a label in a tight box: it wraps at spaces and between phrases, never inside a word (Japanese included) */
  .words { word-break: keep-all; overflow-wrap: break-word; line-break: strict; }
  /* one fact of a row in .words (factLine): the line breaks between facts first, inside one only when it is wider than the box */
  .words .f { display: inline-block; max-width: 100%; }
  @supports (word-break: auto-phrase) {
    .words:lang(ja) { word-break: auto-phrase; }
  }
  .mut, .jdim { color: var(--text-muted); }
  a.lnk { color: var(--accent); cursor: pointer; text-decoration: none; }
  a.lnk:hover { text-decoration: underline; }
`;
