from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.database.session import engine
import app.models

# Automatically create database tables if they do not exist
app.models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Hafte-Yar API",
    description="سیستم مدیریت تسک تیمی",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

