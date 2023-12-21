from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from app.routes.api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.requests_client = httpx.AsyncClient()
    yield
    await app.requests_client.aclose()

app = FastAPI(lifespan=lifespan)

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", port=8080, host="0.0.0.0")
