from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.auth_schemas import (
    SendOtpRequest,
    SendOtpResponse,
    TokenResponse,
    VerifyOtpRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register/send-otp", response_model=SendOtpResponse)
def send_register_otp(payload: SendOtpRequest, db: Session = Depends(get_db)):
    return auth_service.send_register_otp(db, payload)


@router.post("/register/verify-otp", response_model=TokenResponse)
def verify_register_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    return auth_service.verify_register_otp(db, payload)


@router.post("/login/send-otp", response_model=SendOtpResponse)
def send_login_otp(payload: SendOtpRequest, db: Session = Depends(get_db)):
    return auth_service.send_login_otp(db, payload)


@router.post("/login/verify-otp", response_model=TokenResponse)
def verify_login_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    return auth_service.verify_login_otp(db, payload)
