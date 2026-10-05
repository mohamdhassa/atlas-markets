# IBKR outage recovery

IBKR backend disconnections previously left the local socket reporting connected while account,
order and candle requests timed out. The bridge now reports degraded health, rejects requests
promptly during a known outage, interrupts pending reads, and bounds timeout retries with a
per-operation cooldown. Connectivity restoration invalidates account cache and permits a fresh read.
The watchdog preserves the authentication session during a known backend outage.

Portfolio and Dashboard label persisted balances STALE and include their synchronization time.
Unknown holdings are unavailable, not zero. Unified totals include fresh providers only and show
that they are partial. Provider failures do not prevent independent Bybit reporting.

Authentication, ownership, certification, strategy, capital sizing, simulation and execution gates
remain in force. No order placement or cancellation is automatically retried. Backend availability
alone does not authorize an order. This change cannot prevent IBKR outages or authentication prompts.

## Validation

Regression tests cover loss/restoration callbacks, pending-read interruption, exponential cooldowns,
concurrent order reads, watchdog behavior, stale execution rejection, independent provider totals,
and actual frontend rendering for stale and recovered balances. Existing tests cover trading guards.
Run the full container suite with tools mounted before activating the app and bridge.

## Deployment and rollback

Preserve the running application image and copy `tools/ibkr_bridge.py` plus
`ops/ibkr_bridge_watchdog.sh` before pulling. Build and test the app, restart the bind-mounted bridge,
verify its mounted source hash, then recreate only the app and check health. The watchdog script
is read from the checkout on every invocation. No database migration is added.

For rollback, restore the saved bridge/watchdog source, restart the bridge, retag the preserved app
image as `atlas-markets-app:latest`, and recreate the app. An IBKR-only incident does not require
restarting PostgreSQL, Redis or the application. A healthy local socket does not prove backend health.

IBKR connectivity codes: https://interactivebrokers.github.io/tws-api/message_codes.html
