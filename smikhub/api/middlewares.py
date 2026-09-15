from fastapi import Request
from fastapi.responses import JSONResponse

async def global_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "SmikHub Core Error", "detail": str(exc)[:150]}
        )
