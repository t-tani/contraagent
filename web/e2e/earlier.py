"""An earlier run of the demo's nested `analyse` flow, for the monitor's forecast.

    uv run python web/e2e/earlier.py    # writes demo-runs/analyse-before in the current directory

It runs the flow over four bundles (the demo runs it over three after it), so the
demo's `analyse` run, which starts after this one finished, is expected to have the
fourth bundle's tasks and has not: its forecast shows them.
"""

from contraagent import Overrides, Pipeline
from contraagent.docs.examples.analysis.flow import analyse
from contraagent.docs.examples.demo.run import DemoAgent


def main() -> None:
    pipeline = Pipeline(None, runs_dir="demo-runs", backends={"stub": DemoAgent(pace=0.03)}, overrides=Overrides(agent="stub"))
    pipeline.run(analyse, bundles=["east", "west", "south", "north"], run_id="analyse-before")


if __name__ == "__main__":
    main()
