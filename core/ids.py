import secrets

ID_PREFIX_USER = "usr"
ID_PREFIX_ACCOUNT = "acc"
ID_PREFIX_TEAM = "tm"
ID_PREFIX_MEMBER = "mbr"
ID_PREFIX_PROJECT = "prj"
ID_PREFIX_LIST = "lst"
ID_PREFIX_TASK = "tsk"
ID_PREFIX_ASSIGNEE = "asn"
ID_PREFIX_COMMENT = "cmt"


def generate_id(prefix: str) -> str:
    """Opaque public identifier: prefix + cryptographically random token."""
    return f"{prefix}_{secrets.token_urlsafe(16)}"


def new_user_id() -> str:
    return generate_id(ID_PREFIX_USER)


def new_account_id() -> str:
    return generate_id(ID_PREFIX_ACCOUNT)


def new_team_id() -> str:
    return generate_id(ID_PREFIX_TEAM)


def new_member_id() -> str:
    return generate_id(ID_PREFIX_MEMBER)


def new_project_id() -> str:
    return generate_id(ID_PREFIX_PROJECT)


def new_list_id() -> str:
    return generate_id(ID_PREFIX_LIST)


def new_task_id() -> str:
    return generate_id(ID_PREFIX_TASK)


def new_assignee_id() -> str:
    return generate_id(ID_PREFIX_ASSIGNEE)


def new_comment_id() -> str:
    return generate_id(ID_PREFIX_COMMENT)
