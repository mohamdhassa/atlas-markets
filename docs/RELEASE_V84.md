# v84 — MT5 runtime readiness

Date: 2026-09-25

## Delivered

- One centrally configured MT5 execution-node client across quotes, validation, scans, preflight, automation, lifecycle and reporting.
- Authenticated application readiness endpoint: `GET /mt5/readiness`.
- Authenticated native-node readiness endpoint with terminal, account, demo, trading and uptime evidence.
- Explicit configuration, reachability, connection, demo-account, algorithmic-trading and bridge-trading blockers.
- Safe transient retries for MT5 read requests only; order POST requests are never automatically retried.
- Correct flat symbol metadata for bid/ask, contract size and broker volume rules.
- Correct MT5 position/order counts during account synchronization.
- Runtime and regression tests that require no live MT5 terminal.
- Installation, security, recovery and certification guidance for the Windows node.

## Boundary

This release completes the software integration but does not claim runtime certification. Certification requires a native Windows host, a logged-in demo terminal, a protected minimum-size demo trade, reconciliation, restart recovery and an observation window. Live Money remains disabled.

## Next gate

Install the native Windows node and execute `docs/MT5_PENDING_EXECUTION_NODE.md`. After recorded certification, proceed to the frontend consolidation phase.
