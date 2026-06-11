from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.phone import normalize_phone
from app.core.security import PASSWORD_PROVIDER, PHONE_PROVIDER
from app.models.user_models import User, UserAccount
from app.schemas.user_schemas import UserAccountCreate, UserCreate, UserUpdate


def get_user(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def list_users(db: Session, limit: int = 50, offset: int = 0) -> list[User]:
    return db.query(User).order_by(User.created_at).offset(offset).limit(limit).all()


def create_user(db: Session, data: UserCreate) -> User:
    if data.email and db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    if data.username and db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = User(**data.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: str, data: UserUpdate) -> User | None:
    user = get_user(db, user_id)
    if not user:
        return None

    updates = data.model_dump(exclude_unset=True)
    if "phone" in updates and updates["phone"] is not None:
        try:
            updates["phone"] = normalize_phone(updates["phone"])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if updates["phone"] != user.phone:
            if db.query(User).filter(User.phone == updates["phone"]).first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already exists")
    if "email" in updates and updates["email"] != user.email:
        if db.query(User).filter(User.email == updates["email"]).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    if "username" in updates and updates["username"] != user.username:
        if db.query(User).filter(User.username == updates["username"]).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    for key, value in updates.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: str) -> bool:
    user = get_user(db, user_id)
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


def add_user_account(db: Session, user_id: str, data: UserAccountCreate) -> UserAccount:
    if data.provider in (PASSWORD_PROVIDER, PHONE_PROVIDER):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account type cannot be linked through this endpoint",
        )

    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = (
        db.query(UserAccount)
        .filter(
            UserAccount.provider == data.provider,
            UserAccount.provider_id == data.provider_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already linked to another user",
        )

    account = UserAccount(user_id=user_id, **data.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_user_accounts(db: Session, user_id: str) -> list[UserAccount]:
    return (
        db.query(UserAccount)
        .filter(
            UserAccount.user_id == user_id,
            UserAccount.provider.notin_([PASSWORD_PROVIDER, PHONE_PROVIDER]),
        )
        .all()
    )
