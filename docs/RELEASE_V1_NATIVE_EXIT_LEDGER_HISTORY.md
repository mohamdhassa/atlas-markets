# Durable IBKR native protective-exit reporting

Performance now recovers broker execution callbacks from persisted native protective-exit
records when the live Gateway history no longer returns them. It validates the Paper profile,
owner, account, deterministic exit identity, exact entry link, protective order group, execution
IDs, sides, complete quantity, positive prices, timestamps and financial fields before reporting.
Malformed, partial, conflicting or cross-account evidence is excluded; unavailable fees/P&L
stay pending. No broker orders, audit records or statement evidence are changed.

Live callbacks and saved callbacks deduplicate by execution ID within the profile. Available
live financial values take precedence; previously saved values can complete a pending callback.
Each split fill remains separate. Broker net P&L already includes fees and is not recalculated.

The protective audit's exact entry replaces generic same-symbol FIFO context. This restores the
October 12 META 40/22-share stop fills and ties the October 13 63-share close to its own entry,
rather than an older orphan lot. Saved fill-status entry times remain audit recording times
unless reviewed statement execution times are available; durations retain that limitation.
The shared execution-time parser preserves the explicit Gateway timezone from the prior fix.

Validation covers absent/partial live history, split fills, duplicate IDs, updated live fees/P&L,
missing financial values, exact entry context, daily P&L and rejected invalid/scoped evidence.
No migration or frontend layout changes. Deploy only app with the native-protection overlay;
leave Gateway and bridge running. The six unsupported/earlier historical rows remain pending.
