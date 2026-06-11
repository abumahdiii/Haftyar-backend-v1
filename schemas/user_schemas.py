from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: EmailStr


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=50)
    email: EmailStr | None = None
    phone: str | None = None


class UserOut(BaseModel):
    id: str
    username: str | None
    email: str | None
    phone: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserAccountCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=50)
    provider_id: str = Field(min_length=1, max_length=255)


class UserAccountOut(BaseModel):
    id: str
    user_id: str
    provider: str
    provider_id: str

    model_config = {"from_attributes": True}
