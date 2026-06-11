import json
import logging
import threading
import time
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models import User, UserAccount
from app.api.v1.webhooks.schemas import InternalMessage

# Async client for calling Telegram/Bale sendMessage endpoints
import httpx

logger = logging.getLogger("app.webhooks")


class IdempotencyCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._cache = {}
        self._lock = threading.Lock()
        self.ttl = ttl_seconds

    def is_duplicate(self, message_id: str | None) -> bool:
        if not message_id:
            return False
        now = time.time()
        with self._lock:
            # Evict expired entries
            expired = [k for k, v in self._cache.items() if now - v > self.ttl]
            for k in expired:
                del self._cache[k]

            if message_id in self._cache:
                return True
            self._cache[message_id] = now
            return False


idempotency_cache = IdempotencyCache()


def normalize_phone(phone: str) -> str:
    """
    Normalizes Iranian phone numbers into 11-digit format starting with 09 (e.g. 09123456789).
    """
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("98") and len(digits) == 12:
        return "0" + digits[2:]
    if digits.startswith("0098") and len(digits) == 14:
        return "0" + digits[4:]
    if len(digits) == 10 and digits.startswith("9"):
        return "0" + digits
    if len(digits) == 11 and digits.startswith("09"):
        return digits
    return digits


async def send_bot_reply(platform: str, chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
    """
    Sends message back to Telegram/Bale user. If credentials are not configured,
    logs the text instead of failing.
    """
    token = settings.TELEGRAM_BOT_TOKEN if platform == "telegram" else settings.BALE_BOT_TOKEN
    if not token:
        logger.warning(
            "Bot token for platform=%s is not set. Text was NOT sent. Text content: %r",
            platform,
            text,
        )
        return False

    base_url = "https://api.telegram.org" if platform == "telegram" else "https://api.bale.ai"
    url = f"{base_url}/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            if response.status_code == 200:
                logger.info("Successfully sent bot reply to platform=%s chat_id=%s", platform, chat_id)
                return True
            else:
                logger.error(
                    "Failed to send bot reply to platform=%s chat_id=%s. HTTP Status: %s, Body: %s",
                    platform,
                    chat_id,
                    response.status_code,
                    response.text,
                )
                return False
    except Exception as e:
        logger.error("Exception sending bot reply to platform=%s: %s", platform, str(e))
        return False


def log_event(event: str, message: InternalMessage, result: str, details: dict | None = None):
    """
    Outputs structured JSON log format for tracking webhook events.
    """
    log_data = {
        "event": event,
        "platform": message.platform,
        "user_id": message.user_id,
        "message_id": message.message_id,
        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
        "result": result,
        "details": details or {},
    }
    logger.info("WEBHOOK_LOG: %s", json.dumps(log_data, default=str))


async def handle_create_team(db: Session, sender: User, args: list[str]) -> str:
    if not args:
        return "⚠️ روش استفاده: /create_team <نام تیم>"
    team_name = " ".join(args)
    from app.schemas.team_schemas import TeamCreate
    from app.services import team_service
    try:
        team_out = team_service.create_team(db, sender, TeamCreate(name=team_name))
        return (
            f"✅ تیم '{team_name}' با موفقیت ساخته شد! 🚀\n\n"
            f"📌 شناسه تیم: `{team_out.id}`\n\n"
            f"برای دعوت دیگران از دستور زیر استفاده کنید:\n"
            f"`/invite {team_out.id} <شماره موبایل>`"
        )
    except Exception as e:
        return f"❌ خطا در ساخت تیم: {str(e)}"


async def handle_teams(db: Session, sender: User) -> str:
    from app.models.team_models import Team, TeamMember
    teams = db.query(Team).join(TeamMember).filter(TeamMember.user_id == sender.id).all()
    if not teams:
        return "⚠️ شما هنوز عضو هیچ تیمی نیستید. می‌توانید با دستور زیر تیم جدید بسازید:\n/create_team <نام تیم>"
    msg = "👥 لیست تیم‌های شما:\n\n"
    for t in teams:
        msg += f"🔹 {t.name}\n📌 شناسه: `{t.id}`\n\n"
    return msg


async def handle_invite(db: Session, sender: User, args: list[str]) -> str:
    if len(args) < 2:
        return "⚠️ روش استفاده: /invite <شناسه تیم> <شماره موبایل>"
    team_id, phone = args[0], args[1]
    phone = normalize_phone(phone)
    if not (phone.startswith("09") and len(phone) == 11):
        return "⚠️ شماره موبایل وارد شده معتبر نیست. باید در قالب 09123456789 باشد."

    from app.services.access import get_team_or_404, ensure_team_admin
    try:
        get_team_or_404(db, team_id)
        ensure_team_admin(db, team_id, sender)
    except Exception:
        return "❌ خطا: شما دسترسی لازم برای دعوت به این تیم را ندارید یا تیم یافت نشد."

    user = db.query(User).filter(User.phone == phone).first()
    is_new = False
    if not user:
        user = User(phone=phone, username=f"user_{phone}")
        db.add(user)
        db.flush()
        is_new = True

    from app.models.team_models import TeamMember, TeamRole
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user.id
    ).first()
    if existing:
        return f"⚠️ کاربر با شماره {phone} قبلاً عضو این تیم بوده است."

    new_member = TeamMember(team_id=team_id, user_id=user.id, role=TeamRole.MEMBER)
    db.add(new_member)
    db.commit()

    msg = f"✅ کاربر با شماره {phone} با موفقیت به تیم دعوت و عضو شد."
    if is_new:
        msg += "\n(این کاربر هنوز در هفته‌یار ثبت‌نام نکرده است. پس از شروع کار با ربات، حساب وی متصل خواهد شد.)"
    return msg


async def handle_members(db: Session, sender: User, args: list[str]) -> str:
    if not args:
        return "⚠️ روش استفاده: /members <شناسه تیم>"
    team_id = args[0]

    from app.models.team_models import TeamMember, Team
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == sender.id
    ).first()
    if not membership:
        return "❌ شما عضو این تیم نیستید یا تیم یافت نشد."

    team = db.query(Team).filter(Team.id == team_id).first()
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    msg = f"👥 اعضای تیم {team.name if team else ''}:\n\n"
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        role_fa = {"OWNER": "سازنده", "ADMIN": "ادمین", "MEMBER": "عضو"}.get(m.role.value, m.role.value)
        msg += f"👤 {u.username or u.phone or 'کاربر'} - نقش: {role_fa}\n"
    return msg


async def handle_projects(db: Session, sender: User, args: list[str]) -> str:
    if not args:
        return "⚠️ روش استفاده: /projects <شناسه تیم>"
    team_id = args[0]

    from app.models.team_models import TeamMember
    from app.models.project_models import Project
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == sender.id
    ).first()
    if not membership:
        return "❌ شما عضو این تیم نیستید یا تیم یافت نشد."

    projects = db.query(Project).filter(Project.team_id == team_id).all()
    if not projects:
        return "⚠️ این تیم هنوز هیچ پروژه‌ای ندارد."
    msg = "📂 پروژه‌های تیم:\n\n"
    for p in projects:
        msg += f"📁 {p.name}\n📌 شناسه: `{p.id}`\n\n"
    return msg


async def handle_create_project(db: Session, sender: User, args: list[str]) -> str:
    if len(args) < 2:
        return "⚠️ روش استفاده: /create_project <شناسه تیم> <نام پروژه>"
    team_id = args[0]
    project_name = " ".join(args[1:])

    from app.services.access import get_team_or_404, ensure_team_admin
    try:
        get_team_or_404(db, team_id)
        ensure_team_admin(db, team_id, sender)
    except Exception:
        return "❌ خطا: شما دسترسی لازم در این تیم را ندارید یا تیم یافت نشد."

    from app.models.project_models import Project, ProjectList
    project = Project(team_id=team_id, name=project_name)
    db.add(project)
    db.flush()

    default_lists = [
        ProjectList(project_id=project.id, name="انجام نشده", position=0),
        ProjectList(project_id=project.id, name="در حال انجام", position=1),
        ProjectList(project_id=project.id, name="انجام شده", position=2),
    ]
    db.add_all(default_lists)
    db.commit()
    return f"✅ پروژه '{project_name}' با موفقیت ساخته شد.\n📌 شناسه پروژه: `{project.id}`"


async def handle_tasks(db: Session, sender: User) -> str:
    from app.models.task_models import Task, TaskAssignee, TaskStatus
    from app.models.project_models import Project
    tasks = db.query(Task).join(TaskAssignee).filter(TaskAssignee.user_id == sender.id).all()
    if not tasks:
        return "📋 شما هیچ تسک محول شده‌ای ندارید."
    msg = "📋 لیست تسک‌های شما:\n\n"
    for t in tasks:
        status_fa = {TaskStatus.TODO: "انجام نشده", TaskStatus.IN_PROGRESS: "در حال انجام", TaskStatus.DONE: "انجام شده"}.get(t.status, t.status)
        project = db.query(Project).filter(Project.id == t.project_id).first()
        proj_name = project.name if project else ""
        msg += f"🔹 {t.title}\n📌 شناسه: `{t.id}`\nوضعیت: {status_fa} | پروژه: {proj_name}\n\n"
    return msg


async def handle_team_tasks(db: Session, sender: User, args: list[str]) -> str:
    if not args:
        return "⚠️ روش استفاده: /team_tasks <شناسه تیم>"
    team_id = args[0]

    from app.models.team_models import TeamMember
    from app.models.project_models import Project
    from app.models.task_models import Task, TaskStatus
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == sender.id
    ).first()
    if not membership:
        return "❌ شما عضو این تیم نیستید یا تیم یافت نشد."

    tasks = db.query(Task).filter(Task.project_id.in_(
        db.query(Project.id).filter(Project.team_id == team_id)
    )).all()
    if not tasks:
        return "⚠️ این تیم هیچ تسکی ندارد."
    msg = "📋 لیست تسک‌های تیم:\n\n"
    for t in tasks:
        status_fa = {TaskStatus.TODO: "انجام نشده", TaskStatus.IN_PROGRESS: "در حال انجام", TaskStatus.DONE: "انجام شده"}.get(t.status, t.status)
        msg += f"🔹 {t.title}\n📌 شناسه: `{t.id}`\nوضعیت: {status_fa}\n\n"
    return msg


async def handle_create_task(db: Session, sender: User, args: list[str]) -> str:
    if len(args) < 2:
        return "⚠️ روش استفاده: /create_task <شناسه تیم> <عنوان تسک> [@شماره_موبایل_مسئول] [توضیحات تسک]"
    team_id = args[0]
    remaining_text = " ".join(args[1:])

    assignee_phone = None
    title = ""
    description = ""

    words = remaining_text.split()
    assignee_idx = -1
    for idx, w in enumerate(words):
        if w.startswith("@") and len(w) > 1:
            phone_part = w[1:]
            if phone_part.isdigit():
                assignee_phone = normalize_phone(phone_part)
                assignee_idx = idx
                break

    if assignee_idx != -1:
        title = " ".join(words[:assignee_idx])
        description = " ".join(words[assignee_idx+1:])
    else:
        title = remaining_text
        description = None

    if not title:
        return "⚠️ عنوان تسک نمی‌تواند خالی باشد."

    from app.services.access import get_team_or_404, ensure_team_admin
    try:
        get_team_or_404(db, team_id)
        ensure_team_admin(db, team_id, sender)
    except Exception:
        return "❌ خطا: شما دسترسی لازم در این تیم را ندارید یا تیم یافت نشد."

    from app.models.project_models import Project, ProjectList
    project = db.query(Project).filter(Project.team_id == team_id).first()
    if not project:
        project = Project(team_id=team_id, name="پروژه عمومی", description="پروژه پیش‌فرض تیم برای مدیریت تسک‌ها")
        db.add(project)
        db.flush()

    project_list = db.query(ProjectList).filter(ProjectList.project_id == project.id).order_by(ProjectList.position).first()
    if not project_list:
        default_lists = [
            ProjectList(project_id=project.id, name="انجام نشده", position=0),
            ProjectList(project_id=project.id, name="در حال انجام", position=1),
            ProjectList(project_id=project.id, name="انجام شده", position=2),
        ]
        db.add_all(default_lists)
        db.flush()
        project_list = default_lists[0]

    from app.models.task_models import Task, TaskAssignee, TaskStatus
    task = Task(
        title=title,
        description=description,
        status=TaskStatus.TODO,
        project_id=project.id,
        list_id=project_list.id,
        creator_id=sender.id
    )
    db.add(task)
    db.flush()

    assignee_msg = ""
    if assignee_phone:
        assignee_user = db.query(User).filter(User.phone == assignee_phone).first()
        if not assignee_user:
            assignee_user = User(phone=assignee_phone, username=f"user_{assignee_phone}")
            db.add(assignee_user)
            db.flush()

        from app.models.team_models import TeamMember, TeamRole
        member = db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == assignee_user.id
        ).first()
        if not member:
            member = TeamMember(team_id=team_id, user_id=assignee_user.id, role=TeamRole.MEMBER)
            db.add(member)
            db.flush()

        assignee_rel = TaskAssignee(task_id=task.id, user_id=assignee_user.id)
        db.add(assignee_rel)
        assignee_msg = f"\n👤 مسئول: {assignee_user.username or assignee_phone}"

    db.commit()
    return f"✅ تسک با موفقیت ایجاد شد.\n📌 شناسه تسک: `{task.id}`\n📋 عنوان: {title}{assignee_msg}"


async def handle_update_task(db: Session, sender: User, args: list[str]) -> str:
    if len(args) < 2:
        return "⚠️ روش استفاده: /update_task <شناسه تسک> <وضعیت (TODO / IN_PROGRESS / DONE)>"
    task_id, status_str = args[0], args[1].upper()

    from app.models.task_models import TaskStatus, Task
    status_map = {
        "TODO": TaskStatus.TODO,
        "TODO_LIST": TaskStatus.TODO,
        "انجام_نشده": TaskStatus.TODO,
        "انجام-نشده": TaskStatus.TODO,
        "IN_PROGRESS": TaskStatus.IN_PROGRESS,
        "IN-PROGRESS": TaskStatus.IN_PROGRESS,
        "در_حال_انجام": TaskStatus.IN_PROGRESS,
        "در-حال-انجام": TaskStatus.IN_PROGRESS,
        "DONE": TaskStatus.DONE,
        "انجام_شده": TaskStatus.DONE,
        "انجام-شده": TaskStatus.DONE,
        "کامل_شده": TaskStatus.DONE,
    }

    if status_str not in status_map:
        return "⚠️ وضعیت معتبر نیست. مقادیر مجاز: TODO (انجام نشده), IN_PROGRESS (در حال انجام), DONE (انجام شده)"

    status_enum = status_map[status_str]
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return "❌ تسک یافت نشد."

    from app.models.project_models import Project
    from app.models.team_models import TeamMember

    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        return "❌ پروژه تسک یافت نشد."

    membership = db.query(TeamMember).filter(
        TeamMember.team_id == project.team_id,
        TeamMember.user_id == sender.id
    ).first()
    if not membership:
        return "❌ شما عضو تیم مربوطه نیستید و دسترسی ندارید."

    task.status = status_enum
    db.commit()

    status_fa = {
        TaskStatus.TODO: "انجام نشده",
        TaskStatus.IN_PROGRESS: "در حال انجام",
        TaskStatus.DONE: "انجام شده"
    }[status_enum]

    return f"✅ وضعیت تسک `{task.title}` به '{status_fa}' تغییر یافت."


# A simple in-memory session store mapping user_id (platform specific string) to their current state/action
USER_STATES = {}


async def answer_callback_query(platform: str, callback_query_id: str, text: str | None = None) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN if platform == "telegram" else settings.BALE_BOT_TOKEN
    if not token:
        return False
    base_url = "https://api.telegram.org" if platform == "telegram" else "https://api.bale.ai"
    url = f"{base_url}/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=5.0)
            return True
    except Exception:
        return False


async def edit_bot_message(platform: str, chat_id: str, message_id: str, text: str, reply_markup: dict | None = None) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN if platform == "telegram" else settings.BALE_BOT_TOKEN
    if not token:
        return False
    base_url = "https://api.telegram.org" if platform == "telegram" else "https://api.bale.ai"
    url = f"{base_url}/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": int(message_id),
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            return response.status_code == 200
    except Exception:
        return False


def get_main_menu_payload(sender: User):
    token = create_access_token(sender.id)
    login_link = f"{settings.FRONTEND_URL}/login/callback?token={token}"
    text = (
        f"سلام {sender.username or 'کاربر'} عزیز! 🌸\n"
        f"به ربات هفته‌یار خوش آمدید.\n\n"
        f"برای ورود مستقیم به پنل مدیریت تسک خود، روی لینک زیر کلیک کنید:\n"
        f"🔗 {login_link}\n\n"
        f"📋 لیست دستورات فعال ربات:\n"
        f"🔹 /teams - لیست تیم‌های شما\n"
        f"🔹 /tasks - لیست تسک‌های شما\n"
        f"🔹 /help - راهنمای استفاده و لیست دستورات\n\n"
        f"همچنین می‌توانید از دکمه‌های زیر برای مدیریت سریع استفاده کنید 👇"
    )

    keyboard = [
        [
            {"text": "👥 تیم‌های من", "callback_data": "menu:teams"},
            {"text": "📋 تسک‌های من", "callback_data": "menu:tasks"}
        ]
    ]
    # Telegram strictly rejects localhost or non-https URLs in inline buttons
    if login_link.startswith("https://") and "localhost" not in login_link:
        keyboard.append([{"text": "🔗 ورود مستقیم به پنل وب", "url": login_link}])

    reply_markup = {"inline_keyboard": keyboard}
    return text, reply_markup



def get_teams_list_payload(db: Session, sender: User):
    from app.models.team_models import Team, TeamMember
    teams = db.query(Team).join(TeamMember).filter(TeamMember.user_id == sender.id).all()
    if not teams:
        text = "⚠️ شما هنوز عضو هیچ تیمی نیستید. می‌توانید با دستور /create_team <نام تیم> تیم جدید بسازید."
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "menu:main"}]
            ]
        }
        return text, reply_markup
    
    text = "👥 لیست تیم‌های شما:\n\n"
    for t in teams:
        text += f"🔹 {t.name}\n📌 شناسه: `{t.id}`\n\n"
    text += "برای مشاهده جزئیات هر تیم روی دکمه‌ی آن کلیک کنید 👇"
    
    keyboard = []
    for t in teams:
        keyboard.append([{"text": f"🔹 {t.name}", "callback_data": f"team:detail:{t.id}"}])
    keyboard.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "menu:main"}])
    reply_markup = {"inline_keyboard": keyboard}
    return text, reply_markup


def get_team_detail_payload(db: Session, sender: User, team_id: str):
    from app.models.team_models import Team
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return "❌ تیم یافت نشد.", {"inline_keyboard": [[{"text": "🔙 لیست تیم‌ها", "callback_data": "menu:teams"}]]}
        
    text = (
        f"👥 نام تیم: *{team.name}*\n"
        f"📌 شناسه تیم:\n`{team.id}`\n\n"
        f"عملیات مورد نظر خود را انتخاب کنید 👇"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "👥 اعضای تیم", "callback_data": f"team:members:{team.id}"},
                {"text": "📂 پروژه‌های تیم", "callback_data": f"team:projects:{team.id}"}
            ],
            [
                {"text": "📋 تسک‌های تیم", "callback_data": f"team:tasks:{team.id}"}
            ],
            [
                {"text": "👥 دعوت عضو جدید", "callback_data": f"team:invite_prompt:{team.id}"},
                {"text": "📂 پروژه جدید", "callback_data": f"team:create_project_prompt:{team.id}"}
            ],
            [
                {"text": "📋 تسک جدید", "callback_data": f"team:create_task_prompt:{team.id}"}
            ],
            [
                {"text": "🔙 بازگشت به لیست تیم‌ها", "callback_data": "menu:teams"}
            ]
        ]
    }
    return text, reply_markup


def get_tasks_list_payload(db: Session, sender: User):
    from app.models.task_models import Task, TaskAssignee, TaskStatus
    tasks = db.query(Task).join(TaskAssignee).filter(TaskAssignee.user_id == sender.id).all()
    if not tasks:
        text = "📋 شما هیچ تسک محول شده‌ای ندارید."
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "menu:main"}]
            ]
        }
        return text, reply_markup
        
    text = "📋 لیست تسک‌های محول شده به شما:\n\n"
    for t in tasks:
        status_fa = {TaskStatus.TODO: "انجام نشده 🔴", TaskStatus.IN_PROGRESS: "در حال انجام 🟡", TaskStatus.DONE: "انجام شده 🟢"}.get(t.status, t.status)
        text += f"🔹 {t.title}\n📌 شناسه: `{t.id}`\nوضعیت: {status_fa}\n\n"
    text += "برای مشاهده جزئیات و تغییر وضعیت تسک روی دکمه‌ی آن کلیک کنید 👇"
    
    keyboard = []
    for t in tasks:
        status_fa = {TaskStatus.TODO: "انجام نشده 🔴", TaskStatus.IN_PROGRESS: "در حال انجام 🟡", TaskStatus.DONE: "انجام شده 🟢"}.get(t.status, t.status)
        keyboard.append([{"text": f"{t.title} ({status_fa})", "callback_data": f"task:detail:{t.id}"}])
    keyboard.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "menu:main"}])
    reply_markup = {"inline_keyboard": keyboard}
    return text, reply_markup


def get_task_detail_payload(db: Session, sender: User, task_id: str):
    from app.models.task_models import Task, TaskStatus
    from app.models.project_models import Project
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return "❌ تسک یافت نشد.", {"inline_keyboard": [[{"text": "🔙 لیست تسک‌ها", "callback_data": "menu:tasks"}]]}
        
    project = db.query(Project).filter(Project.id == task.project_id).first()
    proj_name = project.name if project else "نامشخص"
    status_fa = {
        TaskStatus.TODO: "انجام نشده 🔴",
        TaskStatus.IN_PROGRESS: "در حال انجام 🟡",
        TaskStatus.DONE: "انجام شده 🟢"
    }.get(task.status, task.status)
    
    text = (
        f"📋 تسک: *{task.title}*\n"
        f"📌 شناسه تسک:\n`{task.id}`\n\n"
        f"📂 پروژه: {proj_name}\n"
        f"⚙️ وضعیت فعلی: *{status_fa}*\n"
        f"📝 توضیحات: {task.description or 'ندارد'}\n\n"
        f"برای تغییر وضعیت تسک روی یکی از دکمه‌های زیر کلیک کنید 👇"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🔴 انجام نشده", "callback_data": f"task:status:{task.id}:TODO"},
                {"text": "🟡 در حال انجام", "callback_data": f"task:status:{task.id}:IN_PROGRESS"},
                {"text": "🟢 انجام شده", "callback_data": f"task:status:{task.id}:DONE"}
            ],
            [
                {"text": "🔙 بازگشت به لیست تسک‌ها", "callback_data": "menu:tasks"}
            ]
        ]
    }
    return text, reply_markup


async def send_main_menu(db: Session, sender: User, platform: str, chat_id: str):
    text, reply_markup = get_main_menu_payload(sender)
    await send_bot_reply(platform, chat_id, text, reply_markup)


async def send_teams_list(db: Session, sender: User, platform: str, chat_id: str):
    text, reply_markup = get_teams_list_payload(db, sender)
    await send_bot_reply(platform, chat_id, text, reply_markup)


async def send_tasks_list(db: Session, sender: User, platform: str, chat_id: str):
    text, reply_markup = get_tasks_list_payload(db, sender)
    await send_bot_reply(platform, chat_id, text, reply_markup)


async def send_team_detail(db: Session, sender: User, platform: str, chat_id: str, team_id: str):
    text, reply_markup = get_team_detail_payload(db, sender, team_id)
    await send_bot_reply(platform, chat_id, text, reply_markup)


async def handle_state_invite_shared_user(db: Session, sender: User, team_id: str, shared_user_id: str) -> str:
    from app.services.access import get_team_or_404, ensure_team_admin
    try:
        get_team_or_404(db, team_id)
        ensure_team_admin(db, team_id, sender)
    except Exception:
        return "❌ خطا: شما دسترسی لازم برای دعوت به این تیم را ندارید یا تیم یافت نشد."

    account = db.query(UserAccount).filter(
        UserAccount.provider == "telegram",
        UserAccount.provider_id == shared_user_id
    ).first()

    if account:
        invited_user = account.user
    else:
        # Create a placeholder user without phone but with telegram user account
        base_username = f"tg_{shared_user_id}"
        username = base_username
        suffix = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}_{suffix}"
            suffix += 1

        invited_user = User(username=username, phone=None)
        db.add(invited_user)
        db.flush()

        new_account = UserAccount(
            user_id=invited_user.id,
            provider="telegram",
            provider_id=shared_user_id
        )
        db.add(new_account)
        db.flush()

    from app.models.team_models import TeamMember, TeamRole
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == invited_user.id
    ).first()
    if existing:
        return f"⚠️ کاربر دعوت شده قبلاً عضو این تیم بوده است."

    new_member = TeamMember(team_id=team_id, user_id=invited_user.id, role=TeamRole.MEMBER)
    db.add(new_member)
    db.commit()

    return f"✅ کاربر دعوت شده با موفقیت به عضویت تیم درآمد. (شناسه تلگرام: {shared_user_id})"


async def handle_callback_query(db: Session, sender: User, message: InternalMessage):
    callback_query_id = message.callback_query_id
    callback_data = message.message_text.replace("//callback:", "")
    
    raw_message = message.raw_payload.get("callback_query", {}).get("message", {})
    chat_id = str(raw_message.get("chat", {}).get("id", ""))
    message_id = str(raw_message.get("message_id", ""))
    
    parts = callback_data.split(":")
    action = parts[0]
    
    await answer_callback_query(message.platform, callback_query_id)
    
    if action == "menu":
        sub_action = parts[1]
        if sub_action == "main":
            text, reply_markup = get_main_menu_payload(sender)
            await edit_bot_message(message.platform, chat_id, message_id, text, reply_markup)
        elif sub_action == "teams":
            text, reply_markup = get_teams_list_payload(db, sender)
            await edit_bot_message(message.platform, chat_id, message_id, text, reply_markup)
        elif sub_action == "tasks":
            text, reply_markup = get_tasks_list_payload(db, sender)
            await edit_bot_message(message.platform, chat_id, message_id, text, reply_markup)
            
    elif action == "team":
        sub_action = parts[1]
        team_id = parts[2]
        
        if sub_action == "detail":
            text, reply_markup = get_team_detail_payload(db, sender, team_id)
            await edit_bot_message(message.platform, chat_id, message_id, text, reply_markup)
            
        elif sub_action == "members":
            reply_text = await handle_members(db, sender, [team_id])
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🔙 بازگشت به تیم", "callback_data": f"team:detail:{team_id}"}]
                ]
            }
            await edit_bot_message(message.platform, chat_id, message_id, reply_text, reply_markup)
            
        elif sub_action == "projects":
            reply_text = await handle_projects(db, sender, [team_id])
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "➕ ساخت پروژه جدید", "callback_data": f"team:create_project_prompt:{team_id}"}],
                    [{"text": "🔙 بازگشت به تیم", "callback_data": f"team:detail:{team_id}"}]
                ]
            }
            await edit_bot_message(message.platform, chat_id, message_id, reply_text, reply_markup)
            
        elif sub_action == "tasks":
            reply_text = await handle_team_tasks(db, sender, [team_id])
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "➕ ساخت تسک جدید", "callback_data": f"team:create_task_prompt:{team_id}"}],
                    [{"text": "🔙 بازگشت به تیم", "callback_data": f"team:detail:{team_id}"}]
                ]
            }
            await edit_bot_message(message.platform, chat_id, message_id, reply_text, reply_markup)
            
        elif sub_action == "invite_prompt":
            USER_STATES[message.user_id] = {"action": "awaiting_invite_contact", "team_id": team_id}
            reply_text = (
                "👥 دعوت عضو جدید به تیم:\n\n"
                "لطفاً با استفاده از دکمه‌ی زیر، مخاطب مورد نظر خود را از لیست چت‌های تلگرام انتخاب کنید👇\n"
                "(یا شماره موبایل او را به صورت 09123456789 تایپ و ارسال کنید)"
            )
            keyboard = {
                "keyboard": [
                    [{"text": "👥 انتخاب مخاطب از لیست چت‌ها", "request_users": {"request_id": 1, "user_is_bot": False}}],
                    [{"text": "❌ لغو عملیات"}]
                ],
                "one_time_keyboard": True,
                "resize_keyboard": True
            }
            await send_bot_reply(message.platform, chat_id, reply_text, reply_markup=keyboard)

            
        elif sub_action == "create_project_prompt":
            USER_STATES[message.user_id] = {"action": "awaiting_project_name", "team_id": team_id}
            reply_text = (
                "📂 ساخت پروژه جدید:\n\n"
                "لطفاً نام پروژه مورد نظر خود را تایپ و ارسال کنید 👇"
            )
            keyboard = {
                "keyboard": [
                    [{"text": "❌ لغو عملیات"}]
                ],
                "one_time_keyboard": True,
                "resize_keyboard": True
            }
            await send_bot_reply(message.platform, chat_id, reply_text, reply_markup=keyboard)
            
        elif sub_action == "create_task_prompt":
            USER_STATES[message.user_id] = {"action": "awaiting_task_title", "team_id": team_id}
            reply_text = (
                "📋 ساخت تسک جدید:\n\n"
                "لطفاً عنوان تسک خود را تایپ و ارسال کنید.\n"
                "💡 همچنین می‌توانید مسئول تسک و توضیحات را در ادامه بنویسید:\n"
                "`<عنوان تسک> [@شماره_موبایل_مسئول] [توضیحات تسک]`\n\n"
                "مثال:\n"
                "`طراحی دیتابیس @09123456789 بخش تسک‌ها پیاده‌سازی شود`"
            )
            keyboard = {
                "keyboard": [
                    [{"text": "❌ لغو عملیات"}]
                ],
                "one_time_keyboard": True,
                "resize_keyboard": True
            }
            await send_bot_reply(message.platform, chat_id, reply_text, reply_markup=keyboard)
            
    elif action == "task":
        sub_action = parts[1]
        task_id = parts[2]
        
        if sub_action == "detail":
            text, reply_markup = get_task_detail_payload(db, sender, task_id)
            await edit_bot_message(message.platform, chat_id, message_id, text, reply_markup)
        elif sub_action == "status":
            status_val = parts[3]
            reply_text = await handle_update_task(db, sender, [task_id, status_val])
            await send_bot_reply(message.platform, chat_id, reply_text)
            
            text, reply_markup = get_task_detail_payload(db, sender, task_id)
            await edit_bot_message(message.platform, chat_id, message_id, text, reply_markup)


async def process_message(message: InternalMessage, db: Session):
    """
    Unified pipeline to process normalized messages from Telegram/Bale bots.
    Handles idempotency, account linking, registration, and user login deep links.
    Also handles team/task/member commands for linked accounts.
    """
    # 1. Idempotency Check
    if message.message_id and idempotency_cache.is_duplicate(message.message_id):
        log_event(
            event="idempotency_check",
            message=message,
            result="duplicate_ignored",
            details={"message_id": message.message_id},
        )
        return

    log_event(
        event="incoming_message",
        message=message,
        result="processing",
        details={"text": message.message_text, "has_contact": message.contact_phone is not None},
    )

    try:
        # 2. Check if platform user is already linked to a Haftyar account
        account = db.query(UserAccount).filter(
            UserAccount.provider == message.platform,
            UserAccount.provider_id == message.user_id,
        ).first()

        if account:
            user = account.user
            text = message.message_text.strip() if message.message_text else ""

            # A. Check if it's a callback query
            if message.callback_query_id:
                await handle_callback_query(db, user, message)
                log_event(
                    event="process_message",
                    message=message,
                    result="callback_executed",
                    details={"user_id": user.id, "callback_data": text},
                )
                return

            # B. Check if we have an active state for this user
            state = USER_STATES.get(message.user_id)
            if state:
                if text == "❌ لغو عملیات" or text.lower() == "/cancel":
                    USER_STATES.pop(message.user_id, None)
                    remove_kbd = {"remove_keyboard": True}
                    await send_bot_reply(message.platform, message.user_id, "❌ عملیات لغو شد.", reply_markup=remove_kbd)
                    await send_main_menu(db, user, message.platform, message.user_id)
                    return

                if state["action"] == "awaiting_invite_contact":
                    if message.shared_user_id:
                        reply_text = await handle_state_invite_shared_user(db, user, state["team_id"], message.shared_user_id)
                    elif text:
                        reply_text = await handle_invite(db, user, [state["team_id"], text])
                    else:
                        reply_text = "⚠️ لطفا از دکمه‌ی زیر برای انتخاب مخاطب استفاده کنید یا شماره موبایل او را تایپ کنید."
                        await send_bot_reply(message.platform, message.user_id, reply_text)
                        return

                    USER_STATES.pop(message.user_id, None)
                    remove_kbd = {"remove_keyboard": True}
                    await send_bot_reply(message.platform, message.user_id, reply_text, reply_markup=remove_kbd)
                    await send_team_detail(db, user, message.platform, message.user_id, state["team_id"])
                    return

                elif state["action"] == "awaiting_project_name":
                    if text:
                        reply_text = await handle_create_project(db, user, [state["team_id"], text])
                        USER_STATES.pop(message.user_id, None)
                        remove_kbd = {"remove_keyboard": True}
                        await send_bot_reply(message.platform, message.user_id, reply_text, reply_markup=remove_kbd)
                        await send_team_detail(db, user, message.platform, message.user_id, state["team_id"])
                    else:
                        await send_bot_reply(message.platform, message.user_id, "⚠️ لطفا نام پروژه را ارسال کنید.")
                    return

                elif state["action"] == "awaiting_task_title":
                    if text:
                        args = [state["team_id"]] + text.split()
                        reply_text = await handle_create_task(db, user, args)
                        USER_STATES.pop(message.user_id, None)
                        remove_kbd = {"remove_keyboard": True}
                        await send_bot_reply(message.platform, message.user_id, reply_text, reply_markup=remove_kbd)
                        await send_team_detail(db, user, message.platform, message.user_id, state["team_id"])
                    else:
                        await send_bot_reply(message.platform, message.user_id, "⚠️ لطفا عنوان تسک را ارسال کنید.")
                    return

            # C. Check if it is a bot command
            if text.startswith("/"):
                parts = text.split()
                command = parts[0].lower()
                if "@" in command:
                    command = command.split("@")[0]
                args = parts[1:]

                # If user runs any command, clear existing state
                USER_STATES.pop(message.user_id, None)

                if command == "/start" or command == "/help" or command == "/menu":
                    await send_main_menu(db, user, message.platform, message.user_id)
                elif command == "/teams":
                    await send_teams_list(db, user, message.platform, message.user_id)
                elif command == "/tasks":
                    await send_tasks_list(db, user, message.platform, message.user_id)
                elif command == "/create_team":
                    reply_text = await handle_create_team(db, user, args)
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                elif command == "/invite":
                    reply_text = await handle_invite(db, user, args)
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                elif command == "/members":
                    reply_text = await handle_members(db, user, args)
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                elif command == "/projects":
                    reply_text = await handle_projects(db, user, args)
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                elif command == "/create_project":
                    reply_text = await handle_create_project(db, user, args)
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                elif command == "/team_tasks":
                    reply_text = await handle_team_tasks(db, user, args)
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                elif command == "/create_task":
                    reply_text = await handle_create_task(db, user, args)
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                elif command == "/update_task":
                    reply_text = await handle_update_task(db, user, args)
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                else:
                    reply_text = "⚠️ دستور وارد شده ناشناخته است. برای مشاهده لیست دستورات معتبر دستور /help را ارسال کنید."
                    await send_bot_reply(message.platform, message.user_id, reply_text)
                
                log_event(
                    event="process_message",
                    message=message,
                    result="command_executed",
                    details={"user_id": user.id, "command": command, "args": args},
                )
                return
            else:
                # Text is not a slash command, default to main menu
                USER_STATES.pop(message.user_id, None)
                await send_main_menu(db, user, message.platform, message.user_id)
                return

        # 3. User is not linked. Check if they shared their contact (phone number)
        if message.contact_phone:
            phone = normalize_phone(message.contact_phone)

            # Check if standard user with this phone number already exists
            user = db.query(User).filter(User.phone == phone).first()
            is_new = False

            if not user:
                is_new = True
                user = User(
                    phone=phone,
                    username=f"user_{phone}",
                )
                db.add(user)
                db.flush()

            # Link the new platform account to the User
            new_account = UserAccount(
                user_id=user.id,
                provider=message.platform,
                provider_id=message.user_id,
            )
            db.add(new_account)
            db.commit()
            db.refresh(user)

            if is_new:
                confirm_text = "ثبت‌نام شما در هفته‌یار با موفقیت انجام شد! 🚀"
            else:
                confirm_text = f"حساب هفته‌یار شما با موفقیت به این پیام‌رسان متصل شد! 🎉\nشماره موبایل: {phone}"

            await send_bot_reply(message.platform, message.user_id, confirm_text, reply_markup={"remove_keyboard": True})
            await send_main_menu(db, user, message.platform, message.user_id)


            log_event(
                event="process_message",
                message=message,
                result="link_success",
                details={"user_id": user.id, "phone": phone, "is_new_user": is_new},
            )
            return

        # 4. User is not linked and did not share contact. Ask for contact sharing.
        reply_text = (
            "برای ثبت‌نام یا ورود به سامانه هفته‌یار، نیاز به احراز شماره موبایل شما داریم.\n\n"
            "لطفاً از دکمه زیر برای اشتراک‌گذاری شماره موبایل خود استفاده کنید 👇"
        )
        keyboard = {
            "keyboard": [
                [{"text": "اشتراک‌گذاری شماره موبایل / Share Contact", "request_contact": True}]
            ],
            "one_time_keyboard": True,
            "resize_keyboard": True,
        }

        await send_bot_reply(message.platform, message.user_id, reply_text, reply_markup=keyboard)

        log_event(
            event="process_message",
            message=message,
            result="contact_requested",
            details={"action": "send_contact_prompt_keyboard"},
        )

    except Exception as e:
        db.rollback()
        logger.exception("Error processing webhook message in service layer")
        log_event(
            event="process_message",
            message=message,
            result="error",
            details={"error_message": str(e)},
        )
        err_msg = "متأسفانه در پردازش درخواست شما خطایی رخ داد. لطفاً مجدداً تلاش کنید."
        await send_bot_reply(message.platform, message.user_id, err_msg)

