# Live execution lifecycle

ATLAS defaults to simulation. A Live provider profile is not executable merely because credentials exist.

## Required arming conditions

All conditions must be true:

- server policy explicitly permits Live trading;
- authenticated actor is an administrator;
- profile environment is `LIVE`;
- profile is enabled and active;
- credentials are configured;
- provider connection status is `CONNECTED`;
- the specific Live execution route is certified;
- BUY and SELL lifecycle certification both passed;
- the administrator enters the exact account-specific confirmation phrase.

Paper, Demo and Testnet certification never satisfy Live certification.

## Temporary arming

Arming lasts 5–240 minutes and records the actor, reason and expiry. Status evaluation treats expired arming as disabled. The Integrations workspace exposes current blockers, expiry, emergency disarm and audit history.

Disabling or disconnecting an account automatically disarms it. Provider failures and certification failures prevent an armed state from being considered valid.

## Execution boundary

This lifecycle is the control plane. Broker submission code must call the centralized live-execution predicate before any Live order. Routes that have not completed Live certification remain blocked even when simulation execution is certified.
