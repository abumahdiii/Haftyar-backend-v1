from datetime import datetime, timezone
from app.api.v1.webhooks.adapters.base import BaseAdapter
from app.api.v1.webhooks.schemas import InternalMessage


class TelegramAdapter(BaseAdapter):
    def parse(self, payload: dict) -> InternalMessage:
        # Check if callback_query exists (inline button clicks)
        callback_query = payload.get("callback_query")
        if callback_query:
            from_user = callback_query.get("from")
            if not from_user:
                raise ValueError("No sender info in Telegram callback_query")
            user_id = str(from_user.get("id"))
            
            callback_id = str(callback_query.get("id"))
            data = callback_query.get("data", "")
            
            # Use callback_query id for idempotency
            return InternalMessage(
                user_id=user_id,
                message_text=f"//callback:{data}",
                message_id=callback_id,
                timestamp=datetime.now(timezone.utc),
                platform="telegram",
                raw_payload=payload,
                contact_phone=None,
                callback_query_id=callback_id,
                shared_user_id=None,
            )

        # Standard message parsing
        message_data = payload.get("message") or payload.get("edited_message")
        if not message_data:
            raise ValueError("No message, edited_message, or callback_query found in Telegram payload")

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

        # Parse user_shared / users_shared (selecting contact from chat list)
        shared_user_id = None
        user_shared = message_data.get("user_shared")
        users_shared = message_data.get("users_shared")
        if user_shared:
            shared_user_id = str(user_shared.get("user_id"))
        elif users_shared:
            user_ids = users_shared.get("user_ids")
            if user_ids:
                shared_user_id = str(user_ids[0])

        return InternalMessage(
            user_id=user_id,
            message_text=text,
            message_id=message_id,
            timestamp=timestamp,
            platform="telegram",
            raw_payload=payload,
            contact_phone=contact_phone,
            callback_query_id=None,
            shared_user_id=shared_user_id,
        )

