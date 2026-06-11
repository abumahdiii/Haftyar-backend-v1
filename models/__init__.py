# app/models/__init__.py

# ابتدا Base را ایمپورت کن تا همه مدل‌ها به آن متصل شوند
from app.database.base import Base

# ایمپورت مدل‌ها
from .user_models import User, UserAccount
from .otp_models import OtpVerification, OtpPurpose
from .team_models import Team, TeamMember
from .project_models import Project, ProjectList
from .task_models import Task, TaskAssignee, TaskComment


__all__ = [
    "Base",
    "User", "UserAccount",
    "OtpVerification", "OtpPurpose",
    "Team", "TeamMember",
    "Project", "ProjectList",
    "Task", "TaskAssignee", "TaskComment",
]