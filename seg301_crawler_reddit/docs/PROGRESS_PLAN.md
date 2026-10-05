### Goal
Show comment progress and periodic status during Reddit crawl commands, including while network calls block.

### Assumptions
- Use existing stdlib logging on stderr, preserving the final JSON on stdout.
- The denominator is the user-supplied maximum; fewer comments may be available.
- Emit status every five seconds during waits, plus updates as valid unique comments are collected.
- Include counts, elapsed time, phase and dry-run labeling; never include cookies, content or author names.

### Plan
1. Define progress behavior with regression tests.
   - Files: `tests/test_progress.py`
   - Change: Cover reporting during a blocked transport, correct saved counts with duplicates/deletions, dry-run labeling and worker cleanup after errors/interruption.
   - Verify: `python3 -W error::ResourceWarning -m unittest discover -s tests -p test_progress.py -v` fails before implementation.
2. Add progress reporting to crawl commands.
   - Files: `reddit_crawler.py`
   - Change: Add a managed status worker; update stages around database setup, listing, JSON retrieval and storing comments. Stop and join the worker on every exit.
   - Verify: `python3 -W error::ResourceWarning -m unittest discover -s tests -v`; `python3 -m compileall -q reddit_crawler.py tests`.
3. Document running and saving progress logs.
   - Files: `README.md`, `IMPLEMENTATION_PLAN.md`
   - Change: Show a 50-comment command and stderr capture with tee; explain heartbeat, count semantics and no live verification.
   - Verify: Offline CLI smoke with mocked HTTP; compare documented output with actual logs.

### Risks & mitigations
- Background status must not touch SQLite or HTTP state: read only a locked snapshot of counters/phase.
- Cleanup must not leave a worker printing after completion: signal Event and join in context-manager exit.
- Waiting messages indicate the program remains active, not that Reddit is delivering data.

### Rollback plan
Remove the progress context and callbacks; data schema and collection behavior remain compatible.

### Verification results
- Added five progress tests; the initial targeted run failed because the progress implementation did not yet exist.
- All 60 offline tests passed after implementation, with ResourceWarning treated as an error; Python compilation passed.
- A transport test waits for a periodic status event before returning an error, confirming the worker reports while the HTTP call is blocked. No arbitrary sleep is needed in this test.
- CLI smoke in the suite confirms automatic progress on stderr, valid JSON on stdout, dry-run counts and no worker remaining after completion.
- Tests cover unique saved counts, partial completion, error cleanup and KeyboardInterrupt. Live Reddit access is unchanged and remains unverified.
