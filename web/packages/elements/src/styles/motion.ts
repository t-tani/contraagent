// Motion: the keyframes the elements use, and none of it for a reader who asks
// for reduced motion.
import { css } from 'lit';

export const motionStyles = css`
  .enter { animation: enter 0.5s var(--ease) both; }

  @keyframes turn { to { transform: rotate(360deg); } }
  @keyframes breathe {
    0%, 100% { opacity: 0.45; box-shadow: 0 0 0 0 transparent; transform: scale(0.85); }
    50% { opacity: 1; box-shadow: 0 0 0 4px var(--status-running-bg); transform: scale(1); }
  }
  @keyframes ping { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--status-running) 55%, transparent); } 80%, 100% { box-shadow: 0 0 0 9px transparent; } }
  @keyframes enter { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @keyframes bump { 0% { transform: scale(1); } 35% { transform: scale(1.04); box-shadow: 0 0 0 1px var(--line2); } 100% { transform: scale(1); } }
  @keyframes scan { to { left: 100%; } }
  @keyframes growx { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  @keyframes stripes { to { background-position: 17px 0; } }
  @keyframes toast-in { from { opacity: 0; transform: translateY(12px) scale(0.97); } to { opacity: 1; transform: none; } }
  @keyframes toast-out { to { opacity: 0; transform: translateX(24px); } }
  @keyframes rowin { from { background: color-mix(in srgb, var(--text) 10%, transparent); } to { background: transparent; } }
  @keyframes bounce { 0%, 80%, 100% { transform: translateY(0); opacity: 0.45; } 40% { transform: translateY(-5px); opacity: 1; } }
  @keyframes core-beat { 0%, 100% { transform: scale(1); } 50% { transform: scale(0.72); } }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }
`;
