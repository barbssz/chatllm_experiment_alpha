from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.database import Base, engine
from backend.config import ALLOWED_ORIGINS
from backend.routers.auth import router as auth_router
from backend.routers.chat import router as chat_router
from backend.routers.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="ChatLLM Experiment API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    # Nao devolve os inputs originais, que podem conter senhas invalidas.
    return JSONResponse(status_code=422, content={
        "detail": [
            {key: error[key] for key in ("loc", "msg", "type")}
            for error in exc.errors()
        ]
    })

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Requested-With"],
)


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheMiddleware)

app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(sessions_router)

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/")
def root() -> FileResponse:
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="frontend/index.html nao encontrado")
    return FileResponse(index_path, headers=NO_CACHE_HEADERS)
