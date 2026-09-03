from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.models.symbol_strategy import SymbolStrategy
from app.db.session import get_db
from app.services.automation import get_or_create_state
from app.services.safe_automation import IBKR_CERTIFIED_MAX_SHARES_PER_ORDER

router = APIRouter(prefix="/release", tags=["release"])


def _connected(profile: BrokerProfile) -> bool:
    return bool(
        profile.is_enabled
        and profile.is_active
        and profile.credentials_configured
        and profile.last_connection_status == "CONNECTED"
    )


def _live_certification_status() -> dict:
    providers = {
        "MT5": {
            "simulation_certification": "CERTIFIED_DEMO",
            "live_certification": "NOT_CERTIFIED",
            "live_execution_allowed": False,
            "blockers": [
                "LIVE_MT5_EXECUTION_PATH_NOT_CERTIFIED",
                "LIVE_MT5_POSITION_LIFECYCLE_NOT_CERTIFIED",
            ],
        },
        "IBKR": {
            "simulation_certification": "CERTIFIED_PAPER",
            "live_certification": "NOT_CERTIFIED",
            "live_execution_allowed": False,
            "blockers": [
                "LIVE_IBKR_EXECUTION_PATH_NOT_CERTIFIED",
                "LIVE_IBKR_MARKET_DATA_NOT_VERIFIED",
            ],
        },
        "BYBIT": {
            "simulation_certification": "PROVIDER_BLOCKED_10024",
            "live_certification": "NOT_CERTIFIED",
            "live_execution_allowed": False,
            "blockers": [
                "BYBIT_PROVIDER_RESTRICTION_10024",
                "LIVE_BYBIT_EXECUTION_PATH_NOT_CERTIFIED",
            ],
        },
        "TWELVE_DATA": {
            "simulation_certification": "DATA_ONLY",
            "live_certification": "NOT_APPLICABLE",
            "live_execution_allowed": False,
            "blockers": ["MARKET_DATA_ONLY_PROVIDER"],
        },
    }
    execution_providers = ["MT5", "IBKR", "BYBIT"]
    certified = [p for p in execution_providers if providers[p]["live_certification"] == "CERTIFIED"]
    return {
        "status": "LOCKED" if len(certified) != len(execution_providers) else "CERTIFIED",
        "execution_providers_required": len(execution_providers),
        "execution_providers_certified": len(certified),
        "all_execution_providers_certified": len(certified) == len(execution_providers),
        "providers": providers,
        "rule": "Simulation, Demo, Paper or Testnet certification never implies Live Money certification.",
    }


@router.get("/readiness")
def release_readiness(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    state = get_or_create_state(db)
    profiles = list(db.scalars(select(BrokerProfile).where(BrokerProfile.user_id == current.id)).all())
    strategies = list(db.scalars(select(SymbolStrategy).where(SymbolStrategy.user_id == current.id)).all())

    by_provider: dict[str, list[BrokerProfile]] = {}
    for profile in profiles:
        by_provider.setdefault(profile.provider.upper(), []).append(profile)

    provider_status = {
        "MT5": {
            "connected": any(_connected(p) and p.environment.upper() == "DEMO" for p in by_provider.get("MT5", [])),
            "execution": "CERTIFIED_DEMO",
        },
        "IBKR": {
            "connected": any(_connected(p) and p.environment.upper() == "PAPER" for p in by_provider.get("IBKR", [])),
            "execution": "CERTIFIED_PAPER",
            "max_shares_per_order": IBKR_CERTIFIED_MAX_SHARES_PER_ORDER,
        },
        "BYBIT": {
            "connected": any(_connected(p) for p in by_provider.get("BYBIT", [])),
            "execution": "PROVIDER_BLOCKED_10024",
        },
        "TWELVE_DATA": {
            "connected": any(_connected(p) for p in by_provider.get("TWELVE_DATA", [])),
            "execution": "DATA_ONLY",
        },
    }

    auto_count = sum(1 for x in strategies if x.enabled and x.mode == "AUTO_TRADE")
    signals_count = sum(1 for x in strategies if x.enabled and x.mode == "SIGNALS")
    watch_count = sum(1 for x in strategies if x.enabled and x.mode == "WATCH")

    simulation_ready = (
        state.enabled
        and not state.killed
        and state.auto_execute_paper
        and provider_status["MT5"]["connected"]
        and provider_status["IBKR"]["connected"]
    )

    live_profiles_armed = [
        p
        for p in profiles
        if p.environment.upper() == "LIVE" and p.live_execution_enabled
    ]
    live_certification = _live_certification_status()

    return {
        "release": "1.0.0-simulation",
        "release_status": "SIMULATION_READY" if simulation_ready else "SIMULATION_CONFIGURATION_REQUIRED",
        "completion_scope": "PAPER_DEMO_TESTNET_AUTOMATION",
        "automation": {
            "enabled": state.enabled,
            "killed": state.killed,
            "simulation_execution": state.auto_execute_paper,
            "policy": "CERTIFIED_ROUTES_ONLY",
        },
        "providers": provider_status,
        "live_certification": live_certification,
        "strategies": {
            "configured": len(strategies),
            "auto_trade": auto_count,
            "signals": signals_count,
            "watch": watch_count,
        },
        "safety": {
            "live_money_ready": False,
            "live_money_execution": "GATED",
            "live_profiles_armed": len(live_profiles_armed),
            "live_execution_providers_certified": live_certification["execution_providers_certified"],
            "live_execution_providers_required": live_certification["execution_providers_required"],
            "all_live_execution_providers_certified": live_certification["all_execution_providers_certified"],
            "bybit_execution": "BLOCKED_BY_PROVIDER_10024",
            "historical_strategy_attribution": "ONLY_BROKER_VERIFIED_ACTIONS",
        },
        "completion": {
            "backend": "COMPLETE_FOR_SIMULATION_RELEASE",
            "frontend": "COMPLETE_FOR_SIMULATION_RELEASE",
            "automation": "COMPLETE_ON_CERTIFIED_ROUTES",
            "reporting": "COMPLETE_WITH_CONSERVATIVE_ATTRIBUTION",
            "documentation": "FINAL_HANDOVER_INCLUDED",
            "live_money": "OUTSIDE_SIMULATION_RELEASE_UNTIL_EXTENDED_VALIDATION",
        },
    }
