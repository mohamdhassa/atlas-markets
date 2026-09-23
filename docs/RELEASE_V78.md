# ATLAS MARKETS — v78 Release Notes

Date: 2026-09-23

## Purpose

v78 aligns release-readiness APIs and operational documentation with the Bybit Testnet/Demo Spot automation delivered in v74–v77. It does not enable Live Money.

## Runtime corrections

- `/release/readiness` reports Bybit simulation as `CERTIFIED_TESTNET_DEMO_SPOT`.
- Bybit readiness is scoped to connected Testnet/Demo profiles.
- Readiness exposes the `ATLAS_MANAGED_INVENTORY_ONLY` SELL policy.
- Readiness documents broker-metadata and available-balance reconciliation.
- Bulk AUTO_TRADE copy now lists Bybit Testnet/Demo Spot as eligible when ready.
- Bybit Live and non-Spot products remain uncertified.

## Safeguards retained

- global kill switch;
- provider/environment certification gates;
- account, strategy and risk preflight;
- persisted ATLAS-managed Spot inventory;
- available-balance cap and exchange-step rounding for Bybit SELL orders;
- per-symbol failure isolation;
- broker-fill verification and action audit trail;
- IBKR Paper maximum one share per automatic order;
- Live Money gate.

## Validation

The v77 production audit completed 216 tests successfully. v78 adds regression coverage ensuring Bybit simulation certification never unlocks Bybit Live execution. Run the complete suite again before deployment.

## Deployment boundary

No database migration is required. Deploy the application image only, preserve production environment/Compose assets, run the full test suite, and verify `/release/readiness`, `/automation/state`, Live Activity, and one monitored scan.
