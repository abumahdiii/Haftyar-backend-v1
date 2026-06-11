from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import PHONE_PROVIDER, create_access_token
from app.models.otp_models import OtpPurpose
from app.models.user_models import User, UserAccount
from app.schemas.auth_schemas import SendOtpRequest, SendOtpResponse, TokenResponse, VerifyOtpRequest
from app.services import otp_service


def send_register_otp(db: Session, data: SendOtpRequest) -> SendOtpResponse:
    if db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already registered",
        )

    result = otp_service.send_otp(db, data.phone, OtpPurpose.REGISTER)
    return SendOtpResponse(**result)


def send_login_otp(db: Session, data: SendOtpRequest) -> SendOtpResponse:
    if not db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not registered",
        )

    result = otp_service.send_otp(db, data.phone, OtpPurpose.LOGIN)
    return SendOtpResponse(**result)


def verify_register_otp(db: Session, data: VerifyOtpRequest) -> TokenResponse:
    if db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already registered",
        )

    otp_service.verify_otp(db, data.phone, data.code, OtpPurpose.REGISTER)

    user = User(phone=data.phone, username=f"user_{data.phone}")
    db.add(user)
    db.flush()

    account = UserAccount(
        user_id=user.id,
        provider=PHONE_PROVIDER,
        provider_id=data.phone,
    )
    db.add(account)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id), is_new_user=True)


def verify_login_otp(db: Session, data: VerifyOtpRequest) -> TokenResponse:
    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not registered",
        )

    otp_service.verify_otp(db, data.phone, data.code, OtpPurpose.LOGIN)
    return TokenResponse(access_token=create_access_token(user.id), is_new_user=False)
