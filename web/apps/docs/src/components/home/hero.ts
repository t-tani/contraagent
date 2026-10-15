// The landing page's first screen: the install command's copy button, the coding
// agent the card's command names (one after another while the card is on screen),
// and, where the browser has no scroll-driven animations, the scene's progress
// (--hero-p, --stage-p) from the scroll position (./scene.css).

const reduced = matchMedia('(prefers-reduced-motion: reduce)');

for (const button of document.querySelectorAll<HTMLButtonElement>('.ca-copy')) {
  const status = button.parentElement?.querySelector<HTMLElement>('.ca-copied');
  let timer = 0;
  button.addEventListener('click', () => {
    void navigator.clipboard.writeText(button.dataset['copy'] ?? '').then(() => {
      button.textContent = 'Copied';
      if (status) status.textContent = 'Install command copied';
      clearTimeout(timer);
      timer = window.setTimeout(() => {
        button.textContent = 'Copy';
        if (status) status.textContent = '';
      }, 2000);
    });
  });
}

const card = document.querySelector<HTMLElement>('.ca-agents-card');
const agentName = card?.querySelector<HTMLElement>('[data-agent-name]');
const rows = [...(card?.querySelectorAll<HTMLElement>('[data-agent]') ?? [])];
if (card && agentName && rows.length && !reduced.matches) {
  let i = 0;
  let timer = 0;
  const step = (): void => {
    i = (i + 1) % rows.length;
    rows.forEach((r, k) => r.classList.toggle('is-on', k === i));
    const next = rows[i].dataset['agent'] ?? '';
    agentName.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-4px)' }], { duration: 160, easing: 'ease-in' }).onfinish = () => {
      agentName.textContent = next;
      agentName.animate([{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }], { duration: 220, easing: 'ease-out' });
    };
  };
  new IntersectionObserver(([e]) => {
    clearInterval(timer);
    if (e?.isIntersecting) timer = window.setInterval(step, 2200);
  }).observe(card);
}

// Focus in the hero once it has receded (the replay over it): back to the top, where it shows.
const hero = document.querySelector<HTMLElement>('[data-hero]');
hero?.addEventListener('focusin', () => {
  if (window.scrollY > 0 && matchMedia('(min-width: 50rem)').matches && !reduced.matches) window.scrollTo({ top: 0 });
});

// Without scroll-driven animations: the same frames from the scroll position, read once per frame.
if (!CSS.supports('animation-timeline: scroll()') && !reduced.matches) {
  // Each on the element it moves, and not inherited (scene.css registers them): a change restyles that element alone.
  const heroEl = document.querySelector<HTMLElement>('[data-hero]');
  const stage = document.querySelector<HTMLElement>('.rr-window');
  let top = 0;
  let pin = 0;
  const measure = (): void => {
    pin = window.innerHeight * 0.7;
    // Offsets, not the box: the box moves with the transform this sets.
    top = 0;
    for (let el: HTMLElement | null = stage; el; el = el.offsetParent as HTMLElement | null) top += el.offsetTop;
  };
  let queued = false;
  const frame = (): void => {
    queued = false;
    const y = window.scrollY;
    const vh = window.innerHeight;
    const clamp = (v: number): number => Math.min(1, Math.max(0, v));
    heroEl?.style.setProperty('--hero-p', clamp(y / pin).toFixed(4));
    // The window's top from the bottom of the screen (0) to a quarter of the way down (1).
    stage?.style.setProperty('--stage-p', clamp((vh - (top - y)) / (vh * 0.75)).toFixed(4));
  };
  const queue = (): void => {
    if (!queued) {
      queued = true;
      requestAnimationFrame(frame);
    }
  };
  measure();
  frame();
  addEventListener('scroll', queue, { passive: true });
  addEventListener('resize', () => {
    measure();
    queue();
  });
}

// A module: its names are its own.
export {};
