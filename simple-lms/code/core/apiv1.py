"""
core/apiv1.py
REST API endpoints untuk Simple LMS.

Progress 4 — tambahan:
  - Redis caching pada listCourses & detailCourse
  - Cache invalidation pada create/update/delete Course
  - Rate limiting (60 req/menit) pada endpoint publik
  - MongoDB activity logging pada setiap aksi penting
  - Celery async tasks: enrollment email & certificate generation
"""

from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja_simple_jwt.auth.views.api import mobile_auth_router
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth
from django.contrib.auth.models import User
from typing import List

from courses.models import Comment, Course, CourseContent, CourseMember
from core.schemas import (
    CommentIn, CommentUpdate,
    CourseIn, CourseMemberOut, CourseOut, DetailCourseOut,
    Register, UserOut,
    AnalyticsOut,          # schema baru — lihat schemas.py
)
from core.helpers import (
    admin_required, check_course_owner, check_enrollment,
    get_authenticated_user, instructor_required, student_required,
)
from core.cache import (
    cache_response, invalidate_course_cache, rate_limit,
    COURSE_LIST_KEY, COURSE_DETAIL_KEY,
)
from core.mongodb import log_activity, EventType, get_enrollment_analytics, get_activity_summary

apiv1 = NinjaAPI(
    title="Simple LMS API",
    version="1.0.0",
    description="API untuk Simple Learning Management System",
)

apiv1.add_router("/auth/", mobile_auth_router)

apiAuth = HttpJwtAuth()


# =============================================================================
# COURSES
# =============================================================================

@apiv1.get("courses/", response=List[CourseOut])
@rate_limit()
@cache_response(key_template=COURSE_LIST_KEY, timeout=60 * 10)
def listCourses(request):
    """
    Ambil semua course.
    - Cache TTL : 10 menit
    - Rate limit: 60 req/menit per user/IP
    """
    log_activity(
        event_type=EventType.VIEW_COURSE,
        user_id=getattr(request.user, "id", None),
        username=getattr(request.user, "username", None),
    )
    return Course.objects.select_related("teacher").all()


@apiv1.get("courses/{id}", response=DetailCourseOut)
@rate_limit()
@cache_response(key_template=COURSE_DETAIL_KEY, timeout=60 * 15)
def detailCourse(request, id: int):
    """
    Ambil detail 1 course beserta daftar kontennya.
    - Cache TTL : 15 menit
    - Rate limit: 60 req/menit per user/IP
    """
    try:
        course = (
            Course.objects
            .prefetch_related("coursecontent_set")
            .select_related("teacher")
            .get(pk=id)
        )
    except Course.DoesNotExist:
        raise HttpError(404, "Course tidak ditemukan")

    log_activity(
        event_type=EventType.VIEW_COURSE,
        user_id=getattr(request.user, "id", None),
        username=getattr(request.user, "username", None),
        course_id=id,
    )
    return course


@apiv1.post("courses/", auth=apiAuth, response=CourseOut)
@instructor_required
def createCourse(request, data: CourseIn):
    """Buat course baru. Otomatis invalidate cache course list."""
    user   = User.objects.get(pk=request.user.id)
    course = Course.objects.create(
        name=data.name,
        description=data.description,
        price=data.price,
        image=data.image,
        teacher=user,
    )
    invalidate_course_cache()           # list berubah → hapus cache list
    return course


@apiv1.patch("courses/{id}", auth=apiAuth, response=CourseOut)
@instructor_required
def updateCourse(request, id: int, data: CourseIn):
    """Update course. Invalidate cache list & detail."""
    user   = get_authenticated_user(request)
    course = Course.objects.filter(id=id).first()
    if course is None:
        raise HttpError(404, "Course tidak ditemukan")

    check_course_owner(course, user)

    for attr, value in data.dict(exclude_unset=True).items():
        setattr(course, attr, value)
    course.save()

    invalidate_course_cache(course_id=id)   # hapus cache list + detail
    return course


@apiv1.delete("courses/{id}", auth=apiAuth)
@admin_required
def deleteCourse(request, id: int):
    """Hapus course. Invalidate cache list & detail."""
    user   = get_authenticated_user(request)
    course = Course.objects.filter(id=id).first()
    if course is None:
        raise HttpError(404, "Course tidak ditemukan")

    if course.teacher != user and not user.is_superuser:
        raise HttpError(403, "Anda tidak memiliki izin untuk menghapus course ini")

    course.delete()
    invalidate_course_cache(course_id=id)
    return {"message": "Course berhasil dihapus"}


# =============================================================================
# AUTH / USER
# =============================================================================

@apiv1.post("register/", response={201: UserOut})
def register(request, data: Register):
    if User.objects.filter(username=data.username).exists():
        raise HttpError(400, "Username sudah digunakan")
    if User.objects.filter(email=data.email).exists():
        raise HttpError(400, "Email sudah digunakan")

    new_user = User.objects.create_user(
        username=data.username,
        password=data.password,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
    )
    return 201, new_user


@apiv1.get("auth/me", auth=apiAuth, response=UserOut)
def get_me(request):
    """Ambil data user yang sedang login."""
    user = get_authenticated_user(request)
    log_activity(
        event_type=EventType.USER_LOGIN,
        user_id=user.id,
        username=user.username,
    )
    return user


@apiv1.put("auth/me", auth=apiAuth, response=UserOut)
def update_me(request, data: Register):
    user = get_authenticated_user(request)
    user.first_name = data.first_name
    user.last_name  = data.last_name
    user.email      = data.email
    if data.password:
        user.set_password(data.password)
    user.save()
    return user


# =============================================================================
# ENROLLMENTS
# =============================================================================

@apiv1.post("enrollments", auth=apiAuth, response=CourseMemberOut)
@student_required
def courseEnrollment(request, course_id: int):
    """
    Daftarkan student ke course.
    Setelah berhasil, kirim email konfirmasi via Celery (async).
    """
    user   = get_authenticated_user(request)
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise HttpError(404, "Course tidak ditemukan")

    if CourseMember.objects.filter(user_id=user, course_id=course).exists():
        raise HttpError(400, "Anda sudah terdaftar di course ini")

    enrollment = CourseMember.objects.create(
        user_id=user,
        course_id=course,
        roles="std",
    )

    # --- Async: kirim email konfirmasi ---
    from courses.tasks import send_enrollment_email
    send_enrollment_email.delay(user.email, user.username, course.name)

    # --- Log ke MongoDB ---
    log_activity(
        event_type=EventType.ENROLL_COURSE,
        user_id=user.id,
        username=user.username,
        course_id=course_id,
        metadata={"course_name": course.name},
    )

    return enrollment


@apiv1.get("enrollments/mycourses", auth=apiAuth, response=List[CourseMemberOut])
@student_required
def getMyCourses(request):
    user      = get_authenticated_user(request)
    mycourses = CourseMember.objects.filter(
        user_id=user
    ).select_related("course_id", "user_id")
    return mycourses


@apiv1.post("enrollments/{content_id}/progress", auth=apiAuth)
@student_required
def mark_lesson_complete(request, content_id: int):
    """
    Tandai lesson selesai.
    Jika sudah selesai semua konten course, trigger generate_certificate.
    """
    user    = get_authenticated_user(request)
    content = CourseContent.objects.filter(id=content_id).first()
    if not content:
        raise HttpError(404, "Konten tidak ditemukan")

    check_enrollment(user, content.course_id)

    log_activity(
        event_type=EventType.COMPLETE_LESSON,
        user_id=user.id,
        username=user.username,
        course_id=content.course_id.id,
        content_id=content_id,
    )

    # Hitung apakah semua konten sudah selesai (simplified: cek jumlah progress log)
    total_contents    = CourseContent.objects.filter(course_id=content.course_id).count()
    completed_count   = _count_completed_lessons(user.id, content.course_id.id)

    if completed_count >= total_contents and total_contents > 0:
        from courses.tasks import generate_certificate
        generate_certificate.delay(
            user.id, user.username,
            content.course_id.id, content.course_id.name,
        )
        return {"message": f"Selamat! Course {content.course_id.name} selesai. Sertifikat sedang dibuat."}

    return {"message": f"Materi '{content.name}' ditandai sebagai selesai ({completed_count}/{total_contents})"}


def _count_completed_lessons(user_id: int, course_id: int) -> int:
    """Hitung jumlah lesson yang sudah diselesaikan user di suatu course (via MongoDB log)."""
    from core.mongodb import get_db
    db = get_db()
    if db is None:
        return 0
    return db.activity_logs.count_documents({
        "event_type": EventType.COMPLETE_LESSON,
        "user_id":    user_id,
        "course_id":  course_id,
    })


# =============================================================================
# COMMENTS
# =============================================================================

@apiv1.post("comments/", auth=apiAuth)
def postComment(request, data: CommentIn):
    user    = get_authenticated_user(request)
    content = CourseContent.objects.filter(id=data.content_id).first()
    if content is None:
        raise HttpError(404, "Content tidak ditemukan")

    check_enrollment(user, content.course_id)

    # Pada models.py Comment menggunakan member_id (CourseMember), bukan user_id langsung
    member = CourseMember.objects.filter(user_id=user, course_id=content.course_id).first()
    if member is None:
        raise HttpError(403, "Anda tidak terdaftar di course ini")

    Comment.objects.create(
        comment=data.comment,
        member_id=member,
        content_id=content,
    )

    log_activity(
        event_type=EventType.POST_COMMENT,
        user_id=user.id,
        username=user.username,
        course_id=content.course_id.id,
        content_id=data.content_id,
    )

    return {"message": "Komentar berhasil ditambahkan"}


@apiv1.put("comments/{id}", auth=apiAuth)
def updateComment(request, id: int, data: CommentUpdate):
    user    = User.objects.get(pk=request.user.id)
    comment = Comment.objects.filter(id=id).first()
    if comment is None:
        raise HttpError(404, "Komentar tidak ditemukan")

    if comment.member_id.user_id != user:
        raise HttpError(403, "Anda tidak memiliki izin untuk mengedit komentar ini")

    comment.comment = data.comment
    comment.save()
    return {"message": "Komentar berhasil diperbarui"}


@apiv1.delete("comments/{id}", auth=apiAuth)
def deleteComment(request, id: int):
    user    = User.objects.get(pk=request.user.id)
    comment = Comment.objects.select_related("content_id__course_id").filter(id=id).first()
    if comment is None:
        raise HttpError(404, "Komentar tidak ditemukan")

    is_comment_owner = (comment.member_id.user_id == user)
    is_course_owner  = (comment.content_id.course_id.teacher == user)
    is_superadmin    = user.is_superuser

    if is_comment_owner or is_course_owner or is_superadmin:
        comment.delete()
        return {"message": "Komentar berhasil dihapus"}
    raise HttpError(403, "Anda tidak memiliki izin untuk menghapus komentar ini")


# =============================================================================
# ANALYTICS (MongoDB)
# =============================================================================

@apiv1.get("analytics/enrollments", auth=apiAuth, response=List[AnalyticsOut])
@admin_required
def analyticsEnrollments(request, course_id: int = None):
    """
    Jumlah enrollment per course (dari MongoDB aggregation).
    Hanya bisa diakses admin/superuser.
    """
    data = get_enrollment_analytics(course_id=course_id)
    return [AnalyticsOut(**row) for row in data]


@apiv1.get("analytics/activity", auth=apiAuth)
@admin_required
def analyticsActivity(request, days: int = 7):
    """
    Ringkasan aktivitas per hari dalam N hari terakhir.
    Hanya bisa diakses admin/superuser.
    """
    return get_activity_summary(days=days)