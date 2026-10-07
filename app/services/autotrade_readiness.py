from __future__ import annotations

import json
import math
import httpx
from datetime import datetime, timezone
from sqlalchemy import select

from app.brokers.bybit_private import BybitPrivateClient
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.bybit_inventory import BybitManagedInventory
from app.db.models.signal import RiskProfile
from app.db.models.strategy import StrategyProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.market_data.bybit import BybitPublicMarketData
from app.analysis.strategy_router import route_strategy
from app.services.paper_execution import build_execution_plan
from app.services.signal_risk import evaluate_risk, generate_signal
from app.services.capital_sizing import capital_policy_payload, capital_sizing_inputs
from app.services.bybit_spot_execution import managed_position_slots

READINESS_MAX_GROSS_EXPOSURE_PCT = 50.0
READINESS_MAX_NEW_POSITIONS_PER_ACCOUNT = 5
BYBIT_SIMULATION_ENVIRONMENTS = {"TESTNET", "DEMO"}


def _secret(profile) -> dict:
    if not profile.credential_blob_encrypted:
        raise RuntimeError(f"{profile.provider} bridge configuration missing")
    return json.loads(decrypt_secret(profile.credential_blob_encrypted))


def _risk(db):
    row = db.scalar(select(RiskProfile).where(RiskProfile.name == "Default"))
    return row or RiskProfile(name="Default")


def _strategy(db):
    row = db.scalar(select(StrategyProfile).where(StrategyProfile.name == "Default"))
    return row or StrategyProfile(name="Default")


def _params(cfg, default, risk):
    minimum = max(risk.minimum_signal_score, cfg.minimum_signal_strength if cfg.minimum_signal_strength is not None else default.minimum_signal_strength)
    risk_pct = min(risk.risk_per_trade_pct, cfg.risk_per_trade_pct if cfg.risk_per_trade_pct is not None else risk.risk_per_trade_pct)
    stop = cfg.stop_atr_multiplier if cfg.stop_atr_multiplier is not None else default.stop_atr_multiplier
    rr = cfg.take_profit_rr if cfg.take_profit_rr is not None else default.take_profit_rr
    max_pos = cfg.max_position_notional_pct if cfg.max_position_notional_pct is not None else default.max_position_notional_pct
    return cfg.timeframe or default.timeframe, minimum, risk_pct, stop, rr, max_pos


def _round_volume(raw, info):
    mn = float(info.get("volume_min") or 0.01)
    mx = float(info.get("volume_max") or raw)
    step = float(info.get("volume_step") or mn)
    value = max(mn, min(mx, raw))
    value = math.floor(value / step) * step
    return round(max(mn, value), 8)


def _ibkr_quote_price(quote, decision):
    for field in (("ask", "last", "bid") if decision == "BUY" else ("bid", "last", "ask")):
        try:
            price = float(quote.get(field) or 0)
        except (TypeError, ValueError):
            continue
        if math.isfinite(price) and price > 0:
            return price
    return 0.0


def _ibkr_provider_unavailable(exc: Exception) -> bool:
    """Return True only for IBKR bridge/network availability failures."""
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {502, 503, 504}
    return False


def _ibkr_connection_verdict(profile, credentials: dict, health: dict, account: dict) -> tuple[bool, str]:
    if not health.get("connected") or health.get("server_connected") is False:
        return False, "IBKR_BRIDGE_DISCONNECTED"
    if account.get("data_status") == "STALE":
        return False, "IBKR_ACCOUNT_DATA_STALE"
    actual = str(account.get("account_id") or "").strip()
    expected = str(credentials.get("account_id") or profile.external_account_ref or "").strip()
    if not actual or actual != expected:
        return False, "IBKR_ACCOUNT_MISMATCH"
    simulation = bool(account.get("simulation", health.get("simulation")))
    if str(profile.environment or "").upper() == "PAPER" and not simulation:
        return False, "IBKR_PAPER_SESSION_REQUIRED"
    return True, "CONNECTED"


async def _refresh_ibkr_connection(db, profile, settings) -> tuple[bool, str]:
    """Repair stale profile state only after live bridge/account verification."""
    try:
        credentials = _secret(profile)
        broker = IbkrBridgeClient(
            credentials.get("bridge_url") or "http://host.docker.internal:8766",
            credentials.get("bridge_token"),
            settings.market_data_timeout_seconds,
        )
        health = await broker.health()
        account = await broker.account() if health.get("connected") else {}
        connected, reason = _ibkr_connection_verdict(profile, credentials, health, account)
        profile.last_connection_status = "CONNECTED" if connected else "FAILED"
        profile.last_connection_test_at = datetime.now(timezone.utc)
        if connected:
            profile.last_sync_at = datetime.now(timezone.utc)
            profile.equity_usd = float(account.get("equity") or 0)
            profile.wallet_balance_usd = float(account.get("cash") or 0)
            profile.available_balance_usd = float(account.get("available") or 0)
        db.flush()
        return connected, reason
    except Exception as exc:
        profile.last_connection_status = "FAILED"
        profile.last_connection_test_at = datetime.now(timezone.utc)
        db.flush()
        return False, f"{type(exc).__name__}: {str(exc)[:160]}"


def _provider_execution_blockers(profile):
    if str(profile.provider or "").upper() != "BYBIT":
        return []
    environment = str(profile.environment or "").upper()
    if environment not in BYBIT_SIMULATION_ENVIRONMENTS:
        return ["BYBIT_TESTNET_OR_DEMO_REQUIRED"]
    if not (
        profile.execution_certified
        and profile.execution_certification_buy_passed
        and profile.execution_certification_sell_passed
    ):
        return ["BYBIT_SPOT_CERTIFICATION_REQUIRED"]
    return []


def _router_blocker(route: dict, decision: str) -> str | None:
    decision = str(decision or "").upper()
    strategy = str(route.get("strategy") or "NO_TRADE").upper()
    regime = str(route.get("regime") or "").upper()
    if strategy == "NO_TRADE":
        return "STRATEGY_ROUTER_NO_TRADE"
    if decision not in {"BUY", "SELL"}:
        return "STRATEGY_ROUTER_DIRECTION_REQUIRED"
    if regime in {"TRENDING_UP"} and decision != "BUY":
        return "STRATEGY_ROUTER_DIRECTION_CONFLICT"
    if regime in {"TRENDING_DOWN"} and decision != "SELL":
        return "STRATEGY_ROUTER_DIRECTION_CONFLICT"
    if regime == "BOX_BREAKOUT":
        breakout = str((route.get("box") or {}).get("breakout") or "NONE").upper()
        if (breakout == "UP" and decision != "BUY") or (breakout == "DOWN" and decision != "SELL"):
            return "STRATEGY_ROUTER_DIRECTION_CONFLICT"
    return None


def _bybit_spot_available(wallet: dict, coin: str = "USDT") -> float:
    rows = wallet.get("list") or []
    coins = (rows[0].get("coin") or []) if rows else []
    for row in coins:
        if str(row.get("coin") or "").upper() != coin.upper():
            continue
        for key in ("availableToWithdraw", "walletBalance", "equity"):
            try:
                value = float(row.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
    return 0.0


def _portfolio_guard(*, equity, existing_positions, existing_gross_notional, reserved_new_notional, reserved_new_positions, proposed_notional):
    if equity <= 0:
        return ["PORTFOLIO_EQUITY_UNAVAILABLE"]
    blockers = []
    max_gross = equity * (READINESS_MAX_GROSS_EXPOSURE_PCT / 100)
    projected = max(0, existing_gross_notional) + max(0, reserved_new_notional) + max(0, proposed_notional)
    if projected > max_gross + 1e-8:
        blockers.append("PORTFOLIO_GROSS_EXPOSURE_LIMIT")
    if existing_positions + reserved_new_positions + 1 > READINESS_MAX_NEW_POSITIONS_PER_ACCOUNT:
        blockers.append("PORTFOLIO_POSITION_LIMIT")
    return blockers


def _position_notional(position):
    for key in ("market_value", "marketValue", "notional", "position_value", "positionValue"):
        try:
            value = abs(float(position.get(key) or 0))
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    qty = abs(float(position.get("quantity") or position.get("volume") or position.get("size") or 0))
    for key in ("market_price", "marketPrice", "price", "markPrice", "current_price", "currentPrice"):
        try:
            price = abs(float(position.get(key) or 0))
        except (TypeError, ValueError):
            price = 0
        if price > 0:
            return qty * price
    return 0.0


from app.services.system_events import context, emit, traced


@traced('READINESS')
async def autotrade_readiness(db, *, user_id) -> dict:
    settings = get_settings()
    risk = _risk(db)
    default = _strategy(db)
    configs = list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id == user_id, SymbolStrategy.enabled.is_(True))).all())
    profiles = {p.id: p for p in db.scalars(select(BrokerProfile).where(BrokerProfile.user_id == user_id)).all()}
    market = BybitPublicMarketData(settings.bybit_public_base_url, settings.market_data_timeout_seconds)
    rows = []
    portfolio_reservations = {}
    managed_slot_cache = {}

    for cfg in sorted(configs, key=lambda x: (x.market, x.symbol)):
        profile = profiles.get(cfg.profile_id)
        context(market=cfg.market, symbol=cfg.symbol, provider=profile.provider if profile else 'UNKNOWN')
        emit('AUTOMATION', 'SYMBOL_CHECK_STARTED', message='Configured instrument check started')
        base = {"market": cfg.market, "symbol": cfg.symbol, "mode": cfg.mode, "execution": "DRY_RUN"}
        if not profile:
            rows.append({**base, "readiness": "BLOCK", "reason": "PROFILE_MISSING"})
            continue
        base.update(provider=profile.provider, environment=profile.environment)
        if profile.provider == "IBKR":
            await _refresh_ibkr_connection(db, profile, settings)
        if not (profile.is_enabled and profile.is_active and profile.credentials_configured and profile.last_connection_status == "CONNECTED"):
            rows.append({**base, "readiness": "BLOCK", "reason": "ROUTE_NOT_READY"})
            continue

        try:
            timeframe, minimum, risk_pct, stop, rr, max_pos = _params(cfg, default, risk)
            existing_qty = 0.0
            existing_positions = 0
            existing_gross = equity = available = price = 0.0
            sizing = {}
            normalized_candles = []
            signal_market = str(cfg.market or "CRYPTO").upper()

            if profile.provider == "BYBIT":
                candles = await market.get_candles(symbol=cfg.symbol, interval=timeframe, category="spot", limit=200)
                normalized_candles = [x.model_dump() for x in candles]
                generated = generate_signal(normalized_candles, timeframe=timeframe, market=signal_market)
                environment = str(profile.environment or "").upper()
                if environment == "DEMO":
                    base_url = settings.bybit_demo_base_url
                elif environment == "TESTNET":
                    base_url = settings.bybit_testnet_base_url
                else:
                    raise RuntimeError("BYBIT_TESTNET_OR_DEMO_REQUIRED")
                broker = BybitPrivateClient(
                    decrypt_secret(profile.api_key_encrypted),
                    decrypt_secret(profile.api_secret_encrypted),
                    base_url,
                    settings.market_data_timeout_seconds,
                )
                wallet = await broker.wallet()
                account = (wallet.get("list") or [{}])[0]
                equity = float(account.get("totalEquity") or account.get("totalWalletBalance") or 0)
                available = _bybit_spot_available(wallet, "USDT")
                holdings = broker.spot_holdings_from_wallet(wallet)
                existing_gross = sum(float(row.get("usd_value") or 0) for row in holdings)
                managed_rows = list(db.scalars(select(BybitManagedInventory).where(BybitManagedInventory.broker_profile_id == profile.id, BybitManagedInventory.managed_quantity > 1e-12)).all())
                if profile.id not in managed_slot_cache:
                    managed_slot_cache[profile.id] = await managed_position_slots(broker, managed_rows)
                slots = managed_slot_cache[profile.id]
                existing_positions = slots["count"]
                base["managed_position_slots"] = slots
                managed = db.scalar(select(BybitManagedInventory).where(BybitManagedInventory.broker_profile_id == profile.id, BybitManagedInventory.symbol == str(cfg.symbol).upper()))
                existing_qty = float(managed.managed_quantity or 0) if managed else 0.0
                ticker = await market.get_tickers(category="spot", symbols=(cfg.symbol,))
                price = float(ticker.tickers[0].last_price) if ticker.tickers else 0
                base["product"] = "SPOT"
                base["managed_inventory"] = existing_qty
            elif profile.provider == "MT5":
                c = _secret(profile)
                broker = Mt5BridgeClient(c.get("bridge_url") or "http://host.docker.internal:8765", c.get("bridge_token"), settings.market_data_timeout_seconds)
                normalized_candles = (await broker.candles(cfg.symbol, timeframe, 200)).get("list", [])
                generated = generate_signal(normalized_candles, timeframe=timeframe, market=signal_market)
                acct = await broker.account()
                positions = (await broker.positions()).get("list", [])
                equity = float(acct.get("equity") or 0)
                available = float(acct.get("margin_free") or equity)
                existing_positions = len(positions)
                existing_gross = sum(_position_notional(p) for p in positions)
                existing_qty = sum(float(p.get("volume") or p.get("quantity") or 0) for p in positions if str(p.get("symbol") or "").upper() == cfg.symbol.upper())
                info = await broker.symbol(cfg.symbol)
                price = float(info.get("ask") if generated.decision == "BUY" else info.get("bid") or 0)
                sizing["contract_size"] = float(info.get("trade_contract_size") or 100000)
                sizing["symbol_info"] = info
            elif profile.provider == "IBKR":
                c = _secret(profile)
                broker = IbkrBridgeClient(c.get("bridge_url") or "http://host.docker.internal:8766", c.get("bridge_token"), settings.market_data_timeout_seconds)
                normalized_candles = (await broker.candles(cfg.symbol, timeframe, 200, sec_type="STK")).get("list", [])
                generated = generate_signal(normalized_candles, timeframe=timeframe, market=signal_market)
                acct = await broker.account()
                positions = [p for p in (await broker.positions()).get("list", []) if float(p.get("quantity") or 0) != 0]
                equity = float(acct.get("equity") or 0)
                available = float(acct.get("available") or acct.get("cash") or equity)
                existing_positions = len(positions)
                existing_gross = sum(_position_notional(p) for p in positions)
                existing_qty = sum(float(p.get("quantity") or 0) for p in positions if str(p.get("symbol") or "").upper() == cfg.symbol.upper())
                price = _ibkr_quote_price(await broker.quote(cfg.symbol, sec_type="STK"), generated.decision)
            else:
                rows.append({**base, "readiness": "BLOCK", "reason": "UNSUPPORTED_PROVIDER"})
                continue

            approved, reason, details = evaluate_risk(
                generated,
                minimum_signal_score=minimum,
                account_enabled=profile.is_enabled,
                allow_live_trading=False,
                account_environment=profile.environment,
            )
            strategy_route = route_strategy(normalized_candles)
            emit('TRADING', 'SIGNAL_EVALUATED', message='Signal and risk evaluation completed',
                 decision=generated.decision, status='PASS' if approved else 'BLOCK', reason=reason,
                 timeframe=timeframe, candle_count=len(normalized_candles))
            details["strategy_route"] = strategy_route
            blockers = _provider_execution_blockers(profile)
            router_blocker = _router_blocker(strategy_route, generated.decision)
            if router_blocker:
                blockers.append(router_blocker)
            if not approved:
                blockers.append(reason)

            if profile.provider == "BYBIT":
                if generated.decision == "BUY":
                    if existing_positions >= risk.max_open_positions:
                        blockers.append("MAX_OPEN_POSITIONS_REACHED")
                    if existing_qty > 1e-12:
                        blockers.append("ATLAS_MANAGED_POSITION_ALREADY_OPEN")
                elif generated.decision == "SELL" and existing_qty <= 1e-12:
                    blockers.append("NO_ATLAS_MANAGED_INVENTORY")
            else:
                if existing_positions >= risk.max_open_positions:
                    blockers.append("MAX_OPEN_POSITIONS_REACHED")
                if existing_qty != 0:
                    blockers.append("SYMBOL_ALREADY_HAS_POSITION")

            proposed = None
            reservation = portfolio_reservations.setdefault(str(profile.id), {"notional": 0.0, "positions": 0})
            portfolio = {
                "existing_gross_notional": round(existing_gross, 8),
                "reserved_new_notional": round(float(reservation["notional"]), 8),
                "gross_exposure_limit_pct": READINESS_MAX_GROSS_EXPOSURE_PCT,
                "new_position_limit": READINESS_MAX_NEW_POSITIONS_PER_ACCOUNT,
            }

            if approved and price > 0:
                sizing_equity, sizing_available, capital_basis = capital_sizing_inputs(
                    broker_equity=equity,
                    broker_available=available,
                    environment=profile.environment,
                    simulation_capital_override_usd=profile.simulation_capital_override_usd,
                )
                plan = build_execution_plan(
                    decision=generated.decision,
                    price=price,
                    equity=sizing_equity,
                    available_cash=sizing_available,
                    risk_per_trade_pct=risk_pct,
                    stop_atr_multiplier=stop,
                    take_profit_rr=rr,
                    max_position_notional_pct=max_pos,
                )
                effective_notional = plan.notional
                proposed = {
                    "side": plan.side,
                    "price": price,
                    "notional": plan.notional,
                    "quantity": plan.quantity,
                    "stop_loss": plan.stop_loss,
                    "take_profit": plan.take_profit,
                    "sizing_capital_usd": sizing_equity,
                    "capital_basis": capital_basis,
                    "simulation_capital_override_usd": profile.simulation_capital_override_usd,
                    "max_risk_usd": plan.risk_amount,
                }

                if profile.provider == "BYBIT":
                    if generated.decision == "SELL" and existing_qty > 1e-12:
                        effective_notional = existing_qty * price
                        proposed.update({"quantity": existing_qty, "notional": effective_notional, "sizing_policy": "CLOSE_ATLAS_MANAGED_SPOT_INVENTORY"})
                    else:
                        proposed["sizing_policy"] = "ATLAS_MANAGED_SPOT_INVENTORY"
                        if effective_notional > available:
                            blockers.append("INSUFFICIENT_AVAILABLE_BALANCE")
                        blockers.extend(_portfolio_guard(
                            equity=equity,
                            existing_positions=existing_positions,
                            existing_gross_notional=existing_gross,
                            reserved_new_notional=float(reservation["notional"]),
                            reserved_new_positions=int(reservation["positions"]),
                            proposed_notional=effective_notional,
                        ))
                        if not blockers:
                            reservation["notional"] = float(reservation["notional"]) + effective_notional
                            reservation["positions"] = int(reservation["positions"]) + 1
                elif profile.provider == "MT5":
                    proposed["volume"] = _round_volume(plan.quantity / sizing["contract_size"], sizing["symbol_info"])
                    if effective_notional > available:
                        blockers.append("INSUFFICIENT_AVAILABLE_BALANCE")
                    blockers.extend(_portfolio_guard(
                        equity=equity,
                        existing_positions=existing_positions,
                        existing_gross_notional=existing_gross,
                        reserved_new_notional=float(reservation["notional"]),
                        reserved_new_positions=int(reservation["positions"]),
                        proposed_notional=effective_notional,
                    ))
                    if not blockers:
                        reservation["notional"] = float(reservation["notional"]) + effective_notional
                        reservation["positions"] = int(reservation["positions"]) + 1
                elif profile.provider == "IBKR":
                    from app.services.ibkr_fractional import size_ibkr_entry

                    strategy_shares = max(0.0, float(plan.quantity))
                    entry = size_ibkr_entry(strategy_shares, fractional_enabled=settings.ibkr_fractional_api_enabled)
                    certified_shares = entry["shares"]
                    effective_notional = certified_shares * price
                    proposed.update({
                        "strategy_requested_shares": strategy_shares,
                        **entry,
                        "notional": effective_notional,
                    })
                    if certified_shares <= 0:
                        blockers.append("IBKR_QUANTITY_BELOW_MINIMUM_FRACTIONAL_SHARE" if settings.ibkr_fractional_api_enabled else "IBKR_QUANTITY_BELOW_ONE_SHARE")
                    if effective_notional > available:
                        blockers.append("INSUFFICIENT_AVAILABLE_BALANCE")
                    blockers.extend(_portfolio_guard(
                        equity=equity,
                        existing_positions=existing_positions,
                        existing_gross_notional=existing_gross,
                        reserved_new_notional=float(reservation["notional"]),
                        reserved_new_positions=int(reservation["positions"]),
                        proposed_notional=effective_notional,
                    ))
                    if not blockers:
                        reservation["notional"] = float(reservation["notional"]) + effective_notional
                        reservation["positions"] = int(reservation["positions"]) + 1

                portfolio["projected_gross_notional"] = round(existing_gross + float(reservation["notional"]) + (0 if not blockers else effective_notional), 8)

            signal_ready = approved and price > 0
            rows.append({
                **base,
                "timeframe": timeframe,
                "decision": generated.decision,
                "classification": generated.classification,
                "strength": generated.strength,
                "signal_reason": reason,
                "risk_details": details,
                "strategy_route": strategy_route,
                "account": {"equity": equity, "available": available, "open_positions": existing_positions},
                "portfolio": portfolio,
                "existing_symbol_quantity": existing_qty,
                "proposed_order": proposed,
                "signal_ready": signal_ready,
                "execution_ready": not blockers,
                "readiness": "PASS" if not blockers else "BLOCK",
                "blockers": blockers,
            })
        except Exception as exc:
            if profile.provider == "IBKR" and _ibkr_provider_unavailable(exc):
                rows.append({
                    **base,
                    "readiness": "PROVIDER_UNAVAILABLE",
                    "reason": "IBKR_PROVIDER_UNAVAILABLE",
                    "provider_status": "UNAVAILABLE",
                })
            else:
                rows.append({**base, "readiness": "BLOCK", "reason": f"{type(exc).__name__}: {str(exc) or repr(exc)}"})

    for row in rows:
        emit('TRADING', 'READINESS_OUTCOME', message='Instrument readiness outcome', provider=row.get('provider'),
             market=row.get('market'), symbol=row.get('symbol'), decision=row.get('decision') or 'HOLD',
             status=row.get('readiness'), reason='|'.join(row.get('blockers') or []) or row.get('reason'),
             level='INFO' if row.get('readiness') == 'PASS' else 'WARNING')
    return {
        "execution_enabled": False,
        "purpose": "AUTO_TRADE_READINESS_DRY_RUN",
        "capital_sizing_policy": capital_policy_payload(simulation_capital_override_usd=None),
        "portfolio_policy": {
            "max_gross_exposure_pct": READINESS_MAX_GROSS_EXPOSURE_PCT,
            "max_new_positions_per_account": READINESS_MAX_NEW_POSITIONS_PER_ACCOUNT,
            "ibkr_paper_quantity_mode": "RISK_SIZED_FRACTIONAL_SHARES" if settings.ibkr_fractional_api_enabled else "RISK_SIZED_WHOLE_SHARES",
            "ibkr_paper_share_step": 0.0001 if settings.ibkr_fractional_api_enabled else 1.0,
            "bybit_product": "SPOT",
            "bybit_environments": sorted(BYBIT_SIMULATION_ENVIRONMENTS),
            "bybit_sell_policy": "ATLAS_MANAGED_INVENTORY_ONLY",
        },
        "configured_count": len(configs),
        "pass_count": sum(x.get("readiness") == "PASS" for x in rows),
        "block_count": sum(x.get("readiness") == "BLOCK" for x in rows),
        "provider_unavailable_count": sum(x.get("readiness") == "PROVIDER_UNAVAILABLE" for x in rows),
        "items": rows,
    }
