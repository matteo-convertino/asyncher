from fastapi import APIRouter

from app.src.endpoints import sync

router = APIRouter()
router.include_router(sync.router)
