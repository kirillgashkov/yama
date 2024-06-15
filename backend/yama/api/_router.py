from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthOut(BaseModel):
    status: Literal["ok"]


@router.get("/health")
async def get_health() -> HealthOut:
    return HealthOut(status="ok")
