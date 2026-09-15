from fastapi import APIRouter
router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
async def get_health():
    return {"status": "healthy", "service": "SmikHub"}
