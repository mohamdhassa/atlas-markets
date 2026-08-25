# ATLAS MARKETS — Provider Architecture

## Provider responsibilities

ATLAS MARKETS uses external providers. ATLAS is the analysis, strategy, risk, routing, execution-orchestration and performance layer; it is not itself a broker.

| Provider | Primary market responsibility | Development environment | Live environment |
| --- | --- | --- | --- |
| Interactive Brokers | Stocks and ETFs | Paper | Gated/not certified |
| Fusion MT5 | FX, metals, commodities | Demo | Gated/not certified |
| Bybit | Crypto | Testnet | Gated/not certified |
| Twelve Data | Market/historical data | API | Data only |

## Multi-instrument requirement

Provider certification may use one safe representative instrument, but production architecture must not assume one instrument per provider.

Representative intended routing:

- AAPL/MSFT/NVDA/AMZN/META/TSLA/SPY/QQQ and other supported stocks/ETFs → IBKR
- EURUSD/GBPUSD/USDJPY and other supported FX → Fusion MT5
- XAUUSD/XAGUSD and supported metals → Fusion MT5
- XTIUSD and supported commodities → Fusion MT5
- BTCUSDT/ETHUSDT/SOLUSDT and supported crypto → Bybit when account/provider execution is permitted

ATLAS should validate provider/account capabilities and preferably discover supported instruments rather than trusting hard-coded examples.

## Fusion MT5

MT5 integration uses a Windows-side bridge because MetaTrader connectivity is local to the terminal environment.

Current Demo certification:

- login `448261`
- server `FusionMarkets-Demo`
- Algo Trading ON
- account/positions/orders/deals/symbol/quote/candle retrieval operational
- Demo execution certified

Execution certification uses `app/scripts/certify_mt5_execution.py` and must never intentionally touch unrelated positions.

## Interactive Brokers

IBKR integration uses `tools/ibkr_bridge.py` with TWS/IB Gateway and an ATLAS bridge client.

Current Paper account: `DUR980544`.

The bridge supports health/account/positions/orders/executions/market-data and Paper-order operations. Simulation checks are required before any certification execution.

Operational note: IBKR client IDs must be unique. If the bridge health endpoint is already healthy, do not start another bridge process using the same client ID.

## Bybit

Current Testnet AI subaccount UID: `107068845`.

The integration supports signed private API access and retrieval of wallet, positions, open orders, order history and closed P&L. The Testnet execution-certification script dynamically reads instrument constraints before constructing an order.

Current execution restriction: Bybit returned error `10024` when a valid BTCUSDT Testnet order reached `/v5/order/create`. The response describes a regulatory product/service restriction. ATLAS must surface this clearly and must not attempt to bypass it.

## Twelve Data

Twelve Data is market-data-only in the ATLAS provider model. It can contribute market/historical inputs to analysis but must never be routed an execution request.

## Routing principles

The eventual router should consider at least:

- asset class
- symbol/instrument availability
- provider/account enabled state
- environment (Demo/Paper/Testnet/Live)
- connection health
- market hours/session
- risk authorization
- account buying power/margin
- live-money gate

No AI/strategy decision may directly bypass the routing and risk layers.
