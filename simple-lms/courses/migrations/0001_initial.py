from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Category ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='nama kategori')),
                ('slug', models.SlugField(max_length=120, unique=True, verbose_name='slug')),
                ('description', models.TextField(blank=True, default='', verbose_name='deskripsi')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parent', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='children',
                    to='courses.category',
                    verbose_name='kategori induk',
                )),
            ],
            options={
                'verbose_name': 'Kategori',
                'verbose_name_plural': 'Kategori',
                'ordering': ['name'],
            },
        ),

        # ── Course ─────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200, verbose_name='judul')),
                ('slug', models.SlugField(max_length=220, unique=True, verbose_name='slug')),
                ('description', models.TextField(default='', verbose_name='deskripsi')),
                ('short_description', models.CharField(blank=True, max_length=300, verbose_name='deskripsi singkat')),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='courses/thumbnails/', verbose_name='thumbnail')),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='harga')),
                ('level', models.CharField(
                    choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')],
                    default='beginner', max_length=20, verbose_name='level',
                )),
                ('is_published', models.BooleanField(default=False, verbose_name='dipublikasikan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instructor', models.ForeignKey(
                    on_delete=django.db.models.deletion.RESTRICT,
                    related_name='courses_taught',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='instruktur',
                )),
                ('category', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='courses',
                    to='courses.category',
                    verbose_name='kategori',
                )),
            ],
            options={
                'verbose_name': 'Kursus',
                'verbose_name_plural': 'Kursus',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='course',
            index=models.Index(fields=['slug'], name='idx_course_slug'),
        ),
        migrations.AddIndex(
            model_name='course',
            index=models.Index(fields=['is_published', '-created_at'], name='idx_course_pub_date'),
        ),
        migrations.AddIndex(
            model_name='course',
            index=models.Index(fields=['instructor'], name='idx_course_instructor'),
        ),
        migrations.AddIndex(
            model_name='course',
            index=models.Index(fields=['category'], name='idx_course_category'),
        ),

        # ── Lesson ─────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200, verbose_name='judul lesson')),
                ('description', models.TextField(blank=True, default='', verbose_name='deskripsi')),
                ('video_url', models.URLField(blank=True, max_length=500, verbose_name='URL video')),
                ('duration_minutes', models.PositiveIntegerField(default=0, verbose_name='durasi (menit)')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='urutan')),
                ('is_preview', models.BooleanField(default=False, verbose_name='bisa dipreview gratis')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lessons',
                    to='courses.course',
                    verbose_name='kursus',
                )),
            ],
            options={
                'verbose_name': 'Lesson',
                'verbose_name_plural': 'Lesson',
                'ordering': ['course', 'order'],
            },
        ),
        migrations.AddIndex(
            model_name='lesson',
            index=models.Index(fields=['course', 'order'], name='idx_lesson_course_order'),
        ),

        # ── Enrollment ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('enrolled_at', models.DateTimeField(auto_now_add=True, verbose_name='tanggal enroll')),
                ('is_active', models.BooleanField(default=True, verbose_name='aktif')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='tanggal selesai')),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enrollments',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='student',
                )),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enrollments',
                    to='courses.course',
                    verbose_name='kursus',
                )),
            ],
            options={
                'verbose_name': 'Enrollment',
                'verbose_name_plural': 'Enrollment',
            },
        ),
        migrations.AlterUniqueTogether(
            name='enrollment',
            unique_together={('student', 'course')},
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['student', 'is_active'], name='idx_enrollment_student_active'),
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['course'], name='idx_enrollment_course'),
        ),

        # ── Progress ───────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Progress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('is_completed', models.BooleanField(default=False, verbose_name='selesai')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='waktu selesai')),
                ('last_position_seconds', models.PositiveIntegerField(default=0, verbose_name='posisi terakhir (detik)')),
                ('enrollment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progress',
                    to='courses.enrollment',
                    verbose_name='enrollment',
                )),
                ('lesson', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progress_records',
                    to='courses.lesson',
                    verbose_name='lesson',
                )),
            ],
            options={
                'verbose_name': 'Progress',
                'verbose_name_plural': 'Progress',
            },
        ),
        migrations.AlterUniqueTogether(
            name='progress',
            unique_together={('enrollment', 'lesson')},
        ),
        migrations.AddIndex(
            model_name='progress',
            index=models.Index(fields=['enrollment', 'is_completed'], name='idx_progress_enrollment_done'),
        ),
    ]
