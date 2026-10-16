`Pipeline(services={name: service})` names the service that a claim name stands for: a
long-lived helper such as a worker service, a database or a local server. A `Service`
is a function of the name that returns a context manager. The first task that claims
the name starts the service, and every task that claims it shares it while it runs, as
many at once as its claim capacity lets. The run's end stops it, also on an error, on
Ctrl-C and on SIGTERM. `service_idle_s=` stops a service that no task holds and starts
it again for the next claim. A task reaches the service by the address its start gives:
`contraagent.service_address(name)` in a Python task, `CONTRAAGENT_SERVICE_<NAME>` in
an agent task's environment. A start that raises fails the tasks that claim the name
with stop `launch_failed`. `services.jsonl` records each start and stop, the monitor
shows them under "Services" (`Plan.services`, `ServiceSpan`), and `Pipeline.check`
names a service that no task claims.
