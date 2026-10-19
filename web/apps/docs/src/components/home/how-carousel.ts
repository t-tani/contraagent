// The "how it works" scene on a narrow screen (HowItWorks.astro, ./how.css): the steps
// are cards side by side that scroll one at a time (scroll snap), with a button to
// the step before and after, a dot for each step and the step's number. The card on
// screen is the scene's progress: the agent's loop lights its words up to that step,
// and the list is as tall as that card (--how-h), so the buttons are right under it.
// A sideways swipe moves the list here, not in the browser, and at most one card: the
// browser's momentum carries a fast flick past the next card although every card has
// `scroll-snap-stop: always`. The keyboard, a trackpad and a wheel scroll as usual.
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
  /** The swipe the list follows (see below), while a finger is on it. */
  let swipe: Swipe | undefined;
  const landed = (): void => {
    aim = -1;
    clearTimeout(aimTimer);
    if (!swipe?.own) list.classList.remove('is-swiped');
    if (narrow.matches) mark(nearest());
  };
  /** The scroll position that puts card `k` in the middle of the list. */
  const place = (k: number): number => {
    const s = steps[k];
    return Math.max(0, Math.min(list.scrollWidth - list.clientWidth, s.offsetLeft - (list.clientWidth - s.offsetWidth) / 2));
  };
  const go = (k: number): void => {
    const to = Math.max(0, Math.min(steps.length - 1, k));
    aim = to;
    mark(to);
    list.scrollTo({ left: place(to), behavior: reduced.matches ? 'auto' : 'smooth' });
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

  /*
   * A swipe: once a finger moves more sideways than up or down, the list follows it,
   * from the card it started on to the one before or after and no further, without
   * snapping (`is-swiped`, ./how.css) until it lands. Let go past half of the way, or
   * fast enough towards it, it goes on to that card; otherwise back. Up and down, the
   * page scrolls as usual.
   */
  interface Swipe {
    /** Where the finger and the list were when the swipe began: once it is sideways, where it became so. */
    x: number;
    y: number;
    left: number;
    /** The card it started on. */
    from: number;
    /** Sideways (the list's), up or down (the page's), or not yet known. */
    own: boolean | undefined;
    /** The finger's positions and times over its last 100 ms, for its speed when it lets go. */
    trail: [number, number][];
  }
  /** Further than this from where it began (px), a finger's move has a direction. */
  const SLOP = 8;
  /** Faster than this (px per ms) towards the next card, a short flick goes on to it. */
  const FLICK = 0.3;
  /** The finger's speed towards the end of the list (px per ms) over its last moves. */
  const speed = (trail: [number, number][]): number => {
    const [first, last] = [trail[0], trail.at(-1)!];
    return last[1] > first[1] ? (first[0] - last[0]) / (last[1] - first[1]) : 0;
  };
  const track = (s: Swipe, x: number, at: number): void => {
    s.trail = [...s.trail.filter(([, t]) => at - t < 100), [x, at]];
  };
  const letGo = (e?: TouchEvent): void => {
    const s = swipe;
    swipe = undefined;
    if (!s?.own) return;
    const t = e?.changedTouches[0];
    if (t) track(s, t.clientX, e.timeStamp);
    const moved = list.scrollLeft - place(s.from);
    const way = Math.sign(moved);
    const to = Math.max(0, Math.min(steps.length - 1, s.from + way));
    const on = to !== s.from && (Math.abs(moved) > Math.abs(place(to) - place(s.from)) / 2 || speed(s.trail) * way > FLICK);
    const k = on ? to : s.from;
    if (Math.abs(list.scrollLeft - place(k)) < 1) landed();
    else go(k);
  };
  list.addEventListener(
    'touchstart',
    (e) => {
      // A second finger ends the swipe: two are a zoom.
      if (swipe?.own) letGo();
      const t = e.touches[0];
      swipe =
        narrow.matches && e.touches.length === 1
          ? { x: t.clientX, y: t.clientY, left: 0, from: 0, own: undefined, trail: [[t.clientX, e.timeStamp]] }
          : undefined;
    },
    { passive: true },
  );
  list.addEventListener(
    'touchmove',
    (e) => {
      if (!swipe || swipe.own === false) return;
      const t = e.touches[0];
      if (swipe.own === undefined) {
        const [dx, dy] = [t.clientX - swipe.x, t.clientY - swipe.y];
        if (Math.hypot(dx, dy) < SLOP) return;
        swipe.own = Math.abs(dx) > Math.abs(dy);
        if (!swipe.own) return;
        // The swipe takes over from a button's scroll still under way: the card it aims at is the one the swipe starts on.
        clearTimeout(aimTimer);
        aim = -1;
        Object.assign(swipe, { x: t.clientX, left: list.scrollLeft, from: current });
        list.classList.add('is-swiped');
      }
      if (e.cancelable) e.preventDefault();
      const ends = [place(Math.max(0, swipe.from - 1)), place(Math.min(steps.length - 1, swipe.from + 1))];
      list.scrollLeft = Math.max(ends[0], Math.min(ends[1], swipe.left - (t.clientX - swipe.x)));
      track(swipe, t.clientX, e.timeStamp);
    },
    { passive: false },
  );
  list.addEventListener('touchend', letGo);
  list.addEventListener('touchcancel', letGo);

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
