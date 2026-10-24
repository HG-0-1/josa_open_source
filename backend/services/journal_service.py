"""Owner-scoped journal queries and deterministic, non-clinical summaries."""

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import JournalEntry
from schemas.journal import JournalEntryCreate


MOODS = ("قلق", "حزن", "غضب", "فرح", "هدوء", "توتر")
TRIGGERS = ("دراسة", "شغل", "عائلة", "علاقات", "صحة", "نوم", "غير ذلك")
MIN_PATTERN_ENTRIES = 5


def create_entry(db: Session, user_id: int, payload: JournalEntryCreate) -> JournalEntry:
    entry = JournalEntry(user_id=user_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_entries(db: Session, user_id: int, limit: int, offset: int) -> list[JournalEntry]:
    return list(db.scalars(
        select(JournalEntry)
        .where(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc())
        .limit(limit)
        .offset(offset)
    ))


def get_entries_in_period(db: Session, user_id: int, days: int) -> list[JournalEntry]:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    return list(db.scalars(
        select(JournalEntry)
        .where(JournalEntry.user_id == user_id, JournalEntry.created_at >= since)
        .order_by(JournalEntry.created_at.asc(), JournalEntry.id.asc())
    ))


def build_insights(entries: list[JournalEntry], days: int) -> dict:
    mood_counts = Counter(entry.mood for entry in entries)
    trigger_counts = Counter(entry.trigger_category for entry in entries)
    pairs = Counter((entry.mood, entry.trigger_category) for entry in entries)
    enough = len(entries) >= MIN_PATTERN_ENTRIES

    notes = []
    if not enough:
        notes.append("لسه بدنا تسجيلات أكثر حتى نلاحظ نمط واضح")
    else:
        top_mood = max(MOODS, key=lambda item: mood_counts[item])
        top_trigger = max(TRIGGERS, key=lambda item: trigger_counts[item])
        notes.append(f"أكثر شعور سجلته هو {top_mood} ({mood_counts[top_mood]} مرات).")
        notes.append(f"الفئة الأكثر اختياراً هي {top_trigger} ({trigger_counts[top_trigger]} مرات).")
        repeated = [(mood, trigger, count) for (mood, trigger), count in pairs.items() if count >= 2]
        if repeated:
            mood, trigger, count = max(repeated, key=lambda item: item[2])
            notes.append(
                f"تكرر تسجيل {mood} مع فئة {trigger} {count} مرات؛ هذا تزامن في التسجيلات ولا يثبت سبب الشعور."
            )
        else:
            notes.append("هذه الأعداد تصف ما سجلته فقط، ولا تحدد سبب المشاعر.")

    return {
        "days": days,
        "total_entries": len(entries),
        "mood_counts": [{"label": mood, "count": mood_counts[mood]} for mood in MOODS],
        "trigger_counts": [{"label": category, "count": trigger_counts[category]} for category in TRIGGERS],
        "intensity_trend": [
            {
                "date": _date_label(entry.created_at),
                "mood": entry.mood,
                "intensity": entry.intensity,
            }
            for entry in entries
        ],
        "associations": [
            {"mood": mood, "trigger_category": trigger, "count": count}
            for (mood, trigger), count in sorted(pairs.items())
        ],
        "pattern_notes": notes,
        "sufficient_data": enough,
    }


def aggregate_for_ai(entries: list[JournalEntry]) -> dict:
    """Return only low-detail counts and approved enum values, never user notes."""
    mood_counts = Counter(entry.mood for entry in entries)
    trigger_counts = Counter(entry.trigger_category for entry in entries)
    pairs = Counter((entry.mood, entry.trigger_category) for entry in entries)
    return {
        "entry_count": len(entries),
        "mood_counts": {mood: mood_counts[mood] for mood in MOODS if mood_counts[mood]},
        "trigger_counts": {trigger: trigger_counts[trigger] for trigger in TRIGGERS if trigger_counts[trigger]},
        "repeated_mood_trigger_counts": [
            {"mood": mood, "trigger_category": trigger, "count": count}
            for (mood, trigger), count in sorted(pairs.items()) if count >= 2
        ],
    }


def _date_label(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date().isoformat()


def serialize_entry(entry: JournalEntry) -> dict:
    created_at = entry.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "id": entry.id,
        "mood": entry.mood,
        "intensity": entry.intensity,
        "trigger_category": entry.trigger_category,
        "trigger_note": entry.trigger_note,
        "journal_text": entry.journal_text,
        "created_at": created_at.isoformat(),
    }
