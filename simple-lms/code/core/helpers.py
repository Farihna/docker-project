from django.contrib.auth.models import User
from ninja.errors import HttpError
from functools import wraps


def get_authenticated_user(request):
    """Mendapatkan objek User dari request yang terautentikasi."""
    return User.objects.get(pk=request.user.id)


def check_course_owner(course, user):
    """Memeriksa apakah user adalah pemilik course."""
    if course.teacher != user:
        raise HttpError(403, "Hanya pemilik course yang dapat melakukan aksi ini")


def check_owner_or_superadmin(obj_owner, user):
    """Memeriksa apakah user adalah pemilik objek atau superadmin."""
    if obj_owner != user and not user.is_superuser:
        raise HttpError(403, "Anda tidak memiliki izin untuk melakukan aksi ini")


def check_enrollment(user, course):
    """Memeriksa apakah user terdaftar di course tertentu."""
    from courses.models import CourseMember
    if not CourseMember.objects.filter(user_id=user, course_id=course).exists():
        raise HttpError(403, "Anda tidak terdaftar di course ini")
    

def instructor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_staff and not user.is_superuser:
            raise HttpError(403, "Hanya instruktur yang dapat melakukan aksi ini")
            
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_superuser:
            raise HttpError(403, "Hanya admin yang dapat melakukan aksi ini")
        return view_func(request, *args, **kwargs)
    return wrapper

def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_active:
            raise HttpError(403, "Hanya student aktif yang dapat melakukan aksi ini")
            
        return view_func(request, *args, **kwargs)
    return wrapper