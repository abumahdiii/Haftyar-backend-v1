from sqlalchemy.orm import Session

from app.models.project_models import Project
from app.models.user_models import User
from app.schemas.project_schemas import ProjectCreate, ProjectUpdate
from app.services.access import ensure_project_access, ensure_team_admin, ensure_team_subscription_valid, get_team_or_404


def create_project(db: Session, team_id: str, user: User, data: ProjectCreate) -> Project:
    team = get_team_or_404(db, team_id)
    ensure_team_subscription_valid(team)
    ensure_team_admin(db, team_id, user)

    project = Project(team_id=team_id, **data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: str, user: User) -> Project:
    return ensure_project_access(db, project_id, user)


def list_projects(
    db: Session,
    team_id: str,
    user: User,
    limit: int = 50,
    offset: int = 0,
) -> list[Project]:
    team = get_team_or_404(db, team_id)
    ensure_team_subscription_valid(team)
    from app.services.access import ensure_team_member

    ensure_team_member(db, team_id, user)
    return (
        db.query(Project)
        .filter(Project.team_id == team_id)
        .order_by(Project.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def update_project(db: Session, project_id: str, user: User, data: ProjectUpdate) -> Project | None:
    project = ensure_project_access(db, project_id, user)
    ensure_team_admin(db, project.team_id, user)

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: str, user: User) -> bool:
    project = ensure_project_access(db, project_id, user)
    ensure_team_admin(db, project.team_id, user)
    db.delete(project)
    db.commit()
    return True
