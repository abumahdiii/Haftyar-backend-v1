from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.ids import new_account_id, new_user_id
from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=new_user_id)
    username = Column(String, unique=True, nullable=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone = Column(String(11), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("UserAccount", back_populates="user", cascade="all, delete-orphan")
    team_memberships = relationship("TeamMember", back_populates="user")
    tasks_assigned = relationship("TaskAssignee", back_populates="user")


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(String(32), primary_key=True, default=new_account_id)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    provider_id = Column(String, nullable=False, index=True)

    user = relationship("User", back_populates="accounts")
