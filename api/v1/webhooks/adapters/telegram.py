from datetime import datetime, timezone
from app.api.v1.webhooks.adapters.base import BaseAdapter
from app.api.v1.webhooks.schemas import InternalMessage


class TelegramAdapter(BaseAdapter):
    def parse(self, payload: dict) -> InternalMessage:
        message_data = payload.get("message") or payload.get("edited_message")
        if not message_data:
            raise ValueError("No message or edited_message found in Telegram payload")

        from_user = message_data.get("from")
        if not from_user:
            raise ValueError("No sender information found in Telegram message")
        user_id = str(from_user.get("id"))

        message_id = str(message_data.get("message_id"))
        text = message_data.get("text", "")

        date_val = message_data.get("date")
        if date_val:
            timestamp = datetime.fromtimestamp(date_val, tz=timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        contact = message_data.get("contact")
        contact_phone = None
        if contact:
            contact_user_id = str(contact.get("user_id"))
            if contact_user_id == user_id:
                contact_phone = contact.get("phone_number")

        return InternalMessage(
            user_id=user_id,
            message_text=text,
            message_id=message_id,
            timestamp=timestamp,
            platform="telegram",
            raw_payload=payload,
            contact_phone=contact_phone,
        )
