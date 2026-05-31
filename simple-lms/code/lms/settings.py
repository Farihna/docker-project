"""
Django settings untuk Simple LMS
Progress 4: Advanced Features & Integration

Tambahan dari Progress sebelumnya:
- Redis  : Caching & Rate Limiting
- MongoDB: Activity Log & Learning Analytics
- Celery : Async Tasks (RabbitMQ sebagai broker)
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-lab05-db-optimization-simple-lms-key-2025"
)

DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]


# =============================================================================
# Aplikasi yang terdaftar
# =============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Profiling
    "silk",
    # Auth
    "ninja_simple_jwt",
    # Celery scheduler & results
    "django_celery_beat",
    "django_celery_results",
    # LMS apps
    "courses",
]

# =============================================================================
# Middleware
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "silk.middleware.SilkyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "lms.wsgi.application"


# =============================================================================
# Database - PostgreSQL
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "lms_db"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("DB_HOST", "database"),
        "PORT": "5432",
    }
}


# =============================================================================
# Redis - Caching & Rate Limiting
# =============================================================================

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,          # Jika Redis down, fallback ke no-cache
        },
        "KEY_PREFIX": "lms",                    # Prefix semua cache key
        "TIMEOUT": 60 * 15,                     # Default TTL: 15 menit
    }
}

# Cache key untuk setiap resource
CACHE_TTL = {
    "course_list":   60 * 10,   # 10 menit
    "course_detail": 60 * 15,   # 15 menit
}

# Rate Limiting config (requests per window)
RATE_LIMIT = {
    "requests": 60,
    "window":   60,   # detik
}


# =============================================================================
# MongoDB - Activity Log & Analytics
# =============================================================================

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://mongodb:27017/")
MONGODB_DB  = os.environ.get("MONGODB_DB", "lms_logs")


# =============================================================================
# Celery - Async Task Queue (RabbitMQ sebagai broker)
# =============================================================================

CELERY_BROKER_URL         = os.environ.get("CELERY_BROKER_URL", "amqp://guest:guest@rabbitmq:5672//")
CELERY_RESULT_BACKEND     = "django-db"          # Simpan hasil task di PostgreSQL
CELERY_CACHE_BACKEND      = "django-cache"
CELERY_ACCEPT_CONTENT     = ["json"]
CELERY_TASK_SERIALIZER    = "json"
CELERY_RESULT_SERIALIZER  = "json"
CELERY_TIMEZONE           = "Asia/Jakarta"
CELERY_ENABLE_UTC         = True

# Celery Beat - Scheduled tasks
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Jadwal periodik (bisa juga dikelola via Django Admin setelah migrasi)
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Jalankan setiap jam untuk update statistik enrollment
    "update-course-statistics-hourly": {
        "task":     "courses.tasks.update_course_statistics",
        "schedule": crontab(minute=0),            # setiap awal jam
    },
    # Generate report CSV setiap hari pukul 01.00 WIB
    "export-course-report-daily": {
        "task":     "courses.tasks.export_course_report",
        "schedule": crontab(hour=1, minute=0),
    },
}


# =============================================================================
# Email
# =============================================================================

EMAIL_BACKEND       = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST          = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT          = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL  = EMAIL_HOST_USER


# =============================================================================
# Django Silk - Query Profiling (dev only)
# =============================================================================

SILKY_PYTHON_PROFILER = True
SILKY_META            = True


# =============================================================================
# Password Validation
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# =============================================================================
# Internationalization
# =============================================================================

LANGUAGE_CODE = "id"
TIME_ZONE     = "Asia/Jakarta"
USE_I18N      = True
USE_TZ        = True


# =============================================================================
# Static & Media Files
# =============================================================================

STATIC_URL = "static/"
MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"