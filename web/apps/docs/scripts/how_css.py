"""Write src/components/home/how-stages.css: the landing page's "how it works" scene, its stages.

    python3 web/apps/docs/scripts/how_css.py

Each of the scene's stages owns its share (WEIGHTS) of the scroll through the
scene's track; the rules here depend on those shares: which panel, step and words
of the loop show at each point of the scroll, as scroll-driven animations, and as
the states the fallback reaches by transitions (how-scene.ts sets data-stage and
data-sub). The rest of the scene's style is how.css. WEIGHTS is HowItWorks.astro's
too, and how-scene.ts reads it from the track.
"""

import sys
from pathlib import Path

#: Each stage's share of the scroll: the check stage, which goes through three states, has two.
WEIGHTS = [1, 1, 1, 1, 2, 1, 1]
N = len(WEIGHTS)
#: The stage from which each word of the agent's loop is lit: write, check, fix, stub run, done.
LOOP = [3, 4, 4, 5, 6]
#: The check stage, and how far its terminal scrolls in its second and third states.
CHECK = 4
SCROLL = ("-22%", "-47%")
OUT = Path(__file__).resolve().parents[1] / "src" / "components" / "home" / "how-stages.css"


def pct(x: float) -> str:
    return f"{max(0.0, min(100.0, x)):.2f}%"


def window(k: int) -> tuple[float, float]:
    total = sum(WEIGHTS)
    return sum(WEIGHTS[:k]) * 100 / total, sum(WEIGHTS[: k + 1]) * 100 / total


def css() -> str:
    a4, b4 = window(CHECK)
    third = (b4 - a4) / 3
    a6, _ = window(N - 1)
    out: list[str] = [
        "/* Written by scripts/how_css.py from the stages' shares of the scroll; change the script, not this file. */",
        "",
        "@media (min-width: 64rem) and (prefers-reduced-motion: no-preference) {",
        "  @supports (animation-timeline: view()) {",
        "    .how-stage, .how-text, .how-glow, .how-n::after, .how-words, .how-loop-step::before,",
        "    .how-rail-fill, .how-depth, .slip, .term-loop, .run-mark {",
        "      animation-timing-function: linear;",
        "      animation-fill-mode: both;",
        "      animation-timeline: --how;",
        "      animation-range: contain 0% contain 100%;",
        "    }",
        "    .how-rail-fill { animation-name: how-rail; }",
        "    .how-depth { animation-name: how-depth; }",
    ]
    for k in range(N):
        out += [
            f"    .how-stage[data-k='{k}'], .how-step[data-k='{k}'] .how-text {{ animation-name: how-stage-{k}; }}",
            f"    .how-step[data-k='{k}'] .how-glow, .how-step[data-k='{k}'] .how-n::after {{ animation-name: how-on-{k}; }}",
            f"    .how-step[data-k='{k}'] .how-words {{ animation-name: how-words-{k}; }}",
        ]
    for j, frm in enumerate(LOOP):
        name = f"how-loop-{frm}{'b' if j and LOOP[j - 1] == frm else ''}"
        out.append(f"    .how-loop-step:nth-child({j + 1})::before {{ animation-name: {name}; }}")
    out += [
        "    .slip-1 { animation-name: how-slip-1; }",
        "    .slip-2 { animation-name: how-slip-2; }",
        "    .slip-3 { animation-name: how-slip-3; }",
        "    .term-loop { animation-name: how-scroll; }",
        "    .run-mark {",
        "      animation-name: how-mark;",
        f"      animation-range: contain calc({a6 + 1:.2f}% + var(--i) * 0.2%) contain calc({a6 + 2:.2f}% + var(--i) * 0.2%);",
        "    }",
        "  }",
        "",
        "  /* Without scroll-driven animations: the states by data-stage and data-sub (how-scene.ts), by transitions. */",
        "  @supports not (animation-timeline: view()) {",
        "    .how-stage, .how-text {",
        "      opacity: 0;",
        "      transform: translate3d(0, 1.25rem, 0) scale(0.985);",
        "      transition: opacity 0.45s ease, transform 0.6s cubic-bezier(0.2, 0.8, 0.2, 1);",
        "    }",
        "    .how-glow, .how-n::after { transition: opacity 0.4s ease; }",
        "    .how-words { opacity: 0.55; transition: opacity 0.4s ease; }",
        "    .how-loop-step::before { opacity: 0; transition: opacity 0.4s ease; }",
        "    .how-rail-fill { transform: scaleY(var(--how-p)); }",
        "    .how-track:not([data-stage]) .how-stage[data-k='0'],",
        "    .how-track:not([data-stage]) .how-step[data-k='0'] .how-text { opacity: 1; transform: none; }",
    ]
    for k in range(N):
        on = f".how-track[data-stage='{k}']"
        out += [
            f"    {on} .how-stage[data-k='{k}'],",
            f"    {on} .how-step[data-k='{k}'] .how-text,",
            f"    {on} .how-step[data-k='{k}'] .how-words {{ opacity: 1; transform: none; }}",
            f"    {on} .how-step[data-k='{k}'] .how-glow,",
            f"    {on} .how-step[data-k='{k}'] .how-n::after {{ opacity: 1; }}",
        ]
    for j, frm in enumerate(LOOP):
        sel = ",\n    ".join(f".how-track[data-stage='{s}'] .how-loop-step:nth-child({j + 1})::before" for s in range(frm, N))
        out.append(f"    {sel} {{ opacity: 1; }}")
    out += [
        "    /* The check stage's three states (0: the problems, 1: the fix, 2: the check passes). */",
        "    .slip, .term-loop { transition: opacity 0.4s ease, transform 0.6s cubic-bezier(0.2, 0.8, 0.2, 1); }",
        "    .how-track[data-sub='0'] .slip-2, .how-track[data-sub='0'] .slip-3, .how-track[data-sub='1'] .slip-3 { opacity: 0; }",
        f"    .how-track[data-sub='1'] .term-loop {{ transform: translate3d(0, {SCROLL[0]}, 0); }}",
        f"    .how-track[data-sub='2'] .term-loop {{ transform: translate3d(0, {SCROLL[1]}, 0); }}",
        "    .how-track[data-sub='2'] .slip-1 { opacity: 0.4; }",
        "  }",
        "}",
        "",
    ]
    # One panel leaves before the next comes: no two are on screen at once.
    shown = "opacity: 1; transform: none;"
    before = "opacity: 0; transform: translate3d(0, 1.5rem, 0) scale(0.97);"
    after = "opacity: 0; transform: translate3d(0, -1.5rem, 0) scale(0.98);"
    for k in range(N):
        a, b = window(k)
        first, last = k == 0, k == N - 1
        stops = [f"0%, {pct(b - 2.6)} {{ {shown} }}"] if first else [f"0%, {pct(a + 0.2)} {{ {before} }}"]
        if not first:
            stops.append(f"{pct(a + 2.6)}, {'100%' if last else pct(b - 2.6)} {{ {shown} }}")
        if not last:
            stops.append(f"{pct(b - 0.2)}, 100% {{ {after} }}")
        out.append(f"@keyframes how-stage-{k} {{\n  " + "\n  ".join(stops) + "\n}")
        on = ["0% { opacity: 1; }"] if first else [f"0%, {pct(a - 1)} {{ opacity: 0; }}"]
        on.append(f"{pct(a + 1)}, {'100%' if last else pct(b - 1)} {{ opacity: 1; }}")
        if not last:
            on.append(f"{pct(b + 1)}, 100% {{ opacity: 0; }}")
        out.append(f"@keyframes how-on-{k} {{ " + " ".join(on) + " }")
        out.append(f"@keyframes how-words-{k} {{ " + " ".join(s.replace("opacity: 0;", "opacity: 0.55;") for s in on) + " }")
    for frm in sorted(set(LOOP)):
        a, _ = window(frm)
        out.append(f"@keyframes how-loop-{frm} {{ 0%, {pct(a - 1)} {{ opacity: 0; }} {pct(a + 1)}, 100% {{ opacity: 1; }} }}")
    t1, t2 = a4 + third, a4 + 2 * third
    out += [
        f"@keyframes how-loop-{CHECK}b {{ 0%, {pct(t1 - 1)} {{ opacity: 0; }} {pct(t1 + 1)}, 100% {{ opacity: 1; }} }}",
        "@keyframes how-scroll {",
        f"  0%, {pct(t1 - 1)} {{ transform: none; }}",
        f"  {pct(t1 + 1)}, {pct(t2 - 1)} {{ transform: translate3d(0, {SCROLL[0]}, 0); }}",
        f"  {pct(t2 + 1)}, 100% {{ transform: translate3d(0, {SCROLL[1]}, 0); }}",
        "}",
        f"@keyframes how-slip-1 {{ 0%, {pct(t2 - 1)} {{ opacity: 1; }} {pct(t2 + 1)}, 100% {{ opacity: 0.4; }} }}",
        "@keyframes how-slip-2 {",
        f"  0%, {pct(t1 - 1)} {{ opacity: 0; transform: translate3d(0, 0.75rem, 0); }}",
        f"  {pct(t1 + 1)}, 100% {{ opacity: 1; transform: none; }}",
        "}",
        "@keyframes how-slip-3 {",
        f"  0%, {pct(t2 - 1)} {{ opacity: 0; transform: translate3d(0, 0.75rem, 0); }}",
        f"  {pct(t2 + 1)}, 100% {{ opacity: 1; transform: none; }}",
        "}",
        "@keyframes how-mark { from { opacity: 0; transform: scale(0.3); } to { opacity: 1; transform: none; } }",
        "@keyframes how-rail { from { transform: scaleY(0.02); } to { transform: scaleY(1); } }",
        "@keyframes how-depth { from { transform: translate3d(0, 6%, 0); } to { transform: translate3d(0, -6%, 0); } }",
        "",
        "/* The fallback's progress (how-scene.ts sets it on the rail's fill): not inherited. */",
        "@property --how-p { syntax: '<number>'; inherits: false; initial-value: 1; }",
    ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    OUT.write_text(css())
    sys.stdout.write(f"wrote {OUT}\n")
