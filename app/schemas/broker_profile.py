import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BrokerProfileCreate(BaseModel):
    account_label: str = Field(min_length=2, max_length=96)
    provider: Literal["BYBIT"] = "BYBIT"
    environment: Literal["DEMO", "TESTNET"] = "DEMO"
    external_account_ref: str | None = Field(default=None, max_length=128)
    owner_user_id: uuid.UUID | None = None


class BrokerProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    account_label: str
    environment: str
    external_account_ref: str | None
    is_enabled: bool
    last_connection_status: str
    last_connection_test_at: datetime | None
    created_at: datetime
