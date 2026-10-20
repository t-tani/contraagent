"""Contracts: what an agent task is handed and what it must leave behind.

* `contract`    `OutputContract`/`InputContract`: files checked by pydantic and `validators`;
                `run_until_valid` resumes the session until they hold
* `validators`  `Validator`, `CommandValidator`: checks past the schema
* `pointers`    the parts of a JSON output a task keeps (`agent_task(preserve=)`)
* `calls`       the call file an agent task is handed
* `input_file`  `InputFile`: a file a task is given by its path and the hash of its content
"""
