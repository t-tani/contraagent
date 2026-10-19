// The "how it works" scene on a narrow screen (HowItWorks.astro, ./how.css): the steps
// are cards side by side that scroll one at a time (scroll snap), with a button to
// the step before and after, a dot for each step and the step's number. The card on
// screen is the scene's progress: the agent's loop lights its words up to that step,
// and the list is as tall as that card (--how-h), so the buttons are right under it.
// Each card's output is cut to its first lines where it is longer, with a button
// that shows it in full. On a wider screen nothing here applies (the classes it sets
// are read only by the narrow screen's rules).

const how = document.querySelector<HTMLElement>('.how');
const list = how?.querySelector<HTMLElement>('.how-steps');
const nav = how?.querySelector<HTMLElement>('.how-nav');
const narrow = matchMedia('(max-width: 49.99rem)');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');

if (how && list && nav) {
  const steps = [...list.querySelectorAll<HTMLElement>('.how-step')];
  const dots = [...nav.querySelectorAll<HTMLElement>('.how-dot')];
  const [prev, next] = [...nav.querySelectorAll<HTMLButtonElement>('.how-go')];
  const at = nav.querySelector<HTMLElement>('.how-at')!;
  const count = at.appendChild(document.createElement('span'));
  const named = at.appendChild(document.createElement('span'));
  named.className = 'how-sr';
  const loop = [...how.querySelectorAll<HTMLElement>('.how-loop-step')];
  let current = -1;

  /** The card whose middle is nearest the middle of the list. */
  const nearest = (): number => {
    const mid = list.scrollLeft + list.clientWidth / 2;
    let best = 0;
    steps.forEach((s, k) => {
      if (Math.abs(s.offsetLeft + s.offsetWidth / 2 - mid) < Math.abs(steps[best].offsetLeft + steps[best].offsetWidth / 2 - mid)) best = k;
    });
    return best;
  };

  /** The list as tall as the card on screen. */
  const fit = (): void => {
    if (narrow.matches && current >= 0) list.style.setProperty('--how-h', `${steps[current].offsetHeight}px`);
    else list.style.removeProperty('--how-h');
  };
  for (const s of steps)
    new ResizeObserver(() => {
      if (s === steps[current]) fit();
    }).observe(s);

  const mark = (k: number): void => {
    if (k === current) return;
    current = k;
    dots.forEach((d, i) => d.classList.toggle('is-on', i === k));
    steps.forEach((s, i) => s.classList.toggle('is-current', i === k));
    for (const l of loop) l.classList.toggle('is-on', k >= Number(l.dataset['from']));
    prev.setAttribute('aria-disabled', String(k === 0));
    next.setAttribute('aria-disabled', String(k === steps.length - 1));
    const title = steps[k].querySelector('.how-step-title')?.textContent ?? '';
    // The step's number on screen; its title too for a screen reader (the card on screen shows it).
    count.textContent = `Step ${k + 1} of ${steps.length}`;
    named.textContent = `: ${title}`;
    fit();
  };

  /** The card a button scrolls to, until the scroll ends: the cards it passes on the way are not the step. */
  let aim = -1;
  let aimTimer = 0;
  const landed = (): void => {
    aim = -1;
    clearTimeout(aimTimer);
    if (narrow.matches) mark(nearest());
  };
  const go = (k: number): void => {
    const to = Math.max(0, Math.min(steps.length - 1, k));
    const s = steps[to];
    aim = to;
    mark(to);
    list.scrollTo({ left: s.offsetLeft - (list.clientWidth - s.offsetWidth) / 2, behavior: reduced.matches ? 'auto' : 'smooth' });
    // The scroll's end says where it landed (scrollend); only a browser without the event guesses it is over by then.
    clearTimeout(aimTimer);
    if (!('onscrollend' in list)) aimTimer = window.setTimeout(landed, 900);
  };
  for (const b of [prev, next])
    b.addEventListener('click', () => {
      if (b.getAttribute('aria-disabled') !== 'true') go(current + Number(b.dataset['go']));
    });

  let queued = false;
  list.addEventListener(
    'scroll',
    () => {
      if (queued || aim >= 0) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        if (narrow.matches && aim < 0) mark(nearest());
      });
    },
    { passive: true },
  );
  list.addEventListener('scrollend', () => {
    if (aim < 0) return;
    if (nearest() === aim) return landed();
    // Elsewhere: the end of a scroll another press cut short, which the next scroll goes on
    // from, or a swipe that took the list somewhere else, which leaves it still. A list
    // still a frame later has landed where it is.
    const x = list.scrollLeft;
    requestAnimationFrame(() => {
      if (aim >= 0 && list.scrollLeft === x) landed();
    });
  });

  /**
   * Each output much longer than a cut one (a third more): cut, with its button; the
   * others whole, without (a few lines more are not worth a button).
   */
  const cut = (): void => {
    for (const s of steps) {
      const stage = s.querySelector<HTMLElement>('.how-stage')!;
      const more = s.querySelector<HTMLButtonElement>('.how-more')!;
      if (more.getAttribute('aria-expanded') === 'true') continue;
      stage.classList.add('is-cut');
      const long = narrow.matches && stage.scrollHeight > stage.clientHeight * 1.33;
      stage.classList.toggle('is-cut', long);
      more.hidden = !long;
    }
  };
  for (const s of steps) {
    const stage = s.querySelector<HTMLElement>('.how-stage')!;
    const more = s.querySelector<HTMLButtonElement>('.how-more')!;
    more.addEventListener('click', () => {
      const open = more.getAttribute('aria-expanded') !== 'true';
      more.setAttribute('aria-expanded', String(open));
      more.textContent = open ? 'Hide full output' : 'Show full output';
      stage.classList.toggle('is-cut', !open);
      // Closed again: the card's top back on screen, under the site's header, where the reader was.
      const top = s.getBoundingClientRect().top - (document.querySelector('header.header')?.getBoundingClientRect().bottom ?? 0);
      if (!open && top < 0) window.scrollBy({ top: top - 12, behavior: reduced.matches ? 'auto' : 'smooth' });
    });
  }

  const set = (): void => {
    how.classList.toggle('how-carousel', narrow.matches);
    nav.hidden = !narrow.matches;
    cut();
    current = -1;
    mark(narrow.matches ? nearest() : 0);
  };
  set();
  narrow.addEventListener('change', set);
}

export {};
