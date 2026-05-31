"""
courses/tasks.py
Celery async tasks untuk Simple LMS.

Tasks:
1. send_enrollment_email    → email konfirmasi enroll (triggered on-demand)
2. generate_certificate     → simulasi generate sertifikat (triggered on-demand)
3. update_course_statistics → update statistik enrollment (Celery Beat, per jam)
4. export_course_report     → export CSV laporan course (Celery Beat, harian)
"""

import csv
import logging
import os
from datetime import datetime, timezone

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


# =============================================================================
# 1. send_enrollment_email
# =============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,   # retry setelah 30 detik
    name="courses.tasks.send_enrollment_email",
)
def send_enrollment_email(self, user_email: str, username: str, course_name: str):
    """
    Kirim email konfirmasi enrollment secara async.

    Args:
        user_email  : Alamat email penerima
        username    : Nama user
        course_name : Nama course yang di-enroll

    Dipanggil dari:
        tasks.send_enrollment_email.delay(user.email, user.username, course.name)
    """
    subject = f"Konfirmasi Pendaftaran: {course_name}"
    message = (
        f"Halo {username},\n\n"
        f"Selamat! Anda telah berhasil mendaftar ke course:\n"
        f"  📚 {course_name}\n\n"
        f"Mulai belajar sekarang di platform Simple LMS kami.\n\n"
        f"Salam,\nTim Simple LMS"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        logger.info("Enrollment email sent to %s for course '%s'", user_email, course_name)
        return {"status": "sent", "recipient": user_email, "course": course_name}

    except Exception as exc:
        logger.error("Failed to send enrollment email: %s", exc)
        # Retry otomatis hingga max_retries kali
        raise self.retry(exc=exc)


# =============================================================================
# 2. generate_certificate
# =============================================================================

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="courses.tasks.generate_certificate",
)
def generate_certificate(self, user_id: int, username: str, course_id: int, course_name: str):
    """
    Generate sertifikat penyelesaian course secara async.

    Implementasi ini membuat file .txt sebagai simulasi.
    Pada production, ganti dengan PDF generation (reportlab/weasyprint).

    Args:
        user_id     : ID user Django
        username    : Nama user
        course_id   : ID course
        course_name : Nama course

    Dipanggil dari:
        tasks.generate_certificate.delay(user.id, user.username, course.id, course.name)
    """
    try:
        # Direktori output sertifikat
        cert_dir = os.path.join(settings.MEDIA_ROOT, "certificates")
        os.makedirs(cert_dir, exist_ok=True)

        timestamp  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        cert_file  = os.path.join(cert_dir, f"cert_{user_id}_{course_id}_{timestamp}.txt")
        issued_at  = datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")

        content = (
            "=" * 60 + "\n"
            "         SERTIFIKAT PENYELESAIAN COURSE\n"
            "              Simple LMS Platform\n"
            "=" * 60 + "\n\n"
            f"  Diberikan kepada : {username}\n"
            f"  Course           : {course_name}\n"
            f"  Course ID        : {course_id}\n"
            f"  Tanggal          : {issued_at}\n\n"
            "  Atas penyelesaian seluruh materi dengan baik.\n\n"
            "=" * 60 + "\n"
        )

        with open(cert_file, "w") as f:
            f.write(content)

        # Log ke MongoDB
        from core.mongodb import log_activity, EventType
        log_activity(
            event_type=EventType.COMPLETE_LESSON,
            user_id=user_id,
            username=username,
            course_id=course_id,
            metadata={"certificate_file": cert_file, "issued_at": issued_at},
        )

        logger.info("Certificate generated: %s", cert_file)
        return {"status": "generated", "file": cert_file}

    except Exception as exc:
        logger.error("generate_certificate failed: %s", exc)
        raise self.retry(exc=exc)


# =============================================================================
# 3. update_course_statistics  (Celery Beat — setiap jam)
# =============================================================================

@shared_task(name="courses.tasks.update_course_statistics")
def update_course_statistics():
    """
    Update jumlah enrollment tiap course dan simpan ke MongoDB (course_stats).
    Dijalankan periodik oleh Celery Beat setiap awal jam.

    Tidak ada argumen — task ini mengambil data langsung dari DB.
    """
    from courses.models import Course, CourseMember
    from core.mongodb import upsert_course_stats

    courses = Course.objects.all()
    updated = 0

    for course in courses:
        total_members = CourseMember.objects.filter(course_id=course).count()
        stats = {
            "course_name":   course.name,
            "total_members": total_members,
        }
        if upsert_course_stats(course.id, stats):
            updated += 1

    logger.info("update_course_statistics: %d courses updated", updated)
    return {"status": "done", "courses_updated": updated}


# =============================================================================
# 4. export_course_report  (Celery Beat — setiap hari jam 01.00)
# =============================================================================

@shared_task(name="courses.tasks.export_course_report")
def export_course_report():
    """
    Generate laporan semua course ke file CSV secara async.
    Output disimpan di media/reports/report_YYYYMMDD.csv

    Dijalankan periodik oleh Celery Beat setiap hari pukul 01.00 WIB.
    Bisa juga di-trigger manual:
        tasks.export_course_report.delay()
    """
    from courses.models import Course, CourseMember
    from core.mongodb import log_activity, EventType

    report_dir = os.path.join(settings.MEDIA_ROOT, "reports")
    os.makedirs(report_dir, exist_ok=True)

    date_str    = datetime.now(timezone.utc).strftime("%Y%m%d")
    report_file = os.path.join(report_dir, f"report_{date_str}.csv")

    fieldnames = [
        "course_id",
        "course_name",
        "teacher",
        "price",
        "total_members",
        "created_at",
    ]

    try:
        courses = Course.objects.select_related("teacher").all()
        rows    = []

        for course in courses:
            total_members = CourseMember.objects.filter(course_id=course).count()
            rows.append({
                "course_id":     course.id,
                "course_name":   course.name,
                "teacher":       course.teacher.username,
                "price":         course.price,
                "total_members": total_members,
                "created_at":    course.created_at.strftime("%Y-%m-%d %H:%M"),
            })

        with open(report_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        # Catat ke MongoDB activity log
        log_activity(
            event_type=EventType.EXPORT_REPORT,
            metadata={"report_file": report_file, "total_courses": len(rows)},
        )

        logger.info("Course report exported: %s (%d rows)", report_file, len(rows))
        return {"status": "done", "file": report_file, "rows": len(rows)}

    except Exception as exc:
        logger.error("export_course_report failed: %s", exc)
        return {"status": "error", "error": str(exc)}