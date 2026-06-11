from datetime import datetime

from pydantic import BaseModel, Field

from app.models.team_models import TeamRole


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class TeamOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    subscription_expiry: datetime
    is_active: bool
    subscription_valid: bool

    model_config = {"from_attributes": True}


class TeamMemberCreate(BaseModel):
    user_id: str
    role: TeamRole = TeamRole.MEMBER


class TeamMemberUpdate(BaseModel):
    role: TeamRole


class TeamMemberOut(BaseModel):
    id: str
    team_id: str
    user_id: str
    role: TeamRole

    model_config = {"from_attributes": True}
