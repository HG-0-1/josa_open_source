from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers.panic import router as panic_router
from routers.reframe import router as reframe_router


app = FastAPI(
    title="Motanafas AI",
    description="Mental Wellness Awareness API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(reframe_router)
app.include_router(panic_router)


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
def health() -> dict[str, str]:
    return {"status": "ok", "service": "motanafas-backend"}
