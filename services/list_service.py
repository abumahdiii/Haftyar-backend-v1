from sqlalchemy.orm import Session

from app.models.project_models import ProjectList
from app.models.user_models import User
from app.schemas.list_schemas import ListCreate, ListUpdate
from app.services.access import ensure_project_access, ensure_team_admin


def create_list(db: Session, project_id: str, user: User, data: ListCreate) -> ProjectList:
    project = ensure_project_access(db, project_id, user)
    ensure_team_admin(db, project.team_id, user)

    project_list = ProjectList(project_id=project_id, **data.model_dump())
    db.add(project_list)
    db.commit()
    db.refresh(project_list)
    return project_list


def get_list(db: Session, project_id: str, list_id: str, user: User) -> ProjectList | None:
    ensure_project_access(db, project_id, user)
    project_list = (
        db.query(ProjectList)
        .filter(ProjectList.id == list_id, ProjectList.project_id == project_id)
        .first()
    )
    return project_list


def list_lists(db: Session, project_id: str, user: User) -> list[ProjectList]:
    ensure_project_access(db, project_id, user)
    return (
        db.query(ProjectList)
        .filter(ProjectList.project_id == project_id)
        .order_by(ProjectList.position, ProjectList.created_at)
        .all()
    )


def update_list(
    db: Session,
    project_id: str,
    list_id: str,
    user: User,
    data: ListUpdate,
) -> ProjectList | None:
    project = ensure_project_access(db, project_id, user)
    ensure_team_admin(db, project.team_id, user)

    project_list = (
        db.query(ProjectList)
        .filter(ProjectList.id == list_id, ProjectList.project_id == project_id)
        .first()
    )
    if not project_list:
        return None

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(project_list, key, value)
    db.commit()
    db.refresh(project_list)
    return project_list


def delete_list(db: Session, project_id: str, list_id: str, user: User) -> bool:
    project = ensure_project_access(db, project_id, user)
    ensure_team_admin(db, project.team_id, user)

    project_list = (
        db.query(ProjectList)
        .filter(ProjectList.id == list_id, ProjectList.project_id == project_id)
        .first()
    )
    if not project_list:
        return False
    db.delete(project_list)
    db.commit()
    return True
