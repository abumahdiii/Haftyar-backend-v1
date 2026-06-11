from datetime import datetime
from pydantic import BaseModel, Field


class InternalMessage(BaseModel):
    user_id: str = Field(..., description="Unique user ID from the messaging platform")
    message_text: str = Field(..., description="Raw text of the message")
    message_id: str | None = Field(None, description="Optional message identifier for idempotency")
    timestamp: datetime = Field(..., description="Time the message was sent")
    platform: str = Field(..., description="Platform identifier: 'bale' | 'telegram'")
    raw_payload: dict = Field(..., description="Raw webhook payload for logging or future parsing")
    contact_phone: str | None = Field(None, description="Normalized phone number if contact shared")
    callback_query_id: str | None = Field(None, description="Telegram callback query ID if button clicked")
    shared_user_id: str | None = Field(None, description="Telegram user ID shared via KeyboardButtonRequestUsers")

