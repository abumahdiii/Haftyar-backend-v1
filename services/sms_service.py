import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_otp_sms(phone: str, code: str) -> None:
    message = f"Hafte-Yar code: {code}"

    if settings.SMS_PROVIDER == "kavenegar":
        _send_kavenegar(phone, code, message)
        return

    logger.info("OTP SMS [%s] -> %s: %s", settings.SMS_PROVIDER, phone, code)
    print(f"[SMS] {phone}: {code}")


def _send_kavenegar(phone: str, code: str, message: str) -> None:
    if not settings.SMS_API_KEY:
        raise RuntimeError("SMS_API_KEY is required for kavenegar provider")

    if settings.SMS_TEMPLATE:
        url = f"https://api.kavenegar.com/v1/{settings.SMS_API_KEY}/verify/lookup.json"
        params = {"receptor": phone, "token": code, "template": settings.SMS_TEMPLATE}
    else:
        url = f"https://api.kavenegar.com/v1/{settings.SMS_API_KEY}/sms/send.json"
        params = {"receptor": phone, "message": message}

    response = httpx.get(url, params=params, timeout=15.0)
    response.raise_for_status()
    payload = response.json()
    if payload.get("return", {}).get("status") != 200:
        raise RuntimeError(f"Kavenegar SMS failed: {payload}")
