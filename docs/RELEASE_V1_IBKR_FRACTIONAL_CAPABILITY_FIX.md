# IBKR fractional capability fix

Date: 2026-10-03

Production evidence showed that IBKR Paper rejected a risk-sized MSFT quantity of `0.0386` with
error `10243`: fractional-sized orders cannot be placed through the active API route.

This release:

- defaults `IBKR_FRACTIONAL_API_ENABLED` to `false`;
- blocks unsupported fractional quantities before broker What-If;
- records `IBKR_FRACTIONAL_API_UNSUPPORTED` instead of a generic preflight rejection;
- preserves eligible whole-share execution;
- never rounds a fractional quantity up or weakens the USD 100 capital ceiling; and
- documents the certification required before fractional execution can be enabled.

No schema migration or production data change is required.
