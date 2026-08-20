# Phase 0 Architecture Decisions

1. Atlas Markets is a separate system from Atlas Trader.
2. Begin as a modular monolith with dedicated worker processes.
3. PostgreSQL is durable system-of-record; Redis is transient fast state.
4. Broker integrations implement a common asynchronous BrokerAdapter.
5. Bybit Demo/Testnet is the first crypto integration.
6. FX provider remains behind the same interface; final provider is selected only after Bahrain/API/demo checks.
7. Every external account maps to one unique `profile_id`.
8. Duplicate credentials are rejected using a non-reversible credential fingerprint.
9. Provider secrets are encrypted at rest.
10. Signal, risk, order, position and configuration decisions are auditable.
11. Core analysis and strategy code is deterministic and reusable by live/demo/backtesting modes.
12. Risk approval is mandatory before execution.
13. Kill Switch and Safe Mode are backend controls.
14. Backtesting includes realistic costs and requires out-of-sample/walk-forward validation.
15. Caddy is the only public production service; application, DB and Redis remain private.
