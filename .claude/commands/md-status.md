Give a full situational report of the current MD project. Follow these steps in order:

1. **Jobs**: Run `python md_agent.py squeue` and `python md_agent.py sacct`. Report what is running, queued, and recently completed.

2. **Output check**: For any jobs that completed since the last run, find their output files (mdout, log, .out/.err SLURM files) and read them to confirm success or identify failure. Use `python md_agent.py ls <dir>` to find relevant files and `python md_agent.py read <file>` to check them. Look for the mandatory success signals defined in CLAUDE.md (e.g. final NSTEP reached, Errors = 0, cpptraj Done).

3. **Project state**: Based on what files exist across the project directory, summarize what stage each active simulation is at. Which steps are done, which are running, which haven't started yet.

4. **Flags**: Call out anything that needs attention — failed steps, jobs that ended early, suspicious output (NaN energies, density off, SHAKE failures).

5. **Next action**: End with one clear recommended next step. If everything is running fine and nothing needs attention, say so explicitly.

Be concise. Use a structured format so the user can scan quickly.
