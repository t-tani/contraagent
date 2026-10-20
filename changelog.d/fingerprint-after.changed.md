A task's fingerprint is what it is given and what it observes: its kind, unit, key, the JSON of its params (an output it was given among them, by its content; a Python task's defaults filled in), its definition, the file an `output_of` task fills in and its outside state (old → new):

- A task it waits for with `after=` stood in its fingerprint by that task's fingerprint → it is no part of it: a task that only waits for another no longer runs again on a resume when the other does. A task that reads what an `after=` task changed in the working tree declares it with `outside_state=`.
- An output it read stood by the content of its output file (`fingerprint_parts` `output:<key>`, `after:<key>`) → it is part of `params`. A task that runs again and writes the same output still leaves the tasks given it skipped.
- A resume ran again every task that waited for a task whose last result was `partial` → the tasks given its output run again when it now writes another output.
- A call that gives a Python task's default and one that leaves it out had two fingerprints → one.
- A run started on 0.6 that 0.7 resumes runs once more each task given an output, waiting for another with `after=`, or with a default filled in (of an agent task's params model, or of a Python task's function). Finish a running run on 0.6 before upgrading.
