# ATLAS MARKETS — ERD

Last updated: 2026-08-30
Release line: v1.1 simulation / Oracle deployment preparation

This document describes the active PostgreSQL persistence model. Legacy ATLAS Paper tables remain for compatibility/history, but normal execution uses external provider accounts.

## Logical ERD

```mermaid
erDiagram
    USERS ||--o{ USER_SESSIONS : owns
    USERS ||--o{ AUTH_AUDIT_LOG : produces
    USERS ||--o{ BROKER_PROFILES : owns
    USERS ||--o{ SYMBOL_STRATEGIES : configures
    USERS ||--o{ AUTOMATION_ACTIONS : produces
    USERS ||--o{ SIGNALS : receives
    USERS ||--o{ RISK_EVENTS : receives
    USERS ||--o{ PAPER_WALLETS : legacy_owns
    USERS ||--o{ PAPER_POSITIONS : legacy_owns
    USERS ||--o{ PAPER_ORDERS : legacy_owns

    BROKER_PROFILES ||--o{ SYMBOL_STRATEGIES : routes
    BROKER_PROFILES ||--o{ AUTOMATION_ACTIONS : executes
    BROKER_PROFILES ||--o{ DAILY_ACCOUNT_REPORTS : reports

    AUTOMATION_SCANS ||--o{ AUTOMATION_ACTIONS : contains

    STRATEGY_PROFILES ||--o{ SYMBOL_STRATEGIES : defaults_for

    USERS {
      uuid id PK
      string username
      string email
      string password_hash
      enum role
      bool is_active
      datetime created_at
      datetime updated_at
    }

    BROKER_PROFILES {
      uuid id PK
      uuid user_id FK
      string provider
      string account_label
      string environment
      string external_account_ref
      bool is_enabled
      bool is_active
      bool live_execution_enabled
      datetime live_execution_armed_at
      string last_connection_status
      bool credentials_configured
      text encrypted_credentials
      float equity_usd
      float wallet_balance_usd
      float available_balance_usd
      int open_positions_count
      int open_orders_count
      datetime last_sync_at
    }

    SYMBOL_STRATEGIES {
      uuid id PK
      uuid user_id FK
      uuid profile_id FK
      string market
      string symbol
      string mode
      bool enabled
      string timeframe
      float minimum_signal_strength
      float risk_per_trade_pct
      float stop_atr_multiplier
      float take_profit_rr
      float max_position_notional_pct
    }

    AUTOMATION_STATE {
      int id PK
      bool enabled
      bool killed
      bool auto_execute_paper
      int interval_seconds
      text symbols_csv
      datetime last_scan_at
      datetime next_scan_at
    }

    AUTOMATION_SCANS {
      uuid id PK
      string status
      int symbols_count
      int accounts_count
      int signals_count
      int approved_count
      int executed_count
      text error_message
      datetime started_at
      datetime finished_at
    }

    AUTOMATION_ACTIONS {
      uuid id PK
      uuid scan_id FK
      uuid user_id FK
      uuid broker_profile_id FK
      string provider
      string environment
      string market
      string symbol
      string side
      string status
      string reason
      float quantity
      string sizing_policy
      string broker_order_id
      string broker_position_id
      text raw_json
      datetime created_at
    }

    SIGNALS {
      uuid id PK
      uuid user_id FK
      string market
      string symbol
      string side
      float confidence
      text reason
      datetime created_at
    }

    RISK_PROFILES {
      uuid id PK
      string name
      float risk_per_trade_pct
      int max_open_positions
      float max_daily_loss_pct
      float max_drawdown_pct
    }

    RISK_EVENTS {
      uuid id PK
      uuid user_id FK
      string event_type
      string severity
      text detail
      datetime created_at
    }

    HISTORICAL_CANDLES {
      uuid id PK
      string provider
      string market
      string symbol
      string timeframe
      datetime candle_time
      float open
      float high
      float low
      float close
      float volume
    }

    HISTORICAL_BACKTEST_RUNS {
      uuid id PK
      string market
      string symbol
      string timeframe
      text parameters_json
      text result_json
      datetime created_at
    }

    NEWS_ARTICLES {
      uuid id PK
      string source
      string title
      string url
      datetime published_at
      float sentiment
      text raw_json
    }

    DAILY_ACCOUNT_REPORTS {
      uuid id PK
      uuid broker_profile_id FK
      date report_date
      float equity
      float realized_pnl
      float unrealized_pnl
      int trades
      text raw_json
    }
```

## Core ownership model

- `users` is the security/ownership root.
- `broker_profiles` stores provider/account configuration, encrypted credentials and synchronized account summary data.
- `symbol_strategies` maps each market/symbol to a broker profile and an operating mode: `WATCH`, `SIGNALS`, or `AUTO_TRADE`.
- `automation_scans` is the scan/cycle header.
- `automation_actions` is the persistent execution/safety ledger and carries broker order/position references plus raw evidence.

## Broker truth vs ATLAS truth

Provider-native fills, positions and P&L remain the authoritative broker truth. ATLAS persists the action lineage required to attribute future fills without inventing historical strategy ownership. Historical broker activity that predates verifiable action lineage is intentionally kept unverified.

## Legacy Paper entities

`paper_wallets`, `paper_positions`, and `paper_orders` remain in the database for migration/history compatibility. The active account model is `EXTERNAL_PROVIDERS_ONLY`; they must not be mistaken for Fusion Demo, IBKR Paper or Bybit Testnet activity.

## Oracle persistence

Oracle deployment continues to use PostgreSQL 17 in a private Docker network with a persistent Docker volume. PostgreSQL port 5432 and Redis port 6379 are not published publicly. Backups are custom-format `pg_dump` files stored outside Git.

See `ORACLE_DEPLOYMENT.md` for backup/restore and hosting topology.
