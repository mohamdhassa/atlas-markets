from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.analysis.shadow_strategy import evaluate_shadow_strategy
from app.brokers.ibkr_bridge import IbkrBridgeClient
from app.brokers.mt5_bridge import Mt5BridgeClient
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.db.models.broker import BrokerProfile
from app.db.models.shadow import ShadowObservation, ShadowScanEvent
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import SessionLocal
from app.market_data.bybit import BybitPublicMarketData
from app.services.news_intelligence import context_for_symbol

HORIZON_BARS = 6
ROUND_TRIP_COST_BPS = 8.0


def timeframe_seconds(value: str) -> int:
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    value = str(value or "5m").strip().lower()
    try:
        return max(60, int(value[:-1]) * units[value[-1]])
    except (KeyError, TypeError, ValueError):
        return 300


def _secret(profile: BrokerProfile) -> dict:
    return json.loads(decrypt_secret(profile.credential_blob_encrypted)) if profile.credential_blob_encrypted else {}


def _timestamp_ms(value: object) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return int(parsed.timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def _rows(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        payload = payload.get("candles") or payload.get("list") or payload.get("data") or []
    output = []
    for item in payload or []:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        output.append({
            "timestamp_ms": _timestamp_ms(item.get("timestamp_ms") or item.get("time") or item.get("timestamp")),
            "open": float(item["open"]), "high": float(item["high"]), "low": float(item["low"]),
            "close": float(item["close"]), "volume": float(item.get("volume") or 0),
        })
    return sorted(output, key=lambda row: row["timestamp_ms"])


async def candles_for(profile: BrokerProfile, symbol: str, timeframe: str, limit: int = 240) -> list[dict]:
    settings = get_settings()
    credentials = _secret(profile)
    if profile.provider == "IBKR":
        client = IbkrBridgeClient(credentials.get("bridge_url") or "http://host.docker.internal:8766", credentials.get("bridge_token"), settings.market_data_timeout_seconds)
        return _rows(await client.candles(symbol, timeframe, limit))
    if profile.provider == "MT5":
        client = Mt5BridgeClient(credentials.get("bridge_url") or "http://host.docker.internal:8765", credentials.get("bridge_token"), settings.market_data_timeout_seconds)
        return _rows(await client.candles(symbol, timeframe, limit))
    if profile.provider == "BYBIT":
        client = BybitPublicMarketData(settings.bybit_public_base_url, settings.market_data_timeout_seconds)
        return _rows(await client.get_candles(symbol=symbol, interval=timeframe, category="spot", limit=limit))
    return []


def _excursions(observation: ShadowObservation, path: list[dict]) -> tuple[float, float]:
    if not path or not observation.entry_price or observation.action not in {"BUY", "SELL"}:
        return 0.0, 0.0
    entry = observation.entry_price
    high, low = max(row["high"] for row in path), min(row["low"] for row in path)
    if observation.action == "BUY":
        favorable, adverse = (high / entry - 1) * 100, (low / entry - 1) * 100
    else:
        favorable, adverse = (entry / low - 1) * 100, (entry / high - 1) * 100
    return round(max(0.0, favorable), 6), round(min(0.0, adverse), 6)


def settle_due(db, strategy: SymbolStrategy, candles: list[dict], now: datetime) -> int:
    pending = list(db.scalars(select(ShadowObservation).where(
        ShadowObservation.strategy_id == strategy.id,
        ShadowObservation.outcome == "PENDING",
        ShadowObservation.evaluation_due_at <= now,
    )).all())
    settled = 0
    for observation in pending:
        due_ms = int(observation.evaluation_due_at.timestamp() * 1000)
        exit_candle = next((row for row in candles if row["timestamp_ms"] >= due_ms), None)
        if exit_candle is None:
            continue
        exit_price = float(exit_candle["close"])
        raw = ((exit_price / observation.entry_price) - 1) * 100 if observation.entry_price else 0.0
        gross = raw if observation.action == "BUY" else -raw if observation.action == "SELL" else 0.0
        cost_bps = float(observation.round_trip_cost_bps or ROUND_TRIP_COST_BPS)
        net = gross - (cost_bps / 100) if observation.action in {"BUY", "SELL"} else 0.0
        path = [row for row in candles if observation.source_timestamp_ms < row["timestamp_ms"] <= exit_candle["timestamp_ms"]]
        favorable, adverse = _excursions(observation, path)
        observation.exit_price = exit_price
        observation.gross_return_pct = round(gross, 6)
        observation.net_return_pct = round(net, 6)
        observation.max_favorable_excursion_pct = favorable
        observation.max_adverse_excursion_pct = adverse
        observation.outcome = "WIN" if net > 0 else "LOSS" if net < 0 else "FLAT"
        observation.settled_at = now
        settled += 1
    return settled


def _event(db, strategy: SymbolStrategy, profile: BrokerProfile, status: str, reason: str, **details: object) -> None:
    db.add(ShadowScanEvent(
        user_id=strategy.user_id, broker_profile_id=profile.id, strategy_id=strategy.id,
        provider=profile.provider, market=strategy.market, symbol=strategy.symbol,
        status=status, reason=reason, details_json=json.dumps(details, default=str),
    ))


async def observe_strategy(db, strategy: SymbolStrategy, profile: BrokerProfile, now: datetime) -> dict:
    timeframe = strategy.timeframe or "5m"
    candles = await candles_for(profile, strategy.symbol, timeframe)
    if len(candles) < 80:
        return {"status": "SKIP", "reason": "INSUFFICIENT_CANDLES", "symbol": strategy.symbol, "candle_count": len(candles)}
    latest = candles[-1]
    timestamp_ms = int(latest.get("timestamp_ms") or int(now.timestamp() * 1000))
    settled = settle_due(db, strategy, candles, now)
    if db.scalar(select(ShadowObservation.id).where(ShadowObservation.strategy_id == strategy.id, ShadowObservation.source_timestamp_ms == timestamp_ms)):
        return {"status": "EXISTS", "reason": "SOURCE_BAR_ALREADY_OBSERVED", "symbol": strategy.symbol, "settled": settled}
    news = context_for_symbol(db, strategy.symbol)
    decision = evaluate_shadow_strategy(candles, symbol=strategy.symbol, market=strategy.market, timeframe=timeframe, news_score=news.sentiment if news.article_count else None)
    db.add(ShadowObservation(
        user_id=strategy.user_id, broker_profile_id=profile.id, strategy_id=strategy.id,
        provider=profile.provider, market=strategy.market, symbol=strategy.symbol, timeframe=timeframe,
        action=decision["action"], confidence=decision["confidence"], regime=decision["regime"],
        confirmations=decision["confirmations"], contradictions=decision["contradictions"],
        entry_price=float(latest["close"]), source_timestamp_ms=timestamp_ms, horizon_bars=HORIZON_BARS,
        evaluation_due_at=now + timedelta(seconds=timeframe_seconds(timeframe) * HORIZON_BARS),
        news_score=news.sentiment if news.article_count else None, round_trip_cost_bps=ROUND_TRIP_COST_BPS,
        outcome="PENDING", details_json=json.dumps({"reasons": decision["reasons"], "calibration": decision["calibration"], "regime_details": decision["regime_details"], "news_articles": news.article_count}),
    ))
    return {"status": "OBSERVED", "reason": "DECISION_RECORDED", "symbol": strategy.symbol, "action": decision["action"], "settled": settled}


async def run_shadow_scan() -> dict:
    now = datetime.now(timezone.utc)
    result = {"observed": 0, "settled": 0, "skipped": 0, "errors": [], "providers": {}}
    provider_totals = defaultdict(lambda: {"strategies": 0, "observed": 0, "settled": 0, "skipped": 0, "errors": 0})
    with SessionLocal() as db:
        for strategy in db.scalars(select(SymbolStrategy).where(SymbolStrategy.enabled.is_(True))).all():
            profile = db.get(BrokerProfile, strategy.profile_id)
            if not profile:
                result["skipped"] += 1
                result["errors"].append({"symbol": strategy.symbol, "error": "BROKER_PROFILE_NOT_FOUND"})
                continue
            totals = provider_totals[profile.provider]
            totals["strategies"] += 1
            if not profile.is_enabled or not profile.is_active:
                result["skipped"] += 1
                totals["skipped"] += 1
                _event(db, strategy, profile, "SKIP", "PROFILE_DISABLED_OR_INACTIVE")
                db.commit()
                continue
            try:
                row = await observe_strategy(db, strategy, profile, now)
                observed = int(row["status"] == "OBSERVED")
                skipped = int(row["status"] in {"SKIP", "EXISTS"})
                settled = int(row.get("settled") or 0)
                result["observed"] += observed; result["settled"] += settled; result["skipped"] += skipped
                totals["observed"] += observed; totals["settled"] += settled; totals["skipped"] += skipped
                if row["status"] != "EXISTS":
                    _event(db, strategy, profile, row["status"], row["reason"], candle_count=row.get("candle_count"), action=row.get("action"))
                db.commit()
            except Exception as exc:
                db.rollback()
                message = f"{type(exc).__name__}: {str(exc)[:160]}"
                result["errors"].append({"provider": profile.provider, "symbol": strategy.symbol, "error": message})
                totals["errors"] += 1
                _event(db, strategy, profile, "ERROR", "PROVIDER_OR_ANALYSIS_ERROR", error=message)
                db.commit()
    result["providers"] = dict(provider_totals)
    return result


async def shadow_monitor_loop(stop_event, interval_seconds: int = 300) -> None:
    while not stop_event.is_set():
        try:
            await run_shadow_scan()
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(60, interval_seconds))
        except asyncio.TimeoutError:
            continue
