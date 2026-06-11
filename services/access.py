from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project_models import Project, ProjectList
from app.models.task_models import Task
from app.models.team_models import Team, TeamMember, TeamRole
from app.models.user_models import User


def get_team_or_404(db: Session, team_id: str) -> Team:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def ensure_team_subscription_valid(team: Team) -> None:
    if not team.is_subscription_valid():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team subscription is expired or inactive",
        )


def get_membership(db: Session, team_id: str, user_id: str) -> TeamMember | None:
    return (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        .first()
    )


def ensure_team_member(db: Session, team_id: str, user: User) -> TeamMember:
    membership = get_membership(db, team_id, user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this team",
        )
    return membership


def ensure_team_admin(db: Session, team_id: str, user: User) -> TeamMember:
    membership = ensure_team_member(db, team_id, user)
    if membership.role not in (TeamRole.OWNER, TeamRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return membership


def get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def ensure_project_access(db: Session, project_id: str, user: User) -> Project:
    project = get_project_or_404(db, project_id)
    team = get_team_or_404(db, project.team_id)
    ensure_team_subscription_valid(team)
    ensure_team_member(db, project.team_id, user)
    return project


def get_list_or_404(db: Session, list_id: str) -> ProjectList:
    project_list = db.query(ProjectList).filter(ProjectList.id == list_id).first()
    if not project_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")
    return project_list


def ensure_list_belongs_to_project(project_list: ProjectList, project_id: str) -> None:
    if project_list.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="List does not belong to the specified project",
        )


def get_task_or_404(db: Session, task_id: str) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def get_user_or_404(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
