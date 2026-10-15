"""The sums the monitor's views share: tokens, and what agent sessions spent per model.

A run's row in the runs list (`Monitor.runs`), its plan (`Monitor.plan`) and the trends of
a period (`trends.digest`, `trends.aggregate`) add up the same journal fields; each sum is
defined here once, over journal rows as dicts (a row a domain's own code wrote may hold
anything, so every value is checked).

* `TOKENS`: the token counts that add up (`TokenUsage`'s counts, in its order); `PEAKS`:
  those whose largest counts (`peak_context`, `context_window`).
* `number`: a JSON number as a float, else None.
* `token_counts`: a journal `usage` as the counts and peaks it holds; `add_tokens`: a
  `usage` added to running counts.
* `model_usage`: what journal rows' hops spent per model (`api.ModelUsage`);
  `add_model_usage`: one such sum added to others.
"""

from __future__ import annotations

from collections.abc import Mapping

from contraagent.dispatch.records import TokenUsage

#: The token counts of a `TokenUsage` that add up, in its order.
TOKENS: tuple[str, ...] = tuple(name for name, f in TokenUsage.model_fields.items() if f.annotation is int)
#: The fields of a `TokenUsage` (and an `api.ModelUsage`) whose largest counts.
PEAKS: tuple[str, ...] = ("peak_context", "context_window")


def number(v: object) -> float | None:
    """`v` as a float when it is a JSON number (not a bool), else None."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def token_counts(usage: object) -> dict[str, int] | None:
    """A journal `usage` (`TokenUsage`) as the counts and peaks it holds, as ints; None for no usage."""
    if not isinstance(usage, Mapping):
        return None
    return {k: int(n) for k in (*TOKENS, *PEAKS) if (n := number(usage.get(k))) is not None}


def add_tokens(into: dict[str, int], usage: object) -> None:
    """Add the counts of a journal `usage` to `into` (`TOKENS` keys)."""
    if isinstance(usage, Mapping):
        for k in TOKENS:
            into[k] += int(number(usage.get(k)) or 0)


def add_model_usage(models: dict[tuple[str, str], dict], m: Mapping) -> None:
    """Add one sum of spend on a model (an `api.ModelUsage` as a dict) to `models`, by agent
    and model, in order of first use: counts and time add up (cost rounded to 6 places,
    time to 1), peaks take the largest."""
    into = models.get((m["agent"], m["model"]))
    if into is None:
        models[(m["agent"], m["model"])] = dict(m)
        return
    for f, v in m.items():
        if f in ("agent", "model") or v is None:
            continue
        if f == "cost_usd":
            into[f] = round((into[f] or 0.0) + v, 6)
        elif f in PEAKS:
            into[f] = max(into.get(f) or 0, v)
        elif f == "wall_s":
            into[f] = round(into[f] + v, 1)
        else:
            into[f] += v


def _spent(agent: str, model: str, usage: object, cost: float | None, sessions: int, wall_s: float) -> dict:
    """One hop's spend on one model, as an `api.ModelUsage` dict."""
    u = usage if isinstance(usage, Mapping) else {}
    peaks = {k: v if isinstance(v := u.get(k), int) and not isinstance(v, bool) else None for k in PEAKS}
    return {
        "agent": agent,
        "model": model,
        "sessions": sessions,
        **{k: int(number(u.get(k)) or 0) for k in TOKENS},
        "cost_usd": round(cost, 6) if cost is not None else None,
        "wall_s": round(wall_s, 1),
        **peaks,
    }


def model_usage(rows: list[dict]) -> list[dict]:
    """What the agent sessions of journal `rows` spent per model (`api.ModelUsage`), in order
    of first use: each hop on its own model (its agent, tokens, cost and time), and what it
    spent on other models (`Hop.other_models`) on each of them, taken out of its own model's
    cost. A row of one hop with no tokens of its own gives the hop the row's. `peak_context`
    and `context_window` are the largest of its hops'. Python rows and hops that never launched (`skipped_hops`)
    are not counted."""
    out: dict[tuple[str, str], dict] = {}
    for row in rows:
        if row.get("executor") == "python":
            continue
        hops = [h for h in row.get("hops") or [] if isinstance(h, dict)]
        for h in hops:
            agent, model = str(h.get("agent") or row.get("agent") or ""), str(h.get("model") or "")
            if not model:
                continue
            usage = h.get("usage") if isinstance(h.get("usage"), dict) else (row.get("usage") if len(hops) == 1 else None)
            cost = number(h.get("cost_usd"))
            given = h.get("other_models")
            others = {str(n): spent for n, spent in given.items() if isinstance(spent, dict)} if isinstance(given, dict) else {}
            parts = [p for spent in others.values() if (p := number(spent.get("cost_usd"))) is not None]
            own = max(0.0, cost - sum(parts)) if cost is not None else None
            add_model_usage(out, _spent(agent, model, usage, own, 1, number(h.get("wall_s")) or 0.0))
            for name, spent in others.items():
                add_model_usage(out, _spent(agent, name, spent, number(spent.get("cost_usd")), 0, 0.0))
    return list(out.values())
