import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
Provider = Literal["BYBIT", "MT5", "IBKR", "TWELVE_DATA", "ATLAS_PAPER"]
Environment = Literal["PAPER", "DEMO", "TESTNET", "LIVE"]
class BrokerProfileCreate(BaseModel):
    account_label: str = Field(min_length=2, max_length=96)
    provider: Provider = "ATLAS_PAPER"
    environment: Environment = "PAPER"
    external_account_ref: str | None = Field(default=None, max_length=128)
    owner_user_id: uuid.UUID | None = None
class BrokerCredentialsUpdate(BaseModel):
    api_key: str | None = Field(default=None, max_length=256)
    api_secret: str | None = Field(default=None, max_length=256)
    credentials: dict[str, Any] | None = None
class BrokerConnectRequest(BrokerProfileCreate):
    api_key: str | None = Field(default=None, max_length=256)
    api_secret: str | None = Field(default=None, max_length=256)
    credentials: dict[str, Any] | None = None
    activate: bool = True
class BrokerConnectResult(BaseModel):
    profile: "BrokerProfilePublic"
    connected: bool
    message: str
    next_action: str | None = None
class LiveExecutionUpdate(BaseModel): enabled: bool
class BrokerProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; user_id: uuid.UUID; provider: str; account_label: str; environment: str; external_account_ref: str | None
    is_enabled: bool; is_active: bool; live_execution_enabled: bool; live_execution_armed_at: datetime | None
    last_connection_status: str; last_connection_test_at: datetime | None; credentials_configured: bool; last_sync_at: datetime | None
    equity_usd: float | None; wallet_balance_usd: float | None; available_balance_usd: float | None
    open_positions_count: int; open_orders_count: int; created_at: datetime
