from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import (
    ParseError,
    ValidationError,
    ContextError,
    MatchError,
    RewriteError,
    JobNotFoundError,
    CVOptimizerError,
)


async def cv_optimizer_exception_handler(request: Request, exc: Exception):
    status_map: dict[type[Exception], int] = {
        ParseError: 422,
        ValidationError: 422,
        JobNotFoundError: 404,
        ContextError: 500,
        MatchError: 500,
        RewriteError: 500,
        CVOptimizerError: 500,
    }
    return JSONResponse(
        status_code=status_map.get(type(exc), 500),
        content={"error": str(exc)},
    )
