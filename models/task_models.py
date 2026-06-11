import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.ids import new_assignee_id, new_comment_id, new_task_id
from app.database.base import Base


class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(32), primary_key=True, default=new_task_id)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus, name="task_status_enum"), default=TaskStatus.TODO)
    due_date = Column(DateTime, nullable=True)
    priority = Column(Integer, default=0)
    list_id = Column(String(32), ForeignKey("project_lists.id"), nullable=False)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    creator_id = Column(String(32), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assignees = relationship("TaskAssignee", back_populates="task", cascade="all, delete-orphan")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")


class TaskAssignee(Base):
    __tablename__ = "task_assignees"

    id = Column(String(32), primary_key=True, default=new_assignee_id)
    task_id = Column(String(32), ForeignKey("tasks.id"), nullable=False)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False)

    task = relationship("Task", back_populates="assignees")
    user = relationship("User", back_populates="tasks_assigned")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(String(32), primary_key=True, default=new_comment_id)
    task_id = Column(String(32), ForeignKey("tasks.id"), nullable=False)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    media_url = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="comments")
