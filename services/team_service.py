from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.team_models import Team, TeamMember, TeamRole
from app.models.user_models import User
from app.schemas.team_schemas import TeamCreate, TeamMemberCreate, TeamMemberUpdate, TeamOut, TeamUpdate
from app.services.access import ensure_team_admin, ensure_team_member, get_team_or_404, get_user_or_404


def _team_to_out(team: Team) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        created_at=team.created_at,
        subscription_expiry=team.subscription_expiry,
        is_active=team.is_active,
        subscription_valid=team.is_subscription_valid(),
    )


def create_team(db: Session, user: User, data: TeamCreate) -> TeamOut:
    team = Team(name=data.name)
    db.add(team)
    db.flush()

    membership = TeamMember(team_id=team.id, user_id=user.id, role=TeamRole.OWNER)
    db.add(membership)

    # Create default project and lists to enable instant task management
    from app.models.project_models import Project, ProjectList
    default_project = Project(
        team_id=team.id,
        name="پروژه عمومی",
        description="پروژه پیش‌فرض تیم برای مدیریت تسک‌ها",
    )
    db.add(default_project)
    db.flush()

    default_lists = [
        ProjectList(project_id=default_project.id, name="انجام نشده", position=0),
        ProjectList(project_id=default_project.id, name="در حال انجام", position=1),
        ProjectList(project_id=default_project.id, name="انجام شده", position=2),
    ]
    db.add_all(default_lists)

    db.commit()
    db.refresh(team)
    return _team_to_out(team)


def get_team(db: Session, team_id: str, user: User) -> TeamOut:
    team = get_team_or_404(db, team_id)
    ensure_team_member(db, team_id, user)
    return _team_to_out(team)


def list_teams(db: Session, user: User, limit: int = 50, offset: int = 0) -> list[TeamOut]:
    teams = (
        db.query(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(TeamMember.user_id == user.id)
        .order_by(Team.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_team_to_out(team) for team in teams]


def update_team(db: Session, team_id: str, user: User, data: TeamUpdate) -> TeamOut | None:
    team = get_team_or_404(db, team_id)
    ensure_team_admin(db, team_id, user)

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(team, key, value)
    db.commit()
    db.refresh(team)
    return _team_to_out(team)


def delete_team(db: Session, team_id: str, user: User) -> bool:
    team = get_team_or_404(db, team_id)
    membership = ensure_team_admin(db, team_id, user)
    if membership.role != TeamRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team owner can delete the team",
        )
    db.delete(team)
    db.commit()
    return True


def add_member(db: Session, team_id: str, user: User, data: TeamMemberCreate) -> TeamMember:
    get_team_or_404(db, team_id)
    ensure_team_admin(db, team_id, user)
    get_user_or_404(db, data.user_id)

    existing = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == data.user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a team member")

    member = TeamMember(team_id=team_id, user_id=data.user_id, role=data.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def list_members(db: Session, team_id: str, user: User) -> list[TeamMember]:
    ensure_team_member(db, team_id, user)
    return db.query(TeamMember).filter(TeamMember.team_id == team_id).order_by(TeamMember.id).all()


def update_member(
    db: Session,
    team_id: str,
    member_id: str,
    user: User,
    data: TeamMemberUpdate,
) -> TeamMember | None:
    ensure_team_admin(db, team_id, user)
    member = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.team_id == team_id).first()
    if not member:
        return None
    if member.role == TeamRole.OWNER and data.role != TeamRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change owner role directly",
        )
    member.role = data.role
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, team_id: str, member_id: str, user: User) -> bool:
    ensure_team_admin(db, team_id, user)
    member = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.team_id == team_id).first()
    if not member:
        return False
    if member.role == TeamRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove team owner",
        )
    db.delete(member)
    db.commit()
    return True
