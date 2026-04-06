from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.db.models import Count

from .models import Category, Course, Lesson, Enrollment, Progress, UserProfile


# ─────────────────────────────────────────────
# UserProfile — Inline di User Admin
# ─────────────────────────────────────────────

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fields = ('role', 'bio', 'avatar')
    can_delete = False
    verbose_name_plural = 'Profil & Role'
    fk_name = 'user'


class UserAdmin(BaseUserAdmin):
    """Extend User admin bawaan Django dengan UserProfile inline."""
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff')
    list_select_related = ('profile',)

    @admin.display(description='Role', ordering='profile__role')
    def get_role(self, obj):
        try:
            role = obj.profile.get_role_display()
            colors = {'Admin': '#e74c3c', 'Instructor': '#2980b9', 'Student': '#27ae60'}
            color = colors.get(role, '#7f8c8d')
            return format_html(
                '<span style="color:{};font-weight:bold">{}</span>', color, role
            )
        except UserProfile.DoesNotExist:
            return '–'


# Daftarkan ulang User dengan admin yang sudah di-extend
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email', 'bio')
    ordering = ('role', 'user__username')


# ─────────────────────────────────────────────
# Category Admin
# ─────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'course_count', 'created_at')
    list_filter = ('parent',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(course_count=Count('courses'))

    @admin.display(description='Jumlah Kursus', ordering='course_count')
    def course_count(self, obj):
        return obj.course_count


# ─────────────────────────────────────────────
# Lesson Inline (dipakai di CourseAdmin)
# ─────────────────────────────────────────────

class LessonInline(admin.TabularInline):
    model = Lesson
    fields = ('order', 'title', 'duration_minutes', 'is_preview', 'video_url')
    extra = 1
    ordering = ('order',)


# ─────────────────────────────────────────────
# Course Admin
# ─────────────────────────────────────────────

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'instructor', 'category', 'level',
        'price', 'is_published', 'enrollment_count',
        'lesson_count', 'created_at',
    )
    list_filter = ('is_published', 'level', 'category', 'instructor')
    search_fields = ('title', 'description', 'instructor__username')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-created_at',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
    inlines = [LessonInline]

    fieldsets = (
        ('Informasi Dasar', {
            'fields': ('title', 'slug', 'short_description', 'description', 'thumbnail'),
        }),
        ('Pengaturan', {
            'fields': ('instructor', 'category', 'level', 'price', 'is_published'),
        }),
        ('Timestamp', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('instructor', 'category').annotate(
            enrollment_count=Count('enrollments', distinct=True),
            lesson_count=Count('lessons', distinct=True),
        )

    @admin.display(description='Enrollments', ordering='enrollment_count')
    def enrollment_count(self, obj):
        return obj.enrollment_count

    @admin.display(description='Lessons', ordering='lesson_count')
    def lesson_count(self, obj):
        return obj.lesson_count

    @admin.display(description='Dipublikasikan', boolean=True)
    def is_published(self, obj):
        return obj.is_published


# ─────────────────────────────────────────────
# Lesson Admin
# ─────────────────────────────────────────────

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'duration_minutes', 'is_preview', 'created_at')
    list_filter = ('course', 'is_preview')
    search_fields = ('title', 'course__title')
    ordering = ('course', 'order')
    list_per_page = 30


# ─────────────────────────────────────────────
# Progress Inline (dipakai di EnrollmentAdmin)
# ─────────────────────────────────────────────

class ProgressInline(admin.TabularInline):
    model = Progress
    fields = ('lesson', 'is_completed', 'completed_at', 'last_position_seconds')
    readonly_fields = ('completed_at',)
    extra = 0


# ─────────────────────────────────────────────
# Enrollment Admin
# ─────────────────────────────────────────────

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'course', 'enrolled_at',
        'is_active', 'is_completed_display', 'progress_bar',
    )
    list_filter = ('is_active', 'course', 'enrolled_at')
    search_fields = ('student__username', 'course__title')
    ordering = ('-enrolled_at',)
    readonly_fields = ('enrolled_at', 'completed_at')
    inlines = [ProgressInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('student', 'course').annotate(
            total_lessons=Count('course__lessons', distinct=True),
            completed_count=Count(
                'progress', filter=__import__('django.db.models', fromlist=['Q']).Q(
                    progress__is_completed=True
                ), distinct=True
            ),
        )

    @admin.display(description='Selesai', boolean=True)
    def is_completed_display(self, obj):
        return obj.completed_at is not None

    @admin.display(description='Progress')
    def progress_bar(self, obj):
        total = getattr(obj, 'total_lessons', 0)
        done = getattr(obj, 'completed_count', 0)
        if total == 0:
            return '–'
        pct = int((done / total) * 100)
        color = '#4CAF50' if pct == 100 else '#2196F3'
        return format_html(
            '<div style="width:100px;background:#eee;border-radius:4px">'
            '<div style="width:{pct}%;background:{color};height:10px;border-radius:4px"></div>'
            '</div> {done}/{total}',
            pct=pct, color=color, done=done, total=total,
        )


# ─────────────────────────────────────────────
# Progress Admin
# ─────────────────────────────────────────────

@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'lesson', 'is_completed', 'completed_at', 'last_position_seconds')
    list_filter = ('is_completed', 'enrollment__course')
    search_fields = ('enrollment__student__username', 'lesson__title')
    ordering = ('enrollment', 'lesson__order')
