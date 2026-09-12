# Frontend Operational Parity

ATLAS MARKETS treats a backend operational capability as complete only when its important state is visible and understandable in the frontend and safe role-appropriate actions are available there.

## Operations view

The Operations page exposes automatic scanning state, simulation/execution mode, kill-switch state, scan timing, recent scans, execution/block counts, decisions, blocking reasons, broker order IDs, certified routes, and live IBKR bridge readiness.

ADMIN users additionally receive application-level controls for enabling/disabling automatic scanning, activating the kill switch, restarting automation after a kill, and requesting a scan now. These controls use the existing ADMIN-protected automation API routes.

Infrastructure controls are deliberately excluded. The frontend does not expose arbitrary Docker, systemd, database, Gateway, bridge, or host restart commands. The watchdog label describes deployment architecture only and is not a live systemd-health claim.

Live Money is not enabled by these controls. Existing live-trading gates remain separate.

## IBKR production architecture

The production paper route is ATLAS -> local bridge on port 8766 -> IB Gateway API on port 4002. The Gateway is hosted on the Oracle Linux execution host. Frontend compatibility text corrects legacy Windows/TWS port 7497 wording.

## Acceptance

Before this work is considered complete: run the full automated test suite, deploy the app without disturbing production-only configuration, verify the Operations page as ADMIN and USER, exercise only safe non-destructive controls in simulation, confirm IBKR live readiness, verify recent scans/actions, and inspect desktop/mobile presentation.
