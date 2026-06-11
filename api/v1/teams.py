from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user_models import User
from app.schemas.team_schemas import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberOut,
    TeamMemberUpdate,
    TeamOut,
    TeamUpdate,
)
from app.services import team_service

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.post("", response_model=TeamOut)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return team_service.create_team(db, current_user, payload)


@router.get("", response_model=list[TeamOut])
def list_teams(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return team_service.list_teams(db, current_user, limit=limit, offset=offset)


@router.get("/{team_id}", response_model=TeamOut)
def get_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return team_service.get_team(db, team_id, current_user)


@router.patch("/{team_id}", response_model=TeamOut)
def update_team(
    team_id: str,
    payload: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    team = team_service.update_team(db, team_id, current_user, payload)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.delete("/{team_id}")
def delete_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = team_service.delete_team(db, team_id, current_user)
    if not ok:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"ok": True}


@router.post("/{team_id}/members", response_model=TeamMemberOut)
def add_member(
    team_id: str,
    payload: TeamMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return team_service.add_member(db, team_id, current_user, payload)


@router.get("/{team_id}/members", response_model=list[TeamMemberOut])
def list_members(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return team_service.list_members(db, team_id, current_user)


@router.patch("/{team_id}/members/{member_id}", response_model=TeamMemberOut)
def update_member(
    team_id: str,
    member_id: str,
    payload: TeamMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = team_service.update_member(db, team_id, member_id, current_user, payload)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.delete("/{team_id}/members/{member_id}")
def remove_member(
    team_id: str,
    member_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = team_service.remove_member(db, team_id, member_id, current_user)
    if not ok:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}
