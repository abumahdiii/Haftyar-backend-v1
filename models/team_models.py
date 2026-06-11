import enum
from datetime import datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.ids import new_member_id, new_team_id
from app.database.base import Base


class TeamRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(32), primary_key=True, default=new_team_id)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    subscription_expiry = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))
    is_active = Column(Boolean, default=True)

    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="team", cascade="all, delete-orphan")

    def is_subscription_valid(self):
        return datetime.utcnow() < self.subscription_expiry and self.is_active


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(String(32), primary_key=True, default=new_member_id)
    team_id = Column(String(32), ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(Enum(TeamRole, name="teamrole"), default=TeamRole.MEMBER)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")
