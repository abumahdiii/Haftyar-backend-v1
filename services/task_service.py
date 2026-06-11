from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.task_models import Task, TaskAssignee, TaskComment
from app.models.user_models import User
from app.schemas.task_schemas import (
    TaskAssigneeCreate,
    TaskCommentCreate,
    TaskCreate,
    TaskUpdate,
)
from app.services.access import (
    ensure_list_belongs_to_project,
    ensure_project_access,
    get_list_or_404,
    get_task_or_404,
    get_user_or_404,
)


def _validate_task_refs(db: Session, project_id: str, list_id: str) -> None:
    project_list = get_list_or_404(db, list_id)
    ensure_list_belongs_to_project(project_list, project_id)


def create_task(db: Session, user: User, data: TaskCreate) -> Task:
    ensure_project_access(db, data.project_id, user)
    _validate_task_refs(db, data.project_id, data.list_id)

    task = Task(**data.model_dump(), creator_id=user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: str, user: User) -> Task:
    task = get_task_or_404(db, task_id)
    ensure_project_access(db, task.project_id, user)
    return task


def list_tasks(
    db: Session,
    user: User,
    project_id: str | None = None,
    list_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Task]:
    query = db.query(Task)

    if project_id is not None:
        ensure_project_access(db, project_id, user)
        query = query.filter(Task.project_id == project_id)

    if list_id is not None:
        project_list = get_list_or_404(db, list_id)
        if project_id is not None:
            ensure_list_belongs_to_project(project_list, project_id)
        else:
            ensure_project_access(db, project_list.project_id, user)
            query = query.filter(Task.project_id == project_list.project_id)
        query = query.filter(Task.list_id == list_id)

    if project_id is None and list_id is None:
        from app.models.project_models import Project
        from app.models.team_models import TeamMember

        accessible_project_ids = (
            db.query(Project.id)
            .join(TeamMember, TeamMember.team_id == Project.team_id)
            .filter(TeamMember.user_id == user.id)
            .subquery()
        )
        query = query.filter(Task.project_id.in_(accessible_project_ids))

    return query.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()


def update_task(db: Session, task_id: str, user: User, data: TaskUpdate) -> Task | None:
    task = get_task_or_404(db, task_id)
    ensure_project_access(db, task.project_id, user)

    updates = data.model_dump(exclude_unset=True)
    new_list_id = updates.get("list_id", task.list_id)
    if "list_id" in updates:
        _validate_task_refs(db, task.project_id, new_list_id)

    for key, value in updates.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: str, user: User) -> bool:
    task = get_task_or_404(db, task_id)
    ensure_project_access(db, task.project_id, user)
    db.delete(task)
    db.commit()
    return True


def add_assignee(db: Session, task_id: str, user: User, data: TaskAssigneeCreate) -> TaskAssignee:
    task = get_task_or_404(db, task_id)
    ensure_project_access(db, task.project_id, user)
    get_user_or_404(db, data.user_id)

    existing = (
        db.query(TaskAssignee)
        .filter(TaskAssignee.task_id == task_id, TaskAssignee.user_id == data.user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already assigned")

    assignee = TaskAssignee(task_id=task_id, user_id=data.user_id)
    db.add(assignee)
    db.commit()
    db.refresh(assignee)
    return assignee


def list_assignees(db: Session, task_id: str, user: User) -> list[TaskAssignee]:
    task = get_task_or_404(db, task_id)
    ensure_project_access(db, task.project_id, user)
    return db.query(TaskAssignee).filter(TaskAssignee.task_id == task_id).all()


def remove_assignee(db: Session, task_id: str, assignee_id: str, user: User) -> bool:
    task = get_task_or_404(db, task_id)
    ensure_project_access(db, task.project_id, user)

    assignee = (
        db.query(TaskAssignee)
        .filter(TaskAssignee.id == assignee_id, TaskAssignee.task_id == task_id)
        .first()
    )
    if not assignee:
        return False
    db.delete(assignee)
    db.commit()
    return True


def add_comment(db: Session, task_id: str, user: User, data: TaskCommentCreate) -> TaskComment:
    task = get_task_or_404(db, task_id)
    ensure_project_access(db, task.project_id, user)

    comment = TaskComment(task_id=task_id, user_id=user.id, **data.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, task_id: str, user: User) -> list[TaskComment]:
    task = get_task_or_404(db, task_id)
    ensure_project_access(db, task.project_id, user)
    return (
        db.query(TaskComment)
        .filter(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at)
        .all()
    )
