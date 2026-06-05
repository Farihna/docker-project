import logging
from datetime import datetime, timezone
from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client = None
_db     = None


def get_db():
    """
    Mengembalikan MongoDB database instance (lazy init, singleton).
    Jika koneksi gagal, kembalikan None agar app tidak crash.
    """
    global _client, _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure

        _client = MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=3000,  # timeout 3 detik
        )
        # Verifikasi koneksi
        _client.admin.command("ping")
        _db = _client[settings.MONGODB_DB]

        # Pastikan indexes ada (idempotent)
        _ensure_indexes(_db)
        logger.info("MongoDB connected: %s / %s", settings.MONGODB_URI, settings.MONGODB_DB)
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", exc)
        _db = None
    return _db


def _ensure_indexes(db):
    """Buat indexes yang diperlukan (dipanggil sekali saat init)."""
    db.activity_logs.create_index([("user_id", 1), ("created_at", -1)])
    db.activity_logs.create_index([("event_type", 1)])
    db.activity_logs.create_index([("course_id", 1)])
    db.course_stats.create_index([("course_id", 1)], unique=True)


# ---------------------------------------------------------------------------
# Activity Log
# ---------------------------------------------------------------------------

# Tipe event yang valid
class EventType:
    USER_LOGIN      = "user_login"
    VIEW_COURSE     = "view_course"
    ENROLL_COURSE   = "enroll_course"
    VIEW_CONTENT    = "view_content"
    POST_COMMENT    = "post_comment"
    COMPLETE_LESSON = "complete_lesson"
    EXPORT_REPORT   = "export_report"


def log_activity(
    event_type: str,
    user_id: int | None = None,
    username: str | None = None,
    course_id: int | None = None,
    content_id: int | None = None,
    metadata: dict | None = None,
) -> bool:
    """
    Catat satu activity log ke MongoDB.

    Args:
        event_type  : Konstanta dari EventType
        user_id     : ID user Django (opsional untuk event anonymous)
        username    : Username string
        course_id   : ID course yang terlibat (opsional)
        content_id  : ID content yang terlibat (opsional)
        metadata    : Dict tambahan bebas

    Returns:
        True jika berhasil, False jika gagal (tidak raise exception)
    """
    db = get_db()
    if db is None:
        return False

    doc = {
        "event_type": event_type,
        "user_id":    user_id,
        "username":   username,
        "course_id":  course_id,
        "content_id": content_id,
        "metadata":   metadata or {},
        "created_at": datetime.now(timezone.utc),
    }

    try:
        db.activity_logs.insert_one(doc)
        return True
    except Exception as exc:
        logger.error("log_activity failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Learning Analytics - Aggregation Queries
# ---------------------------------------------------------------------------

def get_enrollment_analytics(course_id: int | None = None) -> list:
    """
    Jumlah enrollment per course.
    Jika course_id diberikan, filter hanya course tersebut.

    Returns:
        [{"course_id": int, "total_enrollments": int}, ...]
    """
    db = get_db()
    if db is None:
        return []

    match_stage = {"event_type": EventType.ENROLL_COURSE}
    if course_id:
        match_stage["course_id"] = course_id

    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id":               "$course_id",
            "total_enrollments": {"$sum": 1},
        }},
        {"$project": {
            "_id":               0,
            "course_id":         "$_id",
            "total_enrollments": 1,
        }},
        {"$sort": {"total_enrollments": -1}},
    ]

    try:
        return list(db.activity_logs.aggregate(pipeline))
    except Exception as exc:
        logger.error("get_enrollment_analytics failed: %s", exc)
        return []


def get_activity_summary(days: int = 7) -> list:
    """
    Ringkasan aktivitas per hari dalam N hari terakhir.

    Returns:
        [{"date": "YYYY-MM-DD", "event_type": str, "count": int}, ...]
    """
    db = get_db()
    if db is None:
        return []

    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": {
                "date":       {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "event_type": "$event_type",
            },
            "count": {"$sum": 1},
        }},
        {"$project": {
            "_id":        0,
            "date":       "$_id.date",
            "event_type": "$_id.event_type",
            "count":      1,
        }},
        {"$sort": {"date": -1, "event_type": 1}},
    ]

    try:
        return list(db.activity_logs.aggregate(pipeline))
    except Exception as exc:
        logger.error("get_activity_summary failed: %s", exc)
        return []


def get_active_users(top_n: int = 10) -> list:
    """
    Top N user paling aktif berdasarkan jumlah aktivitas.

    Returns:
        [{"user_id": int, "username": str, "activity_count": int}, ...]
    """
    db = get_db()
    if db is None:
        return []

    pipeline = [
        {"$match": {"user_id": {"$ne": None}}},
        {"$group": {
            "_id":            "$user_id",
            "username":       {"$last": "$username"},
            "activity_count": {"$sum": 1},
        }},
        {"$project": {
            "_id":            0,
            "user_id":        "$_id",
            "username":       1,
            "activity_count": 1,
        }},
        {"$sort":  {"activity_count": -1}},
        {"$limit": top_n},
    ]

    try:
        return list(db.activity_logs.aggregate(pipeline))
    except Exception as exc:
        logger.error("get_active_users failed: %s", exc)
        return []


def upsert_course_stats(course_id: int, stats: dict) -> bool:
    """
    Upsert snapshot statistik course (dipanggil oleh Celery Beat task).

    Args:
        course_id : ID course
        stats     : Dict berisi statistik, misal {"total_members": 42}
    """
    db = get_db()
    if db is None:
        return False

    try:
        db.course_stats.update_one(
            {"course_id": course_id},
            {"$set": {**stats, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return True
    except Exception as exc:
        logger.error("upsert_course_stats failed: %s", exc)
        return False