# v85 — Frontend consolidation

Date: 2026-09-25

## Delivered

- Activated the canonical production workspace after authentication.
- Reduced the runtime from overlapping historical UI layers to six JavaScript and four CSS assets.
- Kept legacy phase assets in the repository as rollback/reference files without executing them.
- Consolidated navigation for dashboard, provider engines, market workspaces, charts, strategies, positions, order/action history, performance, automation, integrations, users and management.
- Added MT5 runtime readiness and explicit blockers to Operations.
- Preserved independent Bybit and IBKR visibility while MT5 awaits its native Windows node.
- Improved mobile navigation, touch-target sizing, table scrolling, sticky headers, focus visibility, reduced-motion behavior and semantic status regions.
- Added regression coverage for the canonical asset boundary, post-login startup, mobile navigation and MT5 readiness presentation.

## Safety

The frontend does not relax any backend execution gate. Live Money remains disabled. Provider status is derived from runtime APIs rather than static text.

## Next gate

Continue provider-specific forward observation and strategy calibration without changing the validation window. Complete native Windows MT5 certification when the AWS account becomes available.
