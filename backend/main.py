from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers.panic import router as panic_router
from routers.reframe import router as reframe_router
from routers.auth import router as auth_router
from routers.journal import router as journal_router
from database import init_database
from services.auth_service import allowed_origins


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="Motanafas AI",
    description="Mental Wellness Awareness API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins()),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
    allow_credentials=True,
)

app.include_router(reframe_router)
app.include_router(panic_router)
app.include_router(auth_router)
app.include_router(journal_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Pydantic's default errors echo input; keep thoughts out of error responses.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ]
        },
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to Motanafas AI API"}


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "motanafas-backend"}
