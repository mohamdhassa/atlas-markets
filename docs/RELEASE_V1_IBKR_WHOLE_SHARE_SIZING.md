# IBKR whole-share entry sizing

Date: 2026-10-05

Restoring the paper capital basis did not remove fractional blocks: calculated quantities such as
12.7 were still normalized to a fractional step, then rejected by the disabled capability flag.

New entries now round down to whole shares when `IBKR_FRACTIONAL_API_ENABLED=false`: 12.7 becomes
12; 0.99 becomes zero and is blocked as `IBKR_QUANTITY_BELOW_ONE_SHARE`. Fractional certification
continues to use the existing 0.0001 step when enabled. Readiness recalculates notional and applies
available balance and portfolio guards after rounding. Preflight and execution reject stale
fractional requests, preserving the exact approved quantity rather than resizing during submission.

Broker What-If, duplicate position/order checks, Paper-only gates and fill verification remain
mandatory. Existing-position exits still close the broker-authoritative quantity exactly. No
schema, capital override, environment, live-money permission or provider credential changes.
Only the application needs rebuilding/recreating; the bridge and Gateway are unchanged.

Regression coverage exercises whole/fractional sizing, below-one-share rejection, readiness-to-
broker-preflight quantity preservation and stale-request rejection before broker execution.
Run the full production Docker suite before activating the application. A recovered connection
and sufficient budget do not guarantee a signal, broker acceptance or a fill.
