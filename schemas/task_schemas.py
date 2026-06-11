from datetime import datetime

from pydantic import BaseModel, Field

from app.models.task_models import TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    due_date: datetime | None = None
    priority: int = 0
    list_id: str
    project_id: str


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    due_date: datetime | None = None
    priority: int | None = None
    list_id: str | None = None


class TaskOut(BaseModel):
    id: str
    title: str
    description: str | None
    status: TaskStatus
    due_date: datetime | None
    priority: int
    list_id: str
    project_id: str
    creator_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskAssigneeCreate(BaseModel):
    user_id: str


class TaskAssigneeOut(BaseModel):
    id: str
    task_id: str
    user_id: str

    model_config = {"from_attributes": True}


class TaskCommentCreate(BaseModel):
    content: str = Field(min_length=1)
    media_url: str | None = None
    media_type: str | None = None


class TaskCommentOut(BaseModel):
    id: str
    task_id: str
    user_id: str
    content: str
    media_url: str | None
    media_type: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
