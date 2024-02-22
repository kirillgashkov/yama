from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
async def get_health() -> Health:
    return Health(status="ok")
