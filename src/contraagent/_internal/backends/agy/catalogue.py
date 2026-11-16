"""agy's model catalogue and usage report: `agy models` and `agy -p /usage`, read by `AgyBackend`.

`agy models` asks Google for the models the login may use and prints one per line, its id
and its label separated by a tab (`gemini-3.8-flash-high<TAB>Gemini 3.8 Flash (High)`),
after a line that says it is fetching them. `--model` takes such an id, or the id without
its reasoning level together with `--effort` (`gemini-3.8-flash` and `--effort high`), so
both forms are in the catalogue.

`agy -p /usage --output-format json` prints the plan's remaining quota without calling a
model (checked against agy 1.5.9): `command.data.groups`, each with its `buckets`, one per
window (`weekly`, `5h`), with the fraction that remains (`remaining_fraction`) and when it
resets (`reset_time`). A group lists the labels of the models that share its limits in its
`description` (`Models within this group: Gemini 4 Hydrogen, Gemini 3.8 Flash`), or is
named after its one model (`Gemini 4 Argon`). Which groups and windows a plan has differs.
"""

from __future__ import annotations

import json
import re

from contraagent._internal.dispatch.records import QuotaReading, QuotaWindow
from contraagent._internal.runs.times import iso_of, parse_iso

#: The command that lists the models.
ARGS = ("models",)
#: The command that reports the plan's quota.
USAGE_ARGS = ("-p", "/usage", "--output-format", "json")
#: The reasoning levels a model id may end with (`--effort` takes the same words).
LEVELS = ("low", "medium", "high", "xhigh", "max")
_LEVEL_RE = re.compile(rf"-(?:{'|'.join(LEVELS)})$")
#: A label's reasoning level, as `agy models` writes it: `Gemini 3.8 Flash (High)`.
_LABEL_LEVEL_RE = re.compile(r"\s*\([^()]*\)\s*$")
#: What starts the list of a group's models in its description.
_GROUP_MODELS_RE = re.compile(r"models within this group:\s*(.+)", re.IGNORECASE)


def parse_models(stdout: str) -> dict[str, str]:
    """The label of each model id `agy models` lists, in order."""
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        slug, tab, label = line.partition("\t")
        if tab and slug.strip() and " " not in slug.strip():
            out[slug.strip()] = label.strip()
    return out


def base_id(model: str) -> str:
    """A model id without its reasoning level (`gemini-3.8-flash-high` -> `gemini-3.8-flash`)."""
    return _LEVEL_RE.sub("", model)


def model_ids(labels: dict[str, str]) -> list[str]:
    """Every id `--model` takes for the listed models: each id, and the id without its
    reasoning level."""
    out = list(labels)
    for slug in labels:
        base = base_id(slug)
        if base not in out:
            out.append(base)
    return out


def family(label: str) -> str:
    """A model's label without its reasoning level (`Gemini 3.8 Flash (High)` -> `Gemini 3.8 Flash`)."""
    return _LABEL_LEVEL_RE.sub("", label).strip()


def group_models(group: dict) -> list[str]:
    """The labels of the models that share a usage group's limits: those its description
    lists, else the group's own name (a group of one model is named after it)."""
    m = _GROUP_MODELS_RE.search(str(group.get("description") or ""))
    if m:
        return [name.strip() for name in m.group(1).split(",") if name.strip()]
    name = str(group.get("name") or "").strip()
    return [name] if name else []


def window_name(window: str) -> str:
    """A usage bucket's window as a quota reading names it: `weekly` is `seven_day`, a
    five-hour one `five_hour`, another keeps its own name."""
    word = window.lower().replace("-", "_").replace(" ", "_")
    if "week" in word:
        return "seven_day"
    if word in ("five_hour", "5h", "5_hour", "five_hours", "5_hours"):
        return "five_hour"
    return word


def usage_reading(stdout: str, label: str, observed_at: str | None = None) -> QuotaReading | None:
    """The usage of the group that holds the model labelled `label`, from what `agy -p /usage
    --output-format json` printed at `observed_at`; None when the report cannot be read or
    names no such group. `status` is `rejected` when a window has nothing left, else `allowed`."""
    try:
        groups = json.loads(stdout)["command"]["data"]["groups"]
    except (ValueError, KeyError, TypeError):
        return None
    wanted = family(label)
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, dict) or wanted not in group_models(group):
            continue
        windows: dict[str, QuotaWindow] = {}
        spent = False
        for bucket in group.get("buckets") or []:
            left = bucket.get("remaining_fraction") if isinstance(bucket, dict) else None
            if not isinstance(left, (int, float)) or isinstance(left, bool):
                continue
            reset = parse_iso(bucket.get("reset_time"))
            windows[window_name(str(bucket.get("window") or bucket.get("id") or ""))] = QuotaWindow(
                pct=round((1.0 - float(left)) * 100, 1), resets_at=iso_of(reset.timestamp()) if reset is not None else None
            )
            spent = spent or left <= 0
        if not windows:
            return None
        return QuotaReading.from_windows(windows, status="rejected" if spent else "allowed", observed_at=observed_at)
    return None
