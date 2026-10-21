// The "how it works" scene on a narrow screen (HowItWorks.astro, ./how.css): the steps
// are cards side by side that scroll one at a time (scroll snap), with a button to
// the step before and after, a dot for each step and the step's number. The step is
// the scene's progress: the agent's loop lights its words up to it, and the list is as
// tall as its card (--how-h), so the buttons are right under it. A button or a swipe
// sets the step and scrolls the list to its card; any other scroll that comes to an
// end (`scrollend`) sets the step to the card the list rests on, whatever moved the list.
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

  /**
   * The scroll position at which card `k` snaps (CSS Scroll Snap, `scroll-snap-align:
   * center`): the middle of its border box at the middle of the snapport, the list's
   * box inside its scrollbars less its `scroll-padding`, within the positions the list
   * can scroll to. Read from the layout, in fractions of a pixel.
   */
  const place = (k: number): number => {
    const css = getComputedStyle(list);
    const [start, end] = [parseFloat(css.scrollPaddingLeft) || 0, parseFloat(css.scrollPaddingRight) || 0];
    const box = steps[k].getBoundingClientRect();
    const left = box.left - list.getBoundingClientRect().left - list.clientLeft + list.scrollLeft;
    const snap = left + box.width / 2 - (start + (list.clientWidth - start - end) / 2);
    return Math.max(0, Math.min(list.scrollWidth - list.clientWidth, snap));
  };
  /** The card the list snaps to from where it is: the one whose snap position is nearest. */
  const nearest = (): number => {
    let best = 0;
    steps.forEach((_, k) => {
      if (Math.abs(place(k) - list.scrollLeft) < Math.abs(place(best) - list.scrollLeft)) best = k;
    });
    return best;
  };

  /** The list as tall as the step's card. */
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

  /** The swipe the list follows (see below), while a finger is on it. */
  let swipe: Swipe | undefined;
  /**
   * Where a swipe that let go sends the list, until the list is there. Snapping is off
   * (`is-swiped`), so the list stops exactly where it is sent: the `scroll` that puts it
   * there ends the swipe. Until then, the end of a scroll is that of one of the finger's
   * moves (each scrolls the list), not the list at rest.
   */
  let release: number | undefined;
  /**
   * The list at `left`: the position the browser keeps for one it is sent to differs
   * from it by less than a device pixel, at most a CSS pixel at a device pixel ratio of 1 or more.
   */
  const there = (left: number): boolean => Math.abs(list.scrollLeft - left) < Math.max(1, 1 / devicePixelRatio);
  /**
   * Where a button's smooth scroll sends the list, until the list is there or the reader
   * takes it. A smooth scroll ends at its destination and does not pass it, so the
   * `scroll` that finds the list there is its end. No `scrollend` before that one is the
   * list at rest: a scroll that completed before the press may still have its `scrollend`
   * to come (input runs before the scroll steps that send it), and Chromium sends the
   * `scrollend` of a smooth scroll that replaced another one while the list still moves,
   * and none when it arrives. A newer press records its own destination. A script's
   * scroll that cuts a button's short ends nothing: the step stays the button's card
   * until the list arrives or the reader's input.
   */
  let sending: number | undefined;
  /** The swipe's scroll at its end: snapping on again, and the step the card the list rests on. */
  const land = (): void => {
    release = undefined;
    sending = undefined;
    list.classList.remove('is-swiped');
    if (narrow.matches) mark(nearest());
  };
  const go = (k: number): void => {
    const to = Math.max(0, Math.min(steps.length - 1, k));
    mark(to);
    const left = place(to);
    if (list.classList.contains('is-swiped')) release = left;
    // An instant scroll is there at once, and its `scrollend` finds the list there; a list there does not move.
    else sending = !reduced.matches && !there(left) ? left : undefined;
    // The browser ends a scroll still under way, and does not scroll a list already there.
    list.scrollTo({ left, behavior: reduced.matches ? 'auto' : 'smooth' });
    // Already there, or there at once (an instant scroll): no end of a scroll to wait for.
    if (release !== undefined && there(release)) land();
  };
  for (const b of [prev, next])
    b.addEventListener('click', () => {
      if (b.getAttribute('aria-disabled') !== 'true') go(current + Number(b.dataset['go']));
    });

  // A scroll of the list has ended (CSSOM View: `scrollend` comes when the scroll sequence
  // is over and the position has changed; a smooth scroll that a newer scroll ends has
  // none, nor has a scroll to where the list already is). Snapping has placed the list,
  // so the card it rests on is the step, whatever moved it: a button, the reader, a script,
  // except while a button's scroll is on its way (`sending`) or a swipe's (`release`).
  list.addEventListener('scrollend', () => {
    if (swipe?.own || release !== undefined || sending !== undefined) return;
    if (narrow.matches) mark(nearest());
  });
  list.addEventListener(
    'scroll',
    () => {
      if (sending !== undefined && there(sending)) sending = undefined;
      if (release !== undefined && there(release)) land();
    },
    { passive: true },
  );
  // The reader's own input takes the list from a button's or a swipe's scroll: from then on,
  // the card it rests on is the step; after a swipe, snapping on again from where it is.
  for (const type of ['pointerdown', 'wheel', 'keydown', 'focusin'])
    list.addEventListener(
      type,
      () => {
        sending = undefined;
        if (release !== undefined) land();
      },
      { passive: true },
    );

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
    go(on ? to : s.from);
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
        // The swipe starts on the step: the card a button sends the list to, or the one it rests on.
        // Its first move ends a button's scroll still under way.
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
    sending = undefined;
    current = -1;
    mark(narrow.matches ? nearest() : 0);
  };
  set();
  narrow.addEventListener('change', set);
}

export {};
