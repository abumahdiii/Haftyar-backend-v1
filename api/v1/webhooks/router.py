import logging
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, status
from app.api.v1.webhooks.adapters import BaleAdapter, TelegramAdapter
from app.api.v1.webhooks.schemas import InternalMessage
from app.services import message_service

logger = logging.getLogger("app.webhooks")

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Adapter registry mapping dynamic platform path parameters to adapter instances
ADAPTERS = {
    "bale": BaleAdapter(),
    "telegram": TelegramAdapter(),
}


async def run_message_processing(message: InternalMessage):
    """
    Background worker task to manage DB session lifecycle and handle exceptions
    during asynchronous webhook message processing.
    """
    from app.database.session import SessionLocal
    db = SessionLocal()
    try:
        await message_service.process_message(message, db)
    except Exception:
        logger.exception("Error during background webhook processing for platform=%s", message.platform)
    finally:
        db.close()


@router.post("/{platform}")
async def handle_webhook(
    platform: str,
    background_tasks: BackgroundTasks,
    payload: dict = Body(...),
):
    platform_lower = platform.lower()
    
    # 1. Validate platform
    if platform_lower not in ADAPTERS:
        logger.warning("Received webhook request for unsupported platform=%s", platform)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook platform '{platform}' is not supported."
        )

    adapter = ADAPTERS[platform_lower]

    # 2. Parse incoming payload
    try:
        message = adapter.parse(payload)
    except Exception as e:
        # Standard messaging platforms (Telegram/Bale) retry requests on non-200 responses.
        # Returning a 200 OK with an ignored status prevents infinite retry loops on invalid formats.
        logger.warning(
            "Failed to parse webhook payload for platform=%s. Error: %s. Payload: %s",
            platform_lower,
            str(e),
            payload
        )
        return {"status": "ignored", "reason": f"Payload parsing failed: {str(e)}"}

    # 3. Schedule asynchronous processing of normalized message
    background_tasks.add_task(run_message_processing, message)

    return {"status": "accepted", "message_id": message.message_id}
