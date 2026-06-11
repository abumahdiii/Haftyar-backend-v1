from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user_models import User
from app.schemas.project_schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import project_service

router = APIRouter(tags=["Projects"])


@router.post("/teams/{team_id}/projects", response_model=ProjectOut)
def create_project(
    team_id: str,
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return project_service.create_project(db, team_id, current_user, payload)


@router.get("/teams/{team_id}/projects", response_model=list[ProjectOut])
def list_projects(
    team_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return project_service.list_projects(db, team_id, current_user, limit=limit, offset=offset)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return project_service.get_project(db, project_id, current_user)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = project_service.update_project(db, project_id, current_user, payload)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = project_service.delete_project(db, project_id, current_user)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}
