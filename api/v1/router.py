from fastapi import APIRouter

from app.api.v1 import auth, lists, projects, tasks, teams, users
from app.api.v1.webhooks import router as webhooks

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(teams.router)
api_router.include_router(projects.router)
api_router.include_router(lists.router)
api_router.include_router(tasks.router)
api_router.include_router(webhooks.router)



@api_router.get("/health")
def health():
    return {"status": "ok"}
