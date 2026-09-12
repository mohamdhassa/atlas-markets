# PR29 test plan

1. Build the branch in an isolated worktree/container.
2. Run `python -m pytest -q` and require no failures.
3. Do not change live-trading gates.
4. After merge, rebase the production checkout onto origin/main so the production-only IBKR validation commit is preserved.
5. Rebuild only the ATLAS app service.
6. Confirm app, Postgres and Redis health; confirm IBKR bridge remains connected and simulation=true.
7. In an ADMIN browser session verify Operations shows admin controls and current state. Use Scan now as the first non-destructive action and confirm scan history refreshes.
8. Verify the kill/restart controls render correctly but do not activate the kill switch merely for testing unless operationally desired.
9. Verify a USER session does not receive ADMIN controls.
10. Verify Integration Center displays the Oracle Linux / bridge 8766 / Gateway 4002 architecture wording.
11. Verify desktop and mobile layouts.
