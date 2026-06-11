import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String

from app.database.base import Base


class OtpPurpose(str, enum.Enum):
    REGISTER = "REGISTER"
    LOGIN = "LOGIN"


class OtpVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(11), nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    purpose = Column(Enum(OtpPurpose, name="otp_purpose_enum"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
