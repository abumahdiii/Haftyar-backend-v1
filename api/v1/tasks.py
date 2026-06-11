from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user_models import User
from app.schemas.task_schemas import (
    TaskAssigneeCreate,
    TaskAssigneeOut,
    TaskCommentCreate,
    TaskCommentOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", response_model=TaskOut)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.create_task(db, current_user, payload)


@router.get("", response_model=list[TaskOut])
def list_tasks(
    project_id: str | None = None,
    list_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.list_tasks(
        db,
        current_user,
        project_id=project_id,
        list_id=list_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.get_task(db, task_id, current_user)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = task_service.update_task(db, task_id, current_user, payload)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = task_service.delete_task(db, task_id, current_user)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}


@router.post("/{task_id}/assignees", response_model=TaskAssigneeOut)
def add_assignee(
    task_id: str,
    payload: TaskAssigneeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.add_assignee(db, task_id, current_user, payload)


@router.get("/{task_id}/assignees", response_model=list[TaskAssigneeOut])
def list_assignees(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.list_assignees(db, task_id, current_user)


@router.delete("/{task_id}/assignees/{assignee_id}")
def remove_assignee(
    task_id: str,
    assignee_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = task_service.remove_assignee(db, task_id, assignee_id, current_user)
    if not ok:
        raise HTTPException(status_code=404, detail="Assignee not found")
    return {"ok": True}


@router.post("/{task_id}/comments", response_model=TaskCommentOut)
def add_comment(
    task_id: str,
    payload: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.add_comment(db, task_id, current_user, payload)


@router.get("/{task_id}/comments", response_model=list[TaskCommentOut])
def list_comments(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.list_comments(db, task_id, current_user)
