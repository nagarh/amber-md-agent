Run `python md_agent.py squeue` to show all currently running or pending SLURM jobs for this user.

Then run `python md_agent.py sacct` to show recently completed jobs with their exit codes.

Present the results in a clean summary: what is running, what finished, and whether any jobs exited with an error. Keep it brief — no file reading, no interpretation beyond pass/fail exit codes.
