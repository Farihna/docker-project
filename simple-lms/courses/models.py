from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


# ─────────────────────────────────────────────
# UserProfile — Role System (admin / instructor / student)
# ─────────────────────────────────────────────

ROLE_ADMIN      = 'admin'
ROLE_INSTRUCTOR = 'instructor'
ROLE_STUDENT    = 'student'

ROLE_CHOICES = [
    (ROLE_ADMIN,      'Admin'),
    (ROLE_INSTRUCTOR, 'Instructor'),
    (ROLE_STUDENT,    'Student'),
]


class UserProfileQuerySet(models.QuerySet):
    def admins(self):
        return self.filter(role=ROLE_ADMIN)

    def instructors(self):
        return self.filter(role=ROLE_INSTRUCTOR)

    def students(self):
        return self.filter(role=ROLE_STUDENT)


class UserProfileManager(models.Manager):
    def get_queryset(self):
        return UserProfileQuerySet(self.model, using=self._db)

    def admins(self):
        return self.get_queryset().admins()

    def instructors(self):
        return self.get_queryset().instructors()

    def students(self):
        return self.get_queryset().students()


class UserProfile(models.Model):
    """
    Ekstensi one-to-one ke auth.User untuk menyimpan role.
    Dibuat otomatis saat User baru dibuat via post_save signal.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='user',
    )
    role = models.CharField(
        'peran',
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_STUDENT,
    )
    bio = models.TextField('bio', blank=True, default='')
    avatar = models.ImageField('avatar', upload_to='avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserProfileManager()

    class Meta:
        verbose_name = 'Profil Pengguna'
        verbose_name_plural = 'Profil Pengguna'
        indexes = [
            models.Index(fields=['role'], name='idx_profile_role'),
        ]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    # ── Helper properties ──────────────────────────────────────────────
    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_instructor(self):
        return self.role == ROLE_INSTRUCTOR

    @property
    def is_student(self):
        return self.role == ROLE_STUDENT


# Signal: otomatis buat UserProfile saat User baru dibuat
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Superuser otomatis jadi admin
        role = ROLE_ADMIN if instance.is_superuser else ROLE_STUDENT
        UserProfile.objects.get_or_create(user=instance, defaults={'role': role})


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


# ─────────────────────────────────────────────
# Category (Self-referencing hierarchy)
# ─────────────────────────────────────────────

class CategoryQuerySet(models.QuerySet):
    def top_level(self):
        """Hanya kategori root (tanpa parent)."""
        return self.filter(parent=None)

    def with_course_count(self):
        from django.db.models import Count
        return self.annotate(course_count=Count('course'))


class CategoryManager(models.Manager):
    def get_queryset(self):
        return CategoryQuerySet(self.model, using=self._db)

    def top_level(self):
        return self.get_queryset().top_level()

    def with_course_count(self):
        return self.get_queryset().with_course_count()


class Category(models.Model):
    name = models.CharField("nama kategori", max_length=100)
    slug = models.SlugField("slug", unique=True, max_length=120)
    description = models.TextField("deskripsi", blank=True, default='')
    parent = models.ForeignKey(
        'self',
        verbose_name="kategori induk",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CategoryManager()

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategori"
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

    def get_ancestors(self):
        """Kembalikan list ancestor dari root ke parent."""
        ancestors = []
        current = self.parent
        while current is not None:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors


# ─────────────────────────────────────────────
# Course
# ─────────────────────────────────────────────

class CourseQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

    def for_listing(self):
        """
        Optimized queryset untuk list view.
        Menghindari N+1: eager-load instructor & category,
        annotate enrollment_count & lesson_count.
        """
        from django.db.models import Count
        return (
            self.published()
            .select_related('instructor', 'category', 'category__parent')
            .annotate(
                enrollment_count=Count('enrollments', distinct=True),
                lesson_count=Count('lessons', distinct=True),
            )
            .order_by('-created_at')
        )

    def for_instructor(self, user):
        return self.filter(instructor=user)


class CourseManager(models.Manager):
    def get_queryset(self):
        return CourseQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def for_listing(self):
        return self.get_queryset().for_listing()

    def for_instructor(self, user):
        return self.get_queryset().for_instructor(user)


LEVEL_CHOICES = [
    ('beginner', 'Beginner'),
    ('intermediate', 'Intermediate'),
    ('advanced', 'Advanced'),
]


class Course(models.Model):
    title = models.CharField("judul", max_length=200)
    slug = models.SlugField("slug", unique=True, max_length=220)
    description = models.TextField("deskripsi", default='')
    short_description = models.CharField("deskripsi singkat", max_length=300, blank=True)
    thumbnail = models.ImageField("thumbnail", upload_to='courses/thumbnails/', null=True, blank=True)
    price = models.DecimalField("harga", max_digits=10, decimal_places=2, default=0)
    level = models.CharField("level", max_length=20, choices=LEVEL_CHOICES, default='beginner')
    is_published = models.BooleanField("dipublikasikan", default=False)

    instructor = models.ForeignKey(
        User,
        verbose_name="instruktur",
        on_delete=models.RESTRICT,
        related_name='courses_taught',
    )
    category = models.ForeignKey(
        Category,
        verbose_name="kategori",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CourseManager()

    class Meta:
        verbose_name = "Kursus"
        verbose_name_plural = "Kursus"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug'], name='idx_course_slug'),
            models.Index(fields=['is_published', '-created_at'], name='idx_course_pub_date'),
            models.Index(fields=['instructor'], name='idx_course_instructor'),
            models.Index(fields=['category'], name='idx_course_category'),
        ]

    def __str__(self):
        return self.title

    @property
    def is_free(self):
        return self.price == 0


# ─────────────────────────────────────────────
# Lesson
# ─────────────────────────────────────────────

class Lesson(models.Model):
    course = models.ForeignKey(
        Course,
        verbose_name="kursus",
        on_delete=models.CASCADE,
        related_name='lessons',
    )
    title = models.CharField("judul lesson", max_length=200)
    description = models.TextField("deskripsi", blank=True, default='')
    video_url = models.URLField("URL video", max_length=500, blank=True)
    duration_minutes = models.PositiveIntegerField("durasi (menit)", default=0)
    order = models.PositiveIntegerField("urutan", default=0)
    is_preview = models.BooleanField("bisa dipreview gratis", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lesson"
        verbose_name_plural = "Lesson"
        ordering = ['course', 'order']
        indexes = [
            models.Index(fields=['course', 'order'], name='idx_lesson_course_order'),
        ]

    def __str__(self):
        return f"[{self.course.title}] #{self.order} {self.title}"


# ─────────────────────────────────────────────
# Enrollment
# ─────────────────────────────────────────────

class EnrollmentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_student_dashboard(self, user):
        """
        Optimized queryset untuk dashboard student.
        Eager-load course + instructor + category,
        annotate completed_lessons & total_lessons untuk progress.
        """
        from django.db.models import Count, Q
        return (
            self.active()
            .filter(student=user)
            .select_related(
                'course',
                'course__instructor',
                'course__category',
            )
            .prefetch_related('course__lessons')
            .annotate(
                total_lessons=Count('course__lessons', distinct=True),
                completed_lessons=Count(
                    'progress',
                    filter=Q(progress__is_completed=True),
                    distinct=True,
                ),
            )
            .order_by('-enrolled_at')
        )


class EnrollmentManager(models.Manager):
    def get_queryset(self):
        return EnrollmentQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_student_dashboard(self, user):
        return self.get_queryset().for_student_dashboard(user)


class Enrollment(models.Model):
    student = models.ForeignKey(
        User,
        verbose_name="student",
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(
        Course,
        verbose_name="kursus",
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    enrolled_at = models.DateTimeField("tanggal enroll", auto_now_add=True)
    is_active = models.BooleanField("aktif", default=True)
    completed_at = models.DateTimeField("tanggal selesai", null=True, blank=True)

    objects = EnrollmentManager()

    class Meta:
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollment"
        # Unique constraint: 1 student hanya bisa enroll 1x per course
        unique_together = [('student', 'course')]
        indexes = [
            models.Index(fields=['student', 'is_active'], name='idx_enrollment_student_active'),
            models.Index(fields=['course'], name='idx_enrollment_course'),
        ]

    def __str__(self):
        return f"{self.student.username} → {self.course.title}"

    @property
    def is_completed(self):
        return self.completed_at is not None

    def mark_completed(self):
        self.completed_at = timezone.now()
        self.save(update_fields=['completed_at'])


# ─────────────────────────────────────────────
# Progress (tracking lesson completion per enrollment)
# ─────────────────────────────────────────────

class Progress(models.Model):
    enrollment = models.ForeignKey(
        Enrollment,
        verbose_name="enrollment",
        on_delete=models.CASCADE,
        related_name='progress',
    )
    lesson = models.ForeignKey(
        Lesson,
        verbose_name="lesson",
        on_delete=models.CASCADE,
        related_name='progress_records',
    )
    is_completed = models.BooleanField("selesai", default=False)
    completed_at = models.DateTimeField("waktu selesai", null=True, blank=True)
    last_position_seconds = models.PositiveIntegerField(
        "posisi terakhir (detik)", default=0,
        help_text="Posisi video terakhir ditonton"
    )

    class Meta:
        verbose_name = "Progress"
        verbose_name_plural = "Progress"
        unique_together = [('enrollment', 'lesson')]
        indexes = [
            models.Index(fields=['enrollment', 'is_completed'], name='idx_progress_enrollment_done'),
        ]

    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"{status} {self.enrollment.student.username} - {self.lesson.title}"

    def mark_complete(self):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=['is_completed', 'completed_at'])
