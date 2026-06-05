import json
import logging
import hashlib
import functools
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from ninja.errors import HttpError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache Key Builders
# ---------------------------------------------------------------------------

COURSE_LIST_KEY   = "course:list"
COURSE_DETAIL_KEY = "course:detail:{id}"


def _make_key(base: str, **kwargs) -> str:
    """Bangun cache key dari base string dan parameter opsional."""
    return base.format(**kwargs)


# ---------------------------------------------------------------------------
# Cache Response Decorator
# ---------------------------------------------------------------------------

def cache_response(key_template: str, timeout: int | None = None):
    """
    Decorator untuk cache hasil endpoint Django Ninja.

    Args:
        key_template : String template key, misal "course:detail:{id}"
        timeout      : TTL dalam detik. Default: settings.CACHE_TTL atau 600 detik.

    Usage:
        @apiv1.get('courses/')
        @cache_response(key_template=COURSE_LIST_KEY, timeout=600)
        def listCourses(request):
            ...

        @apiv1.get('courses/{id}')
        @cache_response(key_template=COURSE_DETAIL_KEY, timeout=900)
        def detailCourse(request, id: int):
            ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Build final cache key (substitusi {id}, dll dari kwargs)
            cache_key = _make_key(key_template, **kwargs)
            ttl = timeout or getattr(settings, "CACHE_TTL", {}).get(
                cache_key.split(":")[1], 60 * 10
            )

            # Coba ambil dari cache dulu
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache HIT: %s", cache_key)
                return cached

            # Cache MISS → jalankan view asli
            logger.debug("Cache MISS: %s", cache_key)
            result = view_func(request, *args, **kwargs)

            # Simpan ke cache (Django ninja mengembalikan queryset/model,
            # django-redis serializes otomatis via pickle)
            try:
                cache.set(cache_key, result, ttl)
            except Exception as exc:
                logger.error("Cache SET failed (%s): %s", cache_key, exc)

            return result
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Cache Invalidation
# ---------------------------------------------------------------------------

def invalidate_course_cache(course_id: int | None = None):
    """
    Hapus cache course saat data berubah (create / update / delete).

    - Selalu invalidate course list (karena list berubah)
    - Jika course_id diberikan, invalidate detail course tersebut juga

    Dipanggil dari: createCourse, updateCourse, deleteCourse di apiv1.py
    """
    keys_to_delete = [COURSE_LIST_KEY]

    if course_id is not None:
        keys_to_delete.append(_make_key(COURSE_DETAIL_KEY, id=course_id))

    deleted = cache.delete_many(keys_to_delete)
    logger.info("Cache invalidated: %s (deleted=%s)", keys_to_delete, deleted)


# ---------------------------------------------------------------------------
# Rate Limiting Decorator (Redis-based, Sliding Window)
# ---------------------------------------------------------------------------

def rate_limit(max_requests: int | None = None, window_seconds: int | None = None):
    """
    Decorator rate limiting berbasis Redis (fixed window counter).

    Default limit diambil dari settings.RATE_LIMIT:
        RATE_LIMIT = {"requests": 60, "window": 60}

    Identifier: user_id jika authenticated, IP jika anonymous.

    Usage:
        @apiv1.get('courses/')
        @rate_limit()  # pakai default dari settings
        def listCourses(request): ...

        @apiv1.post('comments/')
        @rate_limit(max_requests=30, window_seconds=60)
        def postComment(request, data): ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            cfg          = getattr(settings, "RATE_LIMIT", {})
            max_req      = max_requests      or cfg.get("requests", 60)
            window_sec   = window_seconds    or cfg.get("window",   60)

            # Identifier
            if hasattr(request, "user") and request.user and request.user.is_authenticated:
                identifier = f"user:{request.user.id}"
            else:
                # X-Forwarded-For untuk reverse proxy, fallback ke REMOTE_ADDR
                ip = (
                    request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                    or request.META.get("REMOTE_ADDR", "unknown")
                )
                identifier = f"ip:{ip}"

            rl_key = f"ratelimit:{view_func.__name__}:{identifier}"

            try:
                count = cache.get(rl_key, 0)

                if count >= max_req:
                    logger.warning("Rate limit exceeded: %s", rl_key)
                    raise HttpError(
                        429,
                        f"Terlalu banyak request. Coba lagi dalam {window_sec} detik."
                    )

                # Increment counter; set TTL hanya pada request pertama
                if count == 0:
                    cache.set(rl_key, 1, window_sec)
                else:
                    cache.incr(rl_key)

            except HttpError:
                raise
            except Exception as exc:
                # Jika Redis down, lanjutkan tanpa rate limit (fail-open)
                logger.error("Rate limit Redis error: %s", exc)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator