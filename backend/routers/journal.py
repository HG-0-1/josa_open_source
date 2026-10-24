from asyncio import to_thread

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete
from sqlalchemy.orm import Session

from database import get_db
from models import JournalEntry
from schemas.journal import (
    AiInsightsOut,
    AiInsightsRequest,
    JournalEntriesOut,
    JournalEntryCreate,
    JournalEntryOut,
)
from services import journal_ai_service, journal_service
from services.auth_service import AuthContext, require_auth, require_csrf


router = APIRouter(prefix="/api/journal", tags=["journal"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"


@router.post("/entries", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
async def create_entry(
    payload: JournalEntryCreate,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> JournalEntryOut:
    entry = journal_service.create_entry(db, context.user.id, payload)
    _no_store(response)
    return journal_service.serialize_entry(entry)


@router.get("/entries", response_model=JournalEntriesOut)
async def list_entries(
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    entries = journal_service.list_entries(db, context.user.id, limit, offset)
    _no_store(response)
    return {
        "entries": [journal_service.serialize_entry(entry) for entry in entries],
        "limit": limit,
        "offset": offset,
    }


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: int,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    result = db.execute(
        delete(JournalEntry).where(
            JournalEntry.id == entry_id,
            JournalEntry.user_id == context.user.id,
        )
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=404, detail="اليومية غير موجودة.")
    db.commit()
    _no_store(response)
    return {"ok": True}


@router.get("/insights")
async def get_insights(
    response: Response,
    days: int = Query(default=7, ge=7, le=30),
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if days not in (7, 30):
        raise HTTPException(status_code=422, detail="اختر 7 أو 30 يوماً.")
    entries = journal_service.get_entries_in_period(db, context.user.id, days)
    _no_store(response)
    return journal_service.build_insights(entries, days)


@router.post("/ai-insights", response_model=AiInsightsOut)
async def get_ai_insights(
    payload: AiInsightsRequest,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> AiInsightsOut:
    entries = journal_service.get_entries_in_period(db, context.user.id, payload.days)
    if len(entries) < journal_service.MIN_PATTERN_ENTRIES:
        raise HTTPException(
            status_code=409,
            detail="لسه بدنا تسجيلات أكثر حتى نلاحظ نمط واضح.",
        )
    try:
        reflection = await to_thread(journal_ai_service.reflect, entries, payload.days)
    except journal_ai_service.JournalAIUnavailable:
        raise HTTPException(
            status_code=503,
            detail="خدمة التأمل الآلي غير متاحة حالياً. حاول لاحقاً.",
        ) from None
    _no_store(response)
    return reflection
