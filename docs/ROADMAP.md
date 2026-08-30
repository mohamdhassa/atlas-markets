# ATLAS MARKETS — Roadmap

Last updated: 2026-08-30

## Completed foundation

v1.0.0 Simulation Release is complete and tagged. Core architecture, external provider profiles, auth, strategies, risk, automation, MT5 Demo execution, IBKR Paper execution, persistent action history, unified performance, historical/news intelligence and frontend operations are implemented.

## Active v1.1 rollout

### 1. Broad certified simulation AUTO_TRADE

- [x] Add ADMIN bulk eligible AUTO_TRADE endpoint.
- [ ] Deploy locally and pass full tests.
- [ ] Promote all ready MT5 Demo and IBKR Paper starter symbols.
- [ ] Review blocked list and confirm Bybit remains provider-blocked.
- [ ] Run monitored scan and verify broker truth.

### 2. IBKR broad Paper operation

- [x] Paper execution certification.
- [x] WhatIf preflight.
- [x] 1-share cap.
- [x] broker fill/cancel state verification.
- [ ] Enable appropriate real-time U.S. market-data subscriptions for API use.
- [ ] Validate all configured stock/ETF AUTO_TRADE symbols across market hours.

### 3. Bybit resolution

- [x] private diagnostics PASS.
- [x] order request reaches provider.
- [x] identify provider `10024` compliance/product restriction.
- [ ] reproduce product access in Testnet UI.
- [ ] open/complete Bybit support review.
- [ ] controlled order accepted after provider resolution.
- [ ] controlled reduce-only close certification.
- [ ] only then add Bybit to certified automation routes.

### 4. Oracle Cloud deployment

- [x] Oracle compose profile.
- [x] Oracle env template.
- [x] deployment/network/backup runbook.
- [ ] provision/update OCI Ubuntu host.
- [ ] copy production secrets privately.
- [ ] restore application database.
- [ ] configure HTTPS reverse proxy.
- [ ] establish private VPN to broker execution nodes.
- [ ] run Oracle acceptance suite.
- [ ] start continuous observation.

### 5. Multi-week observation

Target: several weeks of stable simulation without constant strategy changes.

Measure:

- total/realized/unrealized P&L;
- maximum drawdown;
- win rate and profit factor;
- average winner/loser;
- provider and symbol performance;
- broker cancellations/rejections;
- risk blocks and duplicate prevention;
- automation uptime;
- broker/ATLAS position consistency;
- verified strategy attribution coverage.

## After observation

Possible v1.2 work is driven by evidence, not by a fixed feature list. Candidate improvements include strategy tuning, richer verified attribution, performance charts, alerting, additional providers and execution-node service hardening.

## Live Money program

Live Money is not part of v1.1. It gets its own certification/release after the observation data is reviewed.

Requirements include:

- provider-specific Live account certification;
- smaller initial risk limits than simulation;
- real-time market data where required;
- operational monitoring/alerts;
- backup/recovery validation;
- explicit rollback/kill procedures;
- legal/provider eligibility checks;
- controlled tiny-size deployment before any scaling.
