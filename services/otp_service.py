import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.otp_models import OtpPurpose, OtpVerification
from app.services.sms_service import send_otp_sms


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def send_otp(db: Session, phone: str, purpose: OtpPurpose) -> dict:
    latest = (
        db.query(OtpVerification)
        .filter(OtpVerification.phone == phone, OtpVerification.purpose == purpose)
        .order_by(OtpVerification.id.desc())
        .first()
    )
    if latest:
        elapsed = (datetime.utcnow() - latest.created_at).total_seconds()
        if elapsed < settings.OTP_RESEND_SECONDS:
            remaining = int(settings.OTP_RESEND_SECONDS - elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting a new code",
            )

    db.query(OtpVerification).filter(
        OtpVerification.phone == phone,
        OtpVerification.purpose == purpose,
    ).delete()

    code = _generate_code()
    otp = OtpVerification(
        phone=phone,
        code_hash=hash_password(code),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(otp)
    db.commit()

    try:
        send_otp_sms(phone, code)
    except Exception as exc:
        db.delete(otp)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send SMS",
        ) from exc

    response = {
        "message": "Verification code sent",
        "expires_in_seconds": settings.OTP_EXPIRE_MINUTES * 60,
    }
    if settings.ENV == "dev" and settings.SMS_PROVIDER == "console":
        response["dev_code"] = code
    return response


def verify_otp(db: Session, phone: str, code: str, purpose: OtpPurpose) -> None:
    otp = (
        db.query(OtpVerification)
        .filter(OtpVerification.phone == phone, OtpVerification.purpose == purpose)
        .order_by(OtpVerification.id.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No verification code found")

    if otp.expires_at < datetime.utcnow():
        db.delete(otp)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired")

    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        db.delete(otp)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many failed attempts")

    if not verify_password(code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    db.delete(otp)
    db.commit()
