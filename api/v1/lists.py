from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user_models import User
from app.schemas.list_schemas import ListCreate, ListOut, ListUpdate
from app.services import list_service

router = APIRouter(tags=["Lists"])


@router.post("/projects/{project_id}/lists", response_model=ListOut)
def create_list(
    project_id: str,
    payload: ListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_service.create_list(db, project_id, current_user, payload)


@router.get("/projects/{project_id}/lists", response_model=list[ListOut])
def list_lists(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_service.list_lists(db, project_id, current_user)


@router.get("/projects/{project_id}/lists/{list_id}", response_model=ListOut)
def get_list(
    project_id: str,
    list_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_list = list_service.get_list(db, project_id, list_id, current_user)
    if not project_list:
        raise HTTPException(status_code=404, detail="List not found")
    return project_list


@router.patch("/projects/{project_id}/lists/{list_id}", response_model=ListOut)
def update_list(
    project_id: str,
    list_id: str,
    payload: ListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_list = list_service.update_list(db, project_id, list_id, current_user, payload)
    if not project_list:
        raise HTTPException(status_code=404, detail="List not found")
    return project_list


@router.delete("/projects/{project_id}/lists/{list_id}")
def delete_list(
    project_id: str,
    list_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = list_service.delete_list(db, project_id, list_id, current_user)
    if not ok:
        raise HTTPException(status_code=404, detail="List not found")
    return {"ok": True}
