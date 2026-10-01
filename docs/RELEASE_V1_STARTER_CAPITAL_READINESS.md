# Release — v1 starter-capital readiness

## Delivered

- Each Paper/Testnet/Demo account accepts an optional simulation-capital override.
- A $100 override produces $100-sized validation while percentage controls remain authoritative.
- Clearing the override returns sizing to actual broker equity without a code change.
- Live accounts always size from broker equity and never use the simulation override.
- IBKR orders requiring fractional shares are explicitly blocked until that route is certified.
- The readiness response exposes the complete starter policy for UI and operational inspection.

## Verification

The change includes unit coverage for simulation sizing, scalable broker-equity sizing, live
override exclusion and available-balance capping. Production-equivalent container tests and
deployment verification remain required before merging or deployment.
