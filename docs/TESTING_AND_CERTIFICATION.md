# ATLAS MARKETS — Testing and Certification

## Baseline

Current known automated-test baseline:

```text
55 passed, 1 warning
```

Run from the local project directory:

```powershell
docker compose exec app python -m pytest
```

## Provider connectivity verification

```powershell
docker compose exec app python -m app.scripts.verify_integrations
```

A recent fully connected result included:

```text
PASS | MT5 DEMO: CONNECTED | login=448261 ... algo=ON
PASS | BYBIT TESTNET: CONNECTED | equity=1213.97 ...
PASS | IBKR PAPER: CONNECTED | account=DUR980544 equity=1000000.00 ... simulation=True
PASS | TWELVE_DATA: CONNECTED (market data only)
```

Connectivity PASS does not by itself mean execution is certified.

## Fusion MT5 execution certification

Command:

```powershell
docker compose exec app python -m app.scripts.certify_mt5_execution
```

Latest successful certification:

```text
CERTIFY | MT5 DEMO | login=448261 server=FusionMarkets-Demo equity=9987.63
PREFLIGHT| retcode=0 comment=Done
ORDER   | EURUSD BUY Market volume=0.01
OPEN    | retcode=10009 order=520344397 deal=363392725
POSITION| ticket=520344397 symbol=EURUSD volume=0.01 price_open=1.16746
CLOSE   | retcode=10009 order=520344398 deal=363392726
WARN    | execution confirmed but /history/deals has not exposed deals 363392725,363392726 yet; rows=34
PASS    | MT5 DEMO EXECUTION CERTIFIED | ticket=520344397 open_deal=363392725 close_deal=363392726 flat=True
```

Interpretation: MT5 Demo execution is certified. Delayed history visibility is a known synchronization behavior and is not considered execution failure when the order/deal and position lifecycle provide authoritative confirmation.

## Bybit Testnet execution certification

Command:

```powershell
docker compose exec app python -m app.scripts.certify_bybit_execution
```

The script:

- refuses non-Testnet/Simulation profiles;
- reads actual Bybit instrument metadata;
- calculates a valid minimum quantity/notional;
- refuses unsafe sizing;
- submits a Testnet order only when safeguards pass;
- attempts to verify/close the certification position.

Current result: the request reached Bybit order creation but Bybit returned `10024` due to a regulatory product/service restriction. Therefore connectivity/private auth/order-path reachability are certified, but execution is provider-blocked.

## IBKR Paper execution certification

Status: **next task**.

Required certification behavior:

- Paper/simulation only;
- validate intended account;
- preflight a small liquid stock/ETF order;
- submit the certification order;
- identify only the new certification position/execution;
- close only that position;
- verify flat state;
- inspect execution history;
- clear PASS/FAIL output;
- refuse Live Money.

## Certification rules

1. Never interpret connectivity alone as execution proof.
2. Never bypass provider or regulatory restrictions.
3. Never disable Live Money gates merely to make a test pass.
4. Certification scripts must avoid touching unrelated existing positions/orders.
5. Use actual provider instrument constraints instead of guessed quantities where possible.
6. Preserve reproducible PASS/FAIL output.
7. After meaningful changes, run the full automated test suite again.
