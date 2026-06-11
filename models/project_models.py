from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.ids import new_list_id, new_project_id
from app.database.base import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(32), primary_key=True, default=new_project_id)
    team_id = Column(String(32), ForeignKey("teams.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="projects")
    lists = relationship("ProjectList", back_populates="project", cascade="all, delete-orphan")


class ProjectList(Base):
    __tablename__ = "project_lists"

    id = Column(String(32), primary_key=True, default=new_list_id)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="lists")
