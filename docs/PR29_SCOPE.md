# PR29 scope

Frontend-only operational parity follow-up.

Included: ADMIN automation controls backed by existing protected endpoints; explicit simulation/live-money safety copy; clearer watchdog architecture wording; correction of legacy IBKR Windows/TWS architecture labels; frontend regression tests and acceptance documentation.

Excluded: live-trading enablement, risk-policy changes, broker execution logic changes, database migrations, Docker/systemd controls, Gateway restart controls, watchdog mutation, credential handling changes.
