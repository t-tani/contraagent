"""Diagnosis: what a run's records say to change in its pipeline, kind by kind
(`contraagent diagnose RUN_DIR`), and what changed since an earlier run of the same
tasks (`--against EARLIER_RUN_DIR`).

It reads a run's journal, launches and contract records through `RunSource`, and
launches nothing. Each **sign** is one pattern in the records of one kind's tasks:

* the outputs that were sent back, one sign per check that sent them: a validator
  (`[name]`), a field of the output model, or the file itself (not written, not JSON);
* the launches stopped at a limit of their budget (`max_turns`, `timeout_s`, ...),
  and the attempts whose peak context came near `context_budget`;
* the tool calls the permissions refused, by tool;
* the refusals and stops of a safety classifier;
* the routes passed over: a launch that ended for its route (a rate limit, a failed
  login) and a hop whose credential rested;
* the attempts that ended in any other stop that is not ok (an error, a Python task
  that raised), also those whose task passed on a later attempt;
* the tasks that cost several times the kind's median (in turns, where the coding
  agent reports no cost).

A sign names its tasks and the change it suggests, with the topic that explains the
change, in the form `contraagent check` uses (`check.POINTER`). It counts tasks, not
attempts or errors: what share of the kind's work shows it.

A comparison pairs the tasks of two runs by key. A task the later run took over from
the earlier one (`Pipeline.run(resume_from=)`) is the same work and is only counted.
For every other pair it gives which parts of the fingerprint changed (the definition,
the params, ...), the tasks that pass now and did not then and the reverse, each run's
counts, and the outputs that differ. Each task ran once in each run, so it reports
counts, not a verdict.
"""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contraagent._internal.execution.schemas import JournalRow
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import parse_rows
from contraagent._internal.runs.source import DirectorySource, RunSource


class DiagnosisError(ValueError):
    """A run directory that cannot be diagnosed: absent, not a run, or of a run format this
    release does not read."""


#: The stops of a launch that a limit of its budget ended, and the key that sets the limit.
LIMITS = {
    "max_turns": "max_turns",
    "timeout": "timeout_s",
    "stalled": "stall_s",
    "budget": "max_budget_usd",
    "context_budget": "context_budget",
}
#: The stops of a launch that its route ended, not the task's work: the next hop takes the task.
ROUTE_STOPS = ("rate_limited", "auth_failed", "api_error", "launch_failed", "credential_mismatch")
#: An attempt's stops that are no sign of their own: it passed, it was taken over or
#: waits for later, or another sign counts it (its output checks, a limit, a route, a
#: safety refusal, refused tool calls).
NOT_STOPS = frozenset(
    {
        "completed",
        "partial",
        "skipped",
        "deferred",
        "cancelled",
        "duplicate_key",
        "invalid_output",
        "refused",
        "denied",
        *LIMITS,
        *ROUTE_STOPS,
    }
)
#: A task costs "several times" the kind's median past this factor; the median of fewer
#: tasks than `OUTLIER_TASKS` says too little to judge one task against it.
OUTLIER_FACTOR = 3.0
OUTLIER_TASKS = 5
#: The keys a line shows of the tasks it names; the rest are counted.
SHOWN_KEYS = 3

CHANGE_VALIDATOR = (
    "state the rule in the role; a rule the agent can check itself is a CommandValidator, which the stop hook "
    "runs before the agent stops (contraagent docs contracts, Checked twice, by the same rules)"
)
CHANGE_FIELD = (
    "say what the field takes, in its description in the output model and in the role (contraagent docs contracts, Output models)"
)
CHANGE_FILE = "say in the role where the agent writes the output and in which form (contraagent docs plugins, Roles)"
CHANGES_AT_LIMIT = {
    "max_turns": "raise max_turns, let the session go on (max_continuations), or split the work into smaller tasks "
    "(contraagent docs routing, Budgets)",
    "timeout": "raise timeout_s, split the work into smaller tasks, or keep what the launch wrote (partial_on) "
    "(contraagent docs contracts, A launch stopped for its time)",
    "stalled": "read the transcript where the agent stopped answering; raise stall_s for work that is slow to answer, "
    "or keep what the launch wrote (partial_on) (contraagent docs contracts, A launch stopped for its time)",
    "budget": "raise max_budget_usd, or split the work into smaller tasks (contraagent docs routing, Budgets)",
    "context_budget": "give the large inputs as input files, which the agent reads in parts, or split the work "
    "(contraagent docs tasks, Large inputs: input files)",
}
CHANGE_DENIED = (
    "allow the tool in the plugin, or change the role so the work does not need it (contraagent docs plugins, Tools a task may use)"
)
CHANGE_SAFETY = (
    "read the transcript; state the purpose of the work in the role, or let the kind move a refused task to "
    "another route (contraagent docs security, A refused task and its failover chain)"
)
CHANGE_ROUTE = "the cause is in the routes and credentials, not in the flow or the plugin (contraagent docs routing, Failover)"
CHANGE_REST = "the credential was past its quota cap: another credential, or a later start (contraagent docs routing, Quota caps)"
CHANGE_STOP = "read the reason and the transcript of the attempt (contraagent docs tasks, How a task ends)"
CHANGE_RAISED = "fix the function, or the input of its unit (contraagent docs tasks, Python tasks)"
CHANGE_OUTLIER = "read their transcripts: their units may hold more work than the role expects (contraagent docs monitor)"

#: Where a sign's text takes its count of tasks (`2 of 5 tasks`).
_OF = "\x00"


@dataclass(frozen=True)
class Sign:
    """One pattern in the records of one kind's tasks: what it is (`what`), the tasks that
    show it (`keys`, in the order of the journal), and the change it suggests with the
    topic that explains it (`change`)."""

    what: str
    keys: tuple[str, ...]
    change: str
    #: The transcript of the first of `keys` that has one, relative to the run directory; '' when none does.
    transcript: str = ""


@dataclass
class KindDiagnosis:
    """One kind's tasks in a run: how they ended, what they cost, and the signs."""

    kind: str
    tasks: int = 0
    passed: int = 0
    partial: int = 0
    failed: int = 0
    deferred: int = 0
    cancelled: int = 0
    #: What the coding agent reported the tasks' attempts cost, in USD; None when none reported one.
    cost_usd: float | None = None
    signs: list[Sign] = field(default_factory=list)


@dataclass
class KindChange:
    """One kind's tasks in both runs of a comparison (`tasks` pairs; those taken over are
    not among them): the fingerprint parts that changed, each with its number of pairs; the
    tasks that pass now and did not then (`passing`) and the reverse (`failing`); each run's
    counts as `(earlier, later)`, cost and median turns only when both runs know them; and
    of the pairs that passed in both (`outputs_compared`), those whose output differs."""

    kind: str
    tasks: int = 0
    parts: dict[str, int] = field(default_factory=dict)
    passing: list[str] = field(default_factory=list)
    failing: list[str] = field(default_factory=list)
    passed: tuple[int, int] = (0, 0)
    sent_back: tuple[int, int] = (0, 0)
    cost_usd: tuple[float, float] | None = None
    turns: tuple[float, float] | None = None
    outputs_compared: int = 0
    outputs_differ: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(
            (
                self.parts,
                self.passing,
                self.failing,
                self.outputs_differ,
                self.passed[0] != self.passed[1],
                self.sent_back[0] != self.sent_back[1],
            )
        )


@dataclass
class Comparison:
    """A run against an earlier one (`diagnose(against=)`): how many of its tasks it took
    over from that run (`taken_over`), and per kind the tasks of both runs (`kinds`);
    `flow`, the earlier run's flow when it is not the later run's."""

    earlier: str
    taken_over: int = 0
    kinds: dict[str, KindChange] = field(default_factory=dict)
    flow: str = ""


@dataclass
class Diagnosis:
    """What `diagnose` found in a run: each kind's tasks and signs, in the order the
    journal first names the kind. `ok` when no kind shows a sign."""

    run: str
    #: The run's directory, as it was given: the transcripts' paths start with it.
    run_dir: str = ""
    kinds: dict[str, KindDiagnosis] = field(default_factory=dict)
    #: Tasks the run took over from the run it resumes from (stop `skipped`): not diagnosed.
    taken_over: int = 0
    #: The run it resumes from (`run.json` `resumed_from`); '' when none.
    resumed_from: str = ""
    #: Whether `run.json` records the run's end.
    finished: bool = True
    #: Tasks the flow created that have no journal row yet.
    unfinished: int = 0
    against: Comparison | None = None

    @property
    def ok(self) -> bool:
        return not any(k.signs for k in self.kinds.values())

    def __str__(self) -> str:
        return "\n".join(_lines(self))


# --- reading ---------------------------------------------------------------


@dataclass
class _Task:
    """A task's records in one run: its attempts (no `skipped` row among them), whether the
    run took it over, and its launches (`launches.jsonl` rows, by `label`)."""

    key: str
    kind: str
    attempts: list[JournalRow] = field(default_factory=list)
    taken_over: bool = False
    launches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def last(self) -> JournalRow | None:
        return self.attempts[-1] if self.attempts else None

    @property
    def agent(self) -> bool:
        return bool(self.attempts) and self.attempts[0].executor == "agent"

    @property
    def passed(self) -> bool:
        last = self.last
        return last is not None and last.ok and last.stop != "partial"

    @property
    def outcome(self) -> str:
        """`passed`, `partial`, `deferred`, `cancelled` or `failed`."""
        last = self.last
        if last is None:
            return "failed"
        if last.stop in ("partial", "deferred", "cancelled"):
            return last.stop
        return "passed" if last.ok else "failed"

    @property
    def cost_usd(self) -> float | None:
        """The cost of its attempts; None when one of them reported none."""
        costs = [row.cost_usd for row in self.attempts]
        return sum(c for c in costs if c is not None) if costs and None not in costs else None

    @property
    def turns(self) -> int | None:
        """The turns of its launches; None when one could not be counted, or it made none."""
        turns = [hop.num_turns for row in self.attempts for hop in row.hops]
        return sum(t for t in turns if t is not None) if turns and None not in turns else None

    @property
    def sent_back(self) -> bool:
        return any(_sent_back(row) for row in self.attempts)


@dataclass
class _Run:
    name: str
    source: RunSource
    info: dict[str, Any]
    tasks: dict[str, _Task]
    planned: set[str]


def _open(run_dir: str | Path) -> _Run:
    path = Path(run_dir)
    if not path.is_dir():
        raise DiagnosisError(f"{path.as_posix()}: no such directory")
    source = DirectorySource(path.resolve().parent)
    name = path.resolve().name
    info = source.info(name)
    if info is None:
        raise DiagnosisError(f"{path.as_posix()}: holds no {layout.RUN_INFO}, so it is no run directory")
    if layout.format_of(info) not in layout.FORMATS:
        raise DiagnosisError(f"{path.as_posix()}: run format {info.get('format')!r}, which this release does not read")
    tasks: dict[str, _Task] = {}
    for raw in parse_rows(source.lines(name, layout.JOURNAL)[0]):
        try:
            row = JournalRow.model_validate(raw)
        except ValidationError:
            continue  # a row a pipeline's own code wrote in another shape
        task = tasks.setdefault(row.key, _Task(row.key, row.kind))
        if row.stop == "skipped":
            task.taken_over = not task.attempts
        else:
            task.attempts.append(row)
            task.taken_over = False
    for raw in parse_rows(source.lines(name, layout.LAUNCHES)[0]):
        task = tasks.get(str(raw.get("label", "")))
        if task is not None:
            task.launches.append(raw)
    planned = {str(raw.get("key") or "") for raw in parse_rows(source.lines(name, layout.PLAN)[0])} - {""}
    return _Run(name, source, info, tasks, planned)


# --- signs -----------------------------------------------------------------


#: A schema error's place in the document (`items.3.address`): its indices, made `*`.
_INDEX = re.compile(r"(?<=\.)\d+(?=\.|$)|^\d+(?=\.|$)")
#: The value a schema error quotes (`(got: ...)`), which differs from unit to unit.
_GOT = re.compile(r" \(got: .*\)$")
#: A validator's error: `[name] message`.
_VALIDATOR = re.compile(r"^\[([^\]]+)\] ")
#: The line of a rows file an error names (`line 3: `).
_LINE = re.compile(r"^line \d+: ")


def _check_of(error: str) -> tuple[str, str, str]:
    """What sent an output back, from one line of its errors (`path: [name] message`,
    `path: loc: message`, `path: line 3: loc: message`, `path: file was not written`): the
    sign's label, the change it suggests, and the message without the output's path."""
    head, sep, rest = error.partition(": ")
    message = rest if sep and ("/" in head or "\\" in head or "." in head) else error
    if m := _VALIDATOR.match(message):
        return f"[{m.group(1)}]", CHANGE_VALIDATOR, message[m.end() :]
    place = _LINE.sub("", message)
    loc, sep, _ = place.partition(": ")
    if sep and loc and " " not in loc:
        where = "the output as a whole" if loc == "<root>" else f"the field {_INDEX.sub('*', loc)}"
        return where, CHANGE_FIELD, _GOT.sub("", message)
    return message.split(": ", 1)[0], CHANGE_FILE, message


def _sent_back(row: JournalRow) -> list[list[str]]:
    """The errors each correction of an attempt sent back: every objection of the stop hook,
    and the errors of each correction round (`round_errors` holds one more list after an
    attempt that failed its checks for good, or whose last launch failed)."""
    rounds = (row.rounds or 1) - 1 - row.continuations
    return [*row.hook_errors, *row.round_errors[: max(rounds, 0)]]


def _shown(keys: Sequence[str]) -> str:
    more = len(keys) - SHOWN_KEYS
    return ", ".join(keys[:SHOWN_KEYS]) + (f" and {more} more" if more > 0 else "")


def _of(n: int, total: int) -> str:
    return f"{n} of {total} task{'' if total == 1 else 's'}"


def _quoted(text: str, width: int = 160) -> str:
    text = " ".join(text.split())
    return f'"{text[:width]}{"…" if len(text) > width else ""}"'


class _Signs:
    """The signs of one kind, collected task by task. A sign is told apart by its label and
    the change it suggests; its text is the one its first task gave, with `_OF` where its
    count goes. A check's sign also counts the tasks whose last attempt it still failed
    after every correction (`ended`)."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.keys: dict[tuple[str, str], list[str]] = {}
        self.texts: dict[tuple[str, str], str] = {}
        self.ended: dict[tuple[str, str], set[str]] = {}

    def add(self, label: str, change: str, key: str, text: str, ended: bool = False) -> None:
        keys = self.keys.setdefault((label, change), [])
        if key not in keys:
            keys.append(key)
        self.texts.setdefault((label, change), text)
        if ended:
            self.ended.setdefault((label, change), set()).add(key)

    def signs(self) -> list[Sign]:
        out = []
        for at, keys in self.keys.items():
            what = self.texts[at].replace(_OF, _of(len(keys), self.total))
            if ended := len(self.ended.get(at, ())):
                what += f"; {ended} of them still did not pass it after every correction"
            out.append(Sign(what, tuple(keys), at[1]))
        return sorted(out, key=lambda s: -len(s.keys))


def _kind_signs(tasks: list[_Task]) -> list[Sign]:
    found = _Signs(len(tasks))
    for task in tasks:
        for row in task.attempts:
            _checks(task.key, row, found)
            _launches(task.key, row, found)
            _stops(task.key, row, found)
        _denials(task, found)
    return found.signs() + _outliers(tasks)


def _checks(key: str, row: JournalRow, found: _Signs) -> None:
    """The checks an attempt's outputs did not pass: those its corrections sent back, and
    after `invalid_output` those it still did not pass at its end (also with no correction
    allowed, `max_corrections` 0)."""
    still = row.round_errors[-1] if row.stop == "invalid_output" and row.round_errors else []
    for error, ended in [*((e, False) for errors in _sent_back(row) for e in errors), *((e, True) for e in still)]:
        label, change, message = _check_of(error)
        found.add(label, change, key, f"an output did not pass {label} in {_OF}: {_quoted(message)}", ended=ended)


def _launches(key: str, row: JournalRow, found: _Signs) -> None:
    for hop in row.hops:
        if hop.stop in LIMITS:
            cap = {"max_turns": hop.max_turns, "timeout": hop.timeout_s}.get(hop.stop)
            limit = LIMITS[hop.stop] + (f" ({cap:g})" if cap is not None else "")
            text = f"a launch stopped as stalled ({limit}) in {_OF}" if hop.stop == "stalled" else f"a launch reached its {limit} in {_OF}"
            found.add(hop.stop, CHANGES_AT_LIMIT[hop.stop], key, text)
        elif hop.stop in ROUTE_STOPS:
            found.add(f"{hop.stop} on {hop.route}", CHANGE_ROUTE, key, f"a launch ended {hop.stop} on {hop.route} in {_OF}")
        elif hop.stop == "refused":
            found.add("refused", CHANGE_SAFETY, key, f"a launch refused by a safety classifier in {_OF}")
        elif hop.stop == "denied":
            found.add("denied", CHANGE_DENIED, key, f"a launch ended for its refused tool calls in {_OF}")
    for skipped in row.skipped_hops:
        change = CHANGE_ROUTE if skipped.stop else CHANGE_REST
        found.add(f"{skipped.route} passed over", change, key, f"{skipped.route} passed over while {skipped.credential} rested in {_OF}")
    if row.safety_stops:
        found.add("safety stop", CHANGE_SAFETY, key, f"part of a launch stopped by a safety classifier in {_OF}")
    if row.context_warned and not any(hop.stop == "context_budget" for hop in row.hops):
        found.add("context_budget", CHANGES_AT_LIMIT["context_budget"], key, f"the peak context came near context_budget in {_OF}")


def _stops(key: str, row: JournalRow, found: _Signs) -> None:
    if row.ok or row.stop in NOT_STOPS:
        return
    reason = f": {_quoted(row.reason)}" if row.reason else ""
    if row.executor == "python" and row.stop == "error":
        found.add("raised", CHANGE_RAISED, key, f"the function raised in {_OF}{reason}")
    else:
        found.add(row.stop, CHANGE_STOP, key, f"an attempt ended {row.stop} in {_OF}{reason}")


def _denials(task: _Task, found: _Signs) -> None:
    for launch in task.launches:
        for call in launch.get("denied") or ():
            if isinstance(call, dict):
                tool = str(call.get("tool") or "a tool")
                given = f": {_quoted(str(call['input']))}" if call.get("input") else ""
                found.add(f"{tool} refused", CHANGE_DENIED, task.key, f"calls of {tool} refused in {_OF}{given}")


def _outliers(tasks: list[_Task]) -> list[Sign]:
    """The tasks that cost more than `OUTLIER_FACTOR` times the kind's median: in USD when
    every agent task's attempts reported a cost, else in turns when every one's were counted."""
    agent = [t for t in tasks if t.agent]
    if len(agent) < OUTLIER_TASKS:
        return []
    costs, turns = [t.cost_usd for t in agent], [t.turns for t in agent]
    if None not in costs and any(costs):
        values, unit = [c or 0.0 for c in costs], "cost"
    elif None not in turns and any(turns):
        values, unit = [float(n or 0) for n in turns], "turns"
    else:
        return []
    median = statistics.median(values)
    over = tuple(t.key for t, v in zip(agent, values, strict=True) if v > OUTLIER_FACTOR * median)
    if not over:
        return []
    shown = f"${median:.2f}" if unit == "cost" else f"{median:g}"
    what = f"{unit} over {OUTLIER_FACTOR:g} times the kind's median ({shown}) in {_of(len(over), len(tasks))}"
    return [Sign(what, over, CHANGE_OUTLIER)]


# --- the diagnosis -----------------------------------------------------------


def _with_transcript(run: _Run, sign: Sign) -> Sign:
    for key in sign.keys:
        if run.source.stat(run.name, stream := layout.stream(key)) is not None:
            return replace(sign, transcript=stream)
    return sign


def diagnose(run_dir: str | Path, against: str | Path | None = None) -> Diagnosis:
    """The diagnosis of the run in `run_dir`; with `against`, its comparison with the earlier
    run in that directory. Raises `DiagnosisError` for a directory that is no run of a run
    format this release reads, and for `against` naming the run itself."""
    run = _open(run_dir)
    resumed = run.info.get("resumed_from")
    out = Diagnosis(
        run.name,
        run_dir=Path(run_dir).as_posix(),
        resumed_from=str(resumed.get("run_id") or "") if isinstance(resumed, dict) else "",
        finished=bool(run.info.get("finished_at")),
        unfinished=len(run.planned - set(run.tasks)),
    )
    by_kind: dict[str, list[_Task]] = {}
    for task in run.tasks.values():
        if task.taken_over:
            out.taken_over += 1
        else:
            by_kind.setdefault(task.kind, []).append(task)
    for kind, tasks in by_kind.items():
        outcomes = [t.outcome for t in tasks]
        costs = [row.cost_usd for t in tasks for row in t.attempts if row.cost_usd is not None]
        out.kinds[kind] = KindDiagnosis(
            kind,
            tasks=len(tasks),
            passed=outcomes.count("passed"),
            partial=outcomes.count("partial"),
            failed=outcomes.count("failed"),
            deferred=outcomes.count("deferred"),
            cancelled=outcomes.count("cancelled"),
            cost_usd=sum(costs) if costs else None,
            signs=[_with_transcript(run, sign) for sign in _kind_signs(tasks)],
        )
    if against is not None:
        earlier = _open(against)
        if earlier.source.dir(earlier.name) == run.source.dir(run.name):
            raise DiagnosisError(f"{Path(against).as_posix()}: the run itself, not an earlier one")
        out.against = _compare(run, earlier)
    return out


# --- the comparison ----------------------------------------------------------


def _median_turns(tasks: Iterable[_Task]) -> float | None:
    turns = [t.turns for t in tasks if t.agent]
    if not turns or None in turns:
        return None
    return float(statistics.median(n or 0 for n in turns))


def _total_cost(tasks: Iterable[_Task]) -> float | None:
    costs = [t.cost_usd for t in tasks if t.agent]
    if not costs or None in costs:
        return None
    return sum(c or 0.0 for c in costs)


def _both(values: tuple[float | None, float | None]) -> tuple[float, float] | None:
    return (values[0], values[1]) if values[0] is not None and values[1] is not None else None


def _outputs(run: _Run, key: str) -> dict[str, Any]:
    """The outputs task `key` wrote, by their path under the run directory: a JSON
    document as its value, any other file as its bytes. An output outside the run
    directory is left out: another run may have written it since."""
    text = run.source.document(run.name, layout.task_entry(layout.CONTRACTS, key))
    root = run.source.dir(run.name)
    if text is None or root is None:
        return {}
    try:
        record = json.loads(text)
    except ValueError:
        return {}
    out: dict[str, Any] = {}
    for spec in record.get("outputs") or () if isinstance(record, dict) else ():
        path = spec.get("path") if isinstance(spec, dict) else None
        if not isinstance(path, str):
            continue
        try:
            where = Path(path).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        got = run.source.file(run.name, path)
        if got is None:
            continue
        try:
            out[where] = json.loads(got.data)
        except ValueError:
            out[where] = got.data
    return out


def _compare(run: _Run, earlier: _Run) -> Comparison:
    flow, then = str(run.info.get("flow") or ""), str(earlier.info.get("flow") or "")
    out = Comparison(earlier.name, flow=then if then and flow and then != flow else "")
    pairs: dict[str, list[tuple[_Task, _Task]]] = {}
    for key, task in run.tasks.items():
        before = earlier.tasks.get(key)
        if before is None or not before.attempts:
            continue
        if task.taken_over:
            out.taken_over += 1
        elif task.attempts:
            pairs.setdefault(task.kind, []).append((before, task))
    for kind, both in pairs.items():
        change = KindChange(kind, tasks=len(both))
        for before, after in both:
            a, b = before.last, after.last
            if a is not None and b is not None:
                for part in sorted({*a.fingerprint_parts, *b.fingerprint_parts}):
                    if a.fingerprint_parts.get(part) != b.fingerprint_parts.get(part):
                        change.parts[part] = change.parts.get(part, 0) + 1
            if after.passed and not before.passed:
                change.passing.append(after.key)
            elif before.passed and not after.passed:
                change.failing.append(after.key)
            elif before.passed and after.passed:
                then_out, now_out = _outputs(earlier, before.key), _outputs(run, after.key)
                if then_out or now_out:
                    change.outputs_compared += 1
                    if then_out != now_out:
                        change.outputs_differ.append(after.key)
        befores, afters = [p[0] for p in both], [p[1] for p in both]
        change.passed = (sum(t.passed for t in befores), sum(t.passed for t in afters))
        change.sent_back = (sum(t.sent_back for t in befores), sum(t.sent_back for t in afters))
        change.cost_usd = _both((_total_cost(befores), _total_cost(afters)))
        change.turns = _both((_median_turns(befores), _median_turns(afters)))
        out.kinds[kind] = change
    return out


# --- the text ------------------------------------------------------------------


def _tally(n: int, outcomes: dict[str, int], cost: float | None) -> str:
    """`5 tasks: 4 passed, 1 failed, $0.31`."""
    shown = [f"{v} {o}" for o, v in outcomes.items() if v or o == "passed"]
    if cost is not None:
        shown.append(f"${cost:.2f}")
    return f"{n} task{'' if n == 1 else 's'}: {', '.join(shown)}"


_OUTCOMES = ("passed", "partial", "failed", "deferred", "cancelled")


def _lines(d: Diagnosis) -> list[str]:
    kinds = list(d.kinds.values())
    costs = [k.cost_usd for k in kinds if k.cost_usd is not None]
    outcomes = {o: sum(getattr(k, o) for k in kinds) for o in _OUTCOMES}
    tally = _tally(sum(k.tasks for k in kinds), outcomes, sum(costs) if costs else None)
    head = f"{'✓' if d.ok else '✗'} {d.run}, {len(kinds)} kind{'' if len(kinds) == 1 else 's'}, {tally}"
    if d.taken_over:
        head += f"; {d.taken_over} taken over from {d.resumed_from or 'an earlier run'}"
    if not d.finished:
        head += "; the run has not finished" + (f" ({d.unfinished} tasks have no result yet)" if d.unfinished else "")
    lines = [head]
    quiet = []
    for k in kinds:
        if not k.signs:
            quiet.append(k.kind)
            continue
        lines.append(f"  {k.kind}, {_tally(k.tasks, {o: getattr(k, o) for o in _OUTCOMES}, k.cost_usd)}")
        for sign in k.signs:
            lines += [f"    {sign.what}", f"      tasks: {_shown(sign.keys)}"]
            lines += [f"      transcript: {d.run_dir}/{sign.transcript}"] if sign.transcript else []
            lines += [f"      change: {sign.change}"]
    if quiet:
        lines.append(f"  nothing to change in {', '.join(quiet)}")
    if d.against is not None:
        lines += _comparison_lines(d.against, d.run)
    return lines


def _pair(values: tuple[float, float], form: str) -> str:
    return f"{form.format(values[0])} → {form.format(values[1])}"


def _comparison_lines(c: Comparison, run: str) -> list[str]:
    n = sum(k.tasks for k in c.kinds.values())
    head = f"against {c.earlier}: {n} task{'' if n == 1 else 's'} ran in both runs"
    if c.taken_over:
        head += f", and {run} took over {c.taken_over} from it"
    lines = [head]
    if c.flow:
        lines.append(f"  {c.earlier} ran another flow ({c.flow}): a task of the same key there may be other work")
    quiet = []
    for k in c.kinds.values():
        if not k.changed:
            quiet.append(k.kind)
            continue
        parts = ", ".join(f"{part} in {count}" for part, count in k.parts.items())
        changed = f"changed: {parts}" if parts else "no definition or input changed"
        lines.append(f"  {k.kind}, {k.tasks} task{'' if k.tasks == 1 else 's'}, {changed}")
        figures = [f"passed {_pair(k.passed, '{:g}')}", f"sent back {_pair(k.sent_back, '{:g}')}"]
        if k.cost_usd is not None:
            figures.append(f"cost {_pair(k.cost_usd, '${:.2f}')}")
        if k.turns is not None:
            figures.append(f"median turns {_pair(k.turns, '{:g}')}")
        lines.append(f"    {', '.join(figures)}")
        if k.passing:
            lines.append(f"    passing now: {_shown(k.passing)}")
        if k.failing:
            lines.append(f"    failing now: {_shown(k.failing)}")
        if k.outputs_compared:
            differ = f": {_shown(k.outputs_differ)}" if k.outputs_differ else ""
            lines.append(f"    outputs that differ: {len(k.outputs_differ)} of the {k.outputs_compared} that passed in both{differ}")
    if quiet:
        lines.append(f"  no change in {', '.join(quiet)}")
    lines.append("  each task ran once in each run: a difference in a few tasks can be chance")
    return lines
