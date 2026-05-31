import os
from celery import Celery

# Pastikan Django settings ter-load sebelum Celery init
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lms.settings")

app = Celery("lms")

# Baca semua config Celery dari settings.py (prefix CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py di setiap installed app
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Task debug untuk verifikasi Celery berjalan."""
    print(f"Request: {self.request!r}")