# Position slots and interrupted scans

Bybit managed quantity dust formerly counted toward max_open_positions forever.
Readiness now checks broker Spot quantity step and minimum for each managed symbol,
once per profile per evaluation. Only a balance confirmed below the normalized minimum
is omitted from the entry slot count. Failed or malformed metadata counts conservatively.
The classification appears in readiness and persisted preflight audit details.

Inventory is never deleted or set to zero. Broker holdings, gross exposure, and same-symbol
duplicate protection remain in place. Minimum-notional-only dust is not excluded by this
release. No consolidation, top-up, liquidation or order is performed by classification.
SELL continues to require actual ATLAS ownership and verified broker execution.

IBKR exits use a separate Paper position manager, not entry readiness. Regression tests
exercise exact owned LONG and SHORT closes through that manager without consulting entry
capacity. Bybit readiness already applies the entry capacity gate only to BUY.
This does not certify protective stop/take-profit behavior or promise an exit signal.

Safe scans and IBKR/MT5 exit scans now record INTERRUPTED when their worker is cancelled,
set a finish time, and propagate cancellation. Previously committed action records remain.
An interrupted scan is not evidence that its orders were cancelled or unfilled; broker
reconciliation is required before any retry. Hard process termination can still leave
RUNNING records. Older records are not automatically relabelled: without an owner/lease,
elapsed time alone cannot prove that another worker stopped. Inspect restart evidence
and broker orders/fills before correcting the specific historical record.

No schema, frontend, budget, risk-limit, provider credential, bridge or live gate changes.
Migration remains 20261001_0022. Preserve the current app image, build and run the full
production-equivalent test suite, then recreate app only. Observe a completed scan,
slot classification, duplicate protection and broker-native exit evidence. Roll back by
retagging the saved image to atlas-markets-app:latest and recreating app.
