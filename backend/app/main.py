# Application entry point: configure CORS, register routes, and dispose database connections on shutdown.
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.routes.audio import router as audio_router
from app.routes.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifetime and dispose the database engine on shutdown.

    The app argument is supplied by FastAPI; startup currently needs no work.
    """
    yield

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(audio_router)




@app.get("/health")
async def health():
    """Return a basic process-health response.

    This endpoint does not check database or external-provider availability.
    """
    return {
        "status": "ok",
    }
