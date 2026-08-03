from fastapi import APIRouter
router = APIRouter(prefix="/api", tags=["Health"])
@router.get("/health")
def health_check():
    return {"status":"ok","message":"Solar Analyzer Backend is running","version":"1.1.0"}
