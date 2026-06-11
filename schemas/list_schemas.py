from datetime import datetime

from pydantic import BaseModel, Field


class ListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    position: int = 0


class ListUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    position: int | None = None


class ListOut(BaseModel):
    id: str
    project_id: str
    name: str
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}
