from django.db import models

class CourseQuerySet(models.QuerySet):
    def for_listing(self):
        return self.select_related('instructor', 'category').all()

class EnrollmentQuerySet(models.QuerySet):
    def for_student_dashboard(self):
        return self.select_related('student', 'course').prefetch_related('progress_set')

class CourseManager(models.Manager):
    def get_queryset(self):
        return CourseQuerySet(self.model, using=self._db)

    def for_listing(self):
        return self.get_queryset().for_listing()

class EnrollmentManager(models.Manager):
    def get_queryset(self):
        return EnrollmentQuerySet(self.model, using=self._db)

    def for_student_dashboard(self):
        return self.get_queryset().for_student_dashboard()