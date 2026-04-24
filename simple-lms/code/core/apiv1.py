from core.helpers import admin_required, check_course_owner, check_enrollment, get_authenticated_user, instructor_required, student_required
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja_simple_jwt.auth.views.api import mobile_auth_router
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth
from django.contrib.auth.models import User
from courses.models import Comment, Course, CourseContent, CourseMember
from core.schemas import CommentIn, CommentUpdate, CommentUpdate, CourseIn, CourseMemberOut, CourseMemberOut, CourseOut, DetailCourseOut, Register, UserOut
from typing import List

apiv1 = NinjaAPI(
    title="Simple LMS API",
    version="1.0.0",
    description="API untuk Simple Learning Management System"
)

apiv1.add_router("/auth/", mobile_auth_router)

apiAuth = HttpJwtAuth()

@apiv1.get('courses/', response=List[CourseOut])
def listCourses(request):
    """Mengambil daftar semua course."""
    return Course.objects.select_related('teacher').all()

@apiv1.get('courses/{id}', response=DetailCourseOut)
def detailCourse(request, id: int):
    """Mengambil detail course beserta daftar kontennya."""
    try:
        return Course.objects.prefetch_related(
            'coursecontent_set'
        ).select_related('teacher').get(pk=id)
    except Course.DoesNotExist:
        raise HttpError(404, "Course tidak ditemukan")


@apiv1.post('courses/', auth=apiAuth, response=CourseOut)
@instructor_required
def createCourse(request, data: CourseIn):
    user = User.objects.get(pk=request.user.id)

    course = Course.objects.create(
        name=data.name,
        description=data.description,
        price=data.price,
        image=data.image,
        teacher=user  # User yang membuat otomatis jadi teacher
    )
    return course

@apiv1.patch('courses/{id}', auth=apiAuth, response=CourseOut)
@instructor_required
def updateCourse(request, id: int, data: CourseIn):
    user = get_authenticated_user(request)
    course = Course.objects.filter(id=id).first()
    if course is None:
        raise HttpError(404, "Course tidak ditemukan")

    check_course_owner(course, user)  # Otomatis raise 403 jika bukan owner Authorization: hanya course owner yang boleh edit
    
    for attr, value in data.dict(exclude_unset=True).items():
        setattr(course, attr, value)

    course.save()
    return course


@apiv1.delete('courses/{id}', auth=apiAuth)
@admin_required
def deleteCourse(request, id: int):
    user = get_authenticated_user(request)

    course = Course.objects.filter(id=id).first()
    if course is None:
        raise HttpError(404, "Course tidak ditemukan")

    # Authorization: course owner ATAU superadmin
    if course.teacher != user and not user.is_superuser:
        raise HttpError(403, "Anda tidak memiliki izin untuk menghapus course ini")

    course.delete()
    return {"message": "Course berhasil dihapus"}

@apiv1.post('register/', response={201: UserOut})
def register(request, data: Register):
    # Cek apakah username sudah digunakan
    if User.objects.filter(username=data.username).exists():
        raise HttpError(400, "Username sudah digunakan")

    # Cek apakah email sudah digunakan
    if User.objects.filter(email=data.email).exists():
        raise HttpError(400, "Email sudah digunakan")

    # Buat user baru
    # create_user() otomatis melakukan hashing pada password
    newUser = User.objects.create_user(
        username=data.username,
        password=data.password,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name
    )

    return 201, newUser

@apiv1.post('enrollments', auth=apiAuth, response=CourseMemberOut)
@student_required
def courseEnrollment(request, course_id: int):
    user_id = get_authenticated_user(request)
    course = Course.objects.get(pk=course_id)

    # Cek apakah sudah terdaftar
    if CourseMember.objects.filter(user_id=user_id, course_id=course).exists():
        raise HttpError(400, "Anda sudah terdaftar di course ini")

    enrollment = CourseMember.objects.create(
        user_id=user_id,
        course_id=course,
        roles='std'  # Default role: student
    )
    return enrollment

@apiv1.get('enrollments/mycourses', auth=apiAuth, response=List[CourseMemberOut])
@student_required
def getMyCourses(request):
    user_id = get_authenticated_user(request)
    mycourses = CourseMember.objects.filter(
        user_id=user_id
    ).select_related('course_id', 'user_id')
    return mycourses

@apiv1.post('enrollments/{content_id}/progress', auth=apiAuth)
@student_required
def mark_lesson_complete(request, content_id: int):
    """Menandai materi/lesson tertentu telah selesai dikerjakan."""
    user = get_authenticated_user(request)
    content = CourseContent.objects.filter(id=content_id).first()
    
    if not content:
        raise HttpError(404, "Konten tidak ditemukan")
        
    check_enrollment(user, content.course_id)
    
    return {"message": f"Materi {content.name} ditandai sebagai selesai"}
    
@apiv1.post('comments/', auth=apiAuth)
def postComment(request, data: CommentIn):
    user = get_authenticated_user(request)
    content = CourseContent.objects.filter(id=data.content_id).first()

    if content is None:
        raise HttpError(404, "Content tidak ditemukan")

    check_enrollment(user, content.course_id)  # Otomatis raise 403 jika tidak enrolled

    Comment.objects.create(
        comment=data.comment,
        user_id=user,
        content_id=content
    )
    return {"message": "Komentar berhasil ditambahkan"}
    
@apiv1.put('comments/{id}', auth=apiAuth)
def updateComment(request, id: int, data: CommentUpdate):
    user = User.objects.get(pk=request.user.id)

    comment = Comment.objects.filter(id=id).first()
    if comment is None:
        raise HttpError(404, "Komentar tidak ditemukan")

    # Authorization check: apakah user adalah pemilik komentar?
    if comment.user_id != user:
        raise HttpError(403, "Anda tidak memiliki izin untuk mengedit komentar ini")

    comment.comment = data.comment
    comment.save()
    return {"message": "Komentar berhasil diperbarui"}

@apiv1.delete('comments/{id}', auth=apiAuth)
def deleteComment(request, id: int):
    user = User.objects.get(pk=request.user.id)

    comment = Comment.objects.select_related('content_id__course_id').filter(id=id).first()
    if comment is None:
        raise HttpError(404, "Komentar tidak ditemukan")

    # Cek apakah user adalah pemilik komentar
    is_comment_owner = (comment.user_id == user)

    # Cek apakah user adalah pemilik course
    course = comment.content_id.course_id
    is_course_owner = (course.teacher == user)

    # Cek apakah user adalah superadmin
    is_superadmin = user.is_superuser

    if is_comment_owner or is_course_owner or is_superadmin:
        comment.delete()
        return {"message": "Komentar berhasil dihapus"}
    else:
        raise HttpError(403, "Anda tidak memiliki izin untuk menghapus komentar ini")
    
@apiv1.get('auth/me', auth=apiAuth, response=UserOut)
def get_me(request):
    """Mengambil data user yang sedang login"""
    return get_authenticated_user(request)

@apiv1.put('auth/me', auth=apiAuth, response=UserOut)
def update_me(request, data: Register):
    user = get_authenticated_user(request)
    user.first_name = data.first_name
    user.last_name = data.last_name
    user.email = data.email
    # Password hashing jika ingin ganti password
    if data.password:
        user.set_password(data.password)
    user.save()
    return user