# v86 — IBKR half-open session recovery

Date: 2026-09-25

## Root cause

After an IB Gateway daily reset or connection interruption, its API socket can still report connected while account-summary callbacks no longer complete. The previous watchdog trusted `/health` and port `4002`, so this half-open state passed monitoring even though `/account` returned `504 Gateway Timeout`.

## Fix

- Require a successful authenticated paper-account `/account` round trip before declaring IBKR healthy.
- Restart only the dedicated IBKR bridge when the socket is connected but the account probe fails.
- Require both health and account probes after restart before reporting recovery.
- Retry transient network and 502/503/504 failures for safe IBKR GET requests.
- Never automatically retry IBKR POST requests, including order checks, submissions, cancellations or closes.
- Preserve provider-unavailable exception types so ATLAS continues distinguishing outages from trading blockers.

## Boundary

The recovery cannot bypass IBKR login or two-factor authentication. When port `4002` is unavailable, the watchdog reports `IBKR_AUTH_REQUIRED` and leaves the other providers untouched.
