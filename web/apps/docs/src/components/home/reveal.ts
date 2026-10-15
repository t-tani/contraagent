// Where the browser has no scroll-driven animations: each part of the page below
// the replay gets .is-in once it comes into view, and ./reveal.css moves it there
// by a transition. Nothing is hidden before this runs, nor with reduced motion.
const PARTS = '.steps, .step, .ca-runner .card, .ca-start section';

if (!CSS.supports('animation-timeline: view()') && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const parts = document.querySelectorAll<HTMLElement>(PARTS);
  const seen = new IntersectionObserver(
    (entries) => {
      for (const e of entries)
        if (e.isIntersecting) {
          e.target.classList.add('is-in');
          seen.unobserve(e.target);
        }
    },
    { rootMargin: '0px 0px -8% 0px' },
  );
  // A part focused before it came into view is shown at once.
  document.addEventListener('focusin', (e) => {
    const part = e.target instanceof Element ? e.target.closest(PARTS) : null;
    part?.classList.add('is-in');
  });
  document.documentElement.classList.add('ca-reveal-js');
  for (const p of parts) seen.observe(p);
}

export {};
