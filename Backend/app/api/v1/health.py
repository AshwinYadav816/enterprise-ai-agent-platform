from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up. (Readiness with DB/Redis checks comes in Phase 8.)"""
    return {"status": "ok"}
