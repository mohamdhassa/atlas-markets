from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.routes_accounts import _new_profile, _save_creds
from app.brokers.bybit_private import BybitPrivateClient
from app.core.config import get_settings
from app.db.models.auth import User
from app.db.models.broker import BrokerProfile
from app.db.session import get_db
from app.schemas.broker_profile import BrokerProfileCreate

router = APIRouter(prefix="/bybit/oauth", tags=["bybit-oauth"])
CLIENT_ID = "ai-agent"
TESTNET_AUTHORIZE = "https://testnet.bybit.com/oauth"
TESTNET_OAUTH_BASE = "https://api2-testnet.bybit.com"
TESTNET_TRADING_BASE = "https://api-testnet.bybit.com"
SESSION_TTL = 600
_sessions: dict[str, dict[str, Any]] = {}


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _cleanup() -> None:
    now = time.time()
    for key in [k for k, v in _sessions.items() if now - v["created_at"] > SESSION_TTL]:
        _sessions.pop(key, None)


def _session(session_id: str, user: User | None = None) -> dict[str, Any]:
    _cleanup()
    s = _sessions.get(session_id)
    if not s:
        raise HTTPException(404, "OAuth session expired or not found; start authorization again")
    if user is not None and str(user.id) != s["user_id"]:
        raise HTTPException(403, "OAuth session belongs to another user")
    return s


class OAuthStart(BaseModel):
    account_label: str = "Bybit Testnet"


class OAuthManualCode(BaseModel):
    session_id: str
    authorization_code: str


class OAuthSelect(BaseModel):
    session_id: str
    sub_member_id: str | None = None
    create_new: bool = False
    activate: bool = True


def _oauth_error(data: Any, fallback: str) -> tuple[Any, str]:
    if not isinstance(data, dict):
        return None, fallback
    return data.get("retCode", data.get("ret_code")), data.get("retMsg", data.get("ret_msg", fallback))


async def _json_response(response: httpx.Response, operation: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        content_type = response.headers.get("content-type", "unknown")
        raise HTTPException(
            502,
            f"Bybit OAuth {operation} returned HTTP {response.status_code} ({content_type}) instead of JSON",
        )
    if not isinstance(data, dict):
        raise HTTPException(502, f"Bybit OAuth {operation} returned an unexpected response")
    return data


async def _exchange_code(s: dict[str, Any], code: str) -> dict[str, Any]:
    code = (code or "").strip()
    verifier = s.get("code_verifier")
    if not code:
        raise HTTPException(400, "Authorization code is required")
    if not verifier:
        raise HTTPException(409, "PKCE session is no longer available; start authorization again")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{TESTNET_OAUTH_BASE}/oauth/v1/public/access_token",
                data={"client_id": CLIENT_ID, "code": code, "code_verifier": verifier},
            )
        data = await _json_response(response, "token exchange")
        ret, msg = _oauth_error(data, "token exchange failed")
        if ret is not None and ret != 0:
            raise HTTPException(502, f"Bybit OAuth {ret}: {msg}")
        token = data.get("result") or data
        if not isinstance(token, dict) or not token.get("access_token"):
            raise HTTPException(502, "Bybit OAuth response did not contain an access token")
        s["access_token"] = token["access_token"]
        s["refresh_token"] = token.get("refresh_token")
        s["status"] = "AUTHORIZED"
        s.pop("code_verifier", None)
        s.pop("error", None)
        return token
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Bybit OAuth token exchange failed: {str(exc)[:240]}")


async def _ai_accounts_with_token(token: str, query: str = "") -> Any:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{TESTNET_OAUTH_BASE}/oauth/v1/resource/restrict/ai_accounts{query}",
                headers={"Authorization": f"Bearer {token}"},
            )
        data = await _json_response(response, "AI-account request")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Bybit OAuth request failed: {str(exc)[:240]}")
    ret, msg = _oauth_error(data, "AI account request failed")
    if ret is not None and ret != 0:
        if ret == 20039:
            raise HTTPException(409, "Bybit requires 2FA to be bound before Agent Connect can continue")
        raise HTTPException(502, f"Bybit OAuth {ret}: {msg}")
    return data.get("result", data)


async def _ai_accounts(s: dict[str, Any], query: str = "") -> Any:
    token = (s.get("access_token") or "").strip()
    if not token:
        raise HTTPException(409, "OAuth access token is not available")
    return await _ai_accounts_with_token(token, query)


@router.post("/start")
def start_oauth(payload: OAuthStart, user: User = Depends(get_current_user)):
    _cleanup()
    session_id = secrets.token_urlsafe(24)
    state = secrets.token_urlsafe(24)
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    redirect_uri = "http://127.0.0.1:8000/bybit/oauth/callback"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "ai-account",
        "state": state,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    _sessions[session_id] = {
        "created_at": time.time(),
        "user_id": str(user.id),
        "state": state,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri,
        "account_label": payload.account_label.strip() or "Bybit Testnet",
        "status": "WAITING_FOR_AUTHORIZATION",
    }
    return {
        "environment": "TESTNET",
        "session_id": session_id,
        "authorize_url": f"{TESTNET_AUTHORIZE}?{urlencode(params)}",
        "expires_in": SESSION_TTL,
        "manual_code_supported": True,
        "message": "Authorize from the Testnet main account. If Bybit displays a manual value, paste it into ATLAS; ATLAS will safely detect whether it is an access token or authorization code.",
    }


@router.post("/manual-code")
async def manual_code(payload: OAuthManualCode, user: User = Depends(get_current_user)):
    """Accept Bybit's manually displayed value without guessing its type.

    Bybit documentation currently describes two manual/headless behaviours across its
    cloud-agent and local-agent guides: a directly usable access token, or a one-time
    authorization code tied to the current PKCE verifier. We first test the value as a
    Bearer token. If Bybit rejects token verification, we immediately try the official
    PKCE code exchange using the same in-memory session. Raw values are never persisted.
    """
    s = _session(payload.session_id, user)
    if s.get("status") not in {"WAITING_FOR_AUTHORIZATION", "FAILED"}:
        raise HTTPException(409, "OAuth session is not waiting for a manual authorization value")
    value = (payload.authorization_code or "").strip()
    if not value:
        raise HTTPException(400, "Bybit Agent Connect authorization value is required")

    bearer_error: str | None = None
    try:
        await _ai_accounts_with_token(value)
        s["access_token"] = value
        s["refresh_token"] = None
        s["status"] = "AUTHORIZED"
        s.pop("code_verifier", None)
        s.pop("error", None)
        return {
            "environment": "TESTNET",
            "status": "AUTHORIZED",
            "mode": "ACCESS_TOKEN",
            "message": "Bybit access token accepted. Choose an existing AI sub-account.",
        }
    except HTTPException as exc:
        bearer_error = str(exc.detail)

    try:
        await _exchange_code(s, value)
        await _ai_accounts(s)
        return {
            "environment": "TESTNET",
            "status": "AUTHORIZED",
            "mode": "AUTHORIZATION_CODE",
            "message": "Bybit authorization code exchanged successfully. Choose an existing AI sub-account.",
        }
    except HTTPException as exc:
        s["status"] = "WAITING_FOR_AUTHORIZATION"
        s.pop("access_token", None)
        s.pop("refresh_token", None)
        detail = (
            "Bybit rejected the manual value both as an access token and as the current PKCE authorization code. "
            f"Bearer check: {bearer_error}. Code exchange: {exc.detail}"
        )
        s["error"] = detail[:600]
        raise HTTPException(502, detail[:600])


@router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(code: str | None = Query(None), state: str | None = Query(None), error: str | None = Query(None)):
    _cleanup()
    match = next((s for s in _sessions.values() if secrets.compare_digest(s["state"], state or "")), None)
    if not match:
        return HTMLResponse("<h2>ATLAS authorization failed</h2><p>Invalid or expired OAuth state. Return to ATLAS and start again.</p>", status_code=403)
    if error or not code:
        match["status"] = "FAILED"
        match["error"] = error or "authorization_failed"
        return HTMLResponse("<h2>Bybit authorization was not completed</h2><p>You can close this tab and return to ATLAS.</p>", status_code=400)
    try:
        await _exchange_code(match, code)
        return HTMLResponse("<h2>Bybit Testnet authorized</h2><p>Return to ATLAS MARKETS to choose the AI sub-account. You can close this tab.</p>")
    except HTTPException as exc:
        match["status"] = "FAILED"
        match["error"] = str(exc.detail)[:300]
        return HTMLResponse(f"<h2>ATLAS authorization failed</h2><p>{str(exc.detail)[:240]}</p>", status_code=502)


@router.get("/status/{session_id}")
async def oauth_status(session_id: str, user: User = Depends(get_current_user)):
    s = _session(session_id, user)
    result: dict[str, Any] = {"environment": "TESTNET", "status": s["status"]}
    if s["status"] == "FAILED":
        result["error"] = s.get("error")
    if s["status"] == "AUTHORIZED":
        raw = await _ai_accounts(s)
        accounts = raw if isinstance(raw, list) else raw.get("accounts", []) if isinstance(raw, dict) else []
        result["accounts"] = [
            {
                "sub_member_id": str(a.get("sub_member_id")),
                "nickname": a.get("nickname") or a.get("username") or "AI sub-account",
            }
            for a in accounts
        ]
        result["can_create"] = len(accounts) < 5
        result["status"] = "SELECT_ACCOUNT"
    return result


@router.post("/select")
async def select_ai_account(payload: OAuthSelect, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _session(payload.session_id, user)
    if s.get("status") != "AUTHORIZED":
        raise HTTPException(409, "OAuth authorization is not ready")
    if payload.create_new == bool(payload.sub_member_id):
        raise HTTPException(400, "Choose one existing AI sub-account or choose create new")
    query = "?is_create=true" if payload.create_new else f"?sub_member_id={payload.sub_member_id}"
    acct = await _ai_accounts(s, query)
    if isinstance(acct, list):
        acct = acct[0] if len(acct) == 1 else None
    if isinstance(acct, dict) and "accounts" in acct:
        rows = acct.get("accounts") or []
        acct = rows[0] if len(rows) == 1 else None
    if not isinstance(acct, dict) or not acct.get("api_key") or not acct.get("api_secret"):
        raise HTTPException(502, "Bybit did not return API credentials for the selected AI sub-account")
    sub_id = str(acct.get("sub_member_id") or payload.sub_member_id or "").strip() or None
    client = BybitPrivateClient(
        acct["api_key"], acct["api_secret"], TESTNET_TRADING_BASE, get_settings().market_data_timeout_seconds
    )
    wallet = await client.wallet()
    wallet_row = (wallet.get("list") or [{}])[0]
    profile_payload = BrokerProfileCreate(
        account_label=s["account_label"], provider="BYBIT", environment="TESTNET", external_account_ref=sub_id
    )
    p = _new_profile(db, user, profile_payload, sub_id)
    _save_creds(p, acct["api_key"], acct["api_secret"])
    p.last_connection_status = "CONNECTED"
    p.credentials_configured = True
    p.equity_usd = float(wallet_row.get("totalEquity") or 0)
    p.wallet_balance_usd = float(wallet_row.get("totalWalletBalance") or 0)
    p.available_balance_usd = float(wallet_row.get("totalAvailableBalance") or 0)
    if payload.activate:
        db.execute(
            update(BrokerProfile)
            .where(BrokerProfile.user_id == p.user_id, BrokerProfile.provider == "BYBIT", BrokerProfile.id != p.id)
            .values(is_active=False)
        )
        p.is_active = True
    db.commit()
    db.refresh(p)
    _sessions.pop(payload.session_id, None)
    return {
        "connected": True,
        "environment": "TESTNET",
        "profile_id": str(p.id),
        "account_label": p.account_label,
        "external_account_ref": p.external_account_ref,
        "equity": p.equity_usd,
        "message": "Bybit Testnet AI sub-account authorized, verified and connected to ATLAS.",
    }
