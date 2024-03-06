from fastapi import APIRouter

router = APIRouter()


@router.get("/files/{parent_path:path}")
async def create_file() -> None:
    ...


@router.get("/files/{path:path}")
async def read_file() -> None:
    ...


@router.get("/files/{path:path}")
async def update_file() -> None:
    ...


@router.get("/files/{path:path}")
async def delete_file() -> None:
    ...
