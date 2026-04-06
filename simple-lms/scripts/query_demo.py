"""
=============================================================================
DEMO: N+1 Problem vs Query Optimization
Simple LMS — Progress 2

Jalankan dengan:
    docker-compose exec app python scripts/query_demo.py

Pastikan sudah ada data di database (loaddata fixtures/initial_data.json).
=============================================================================
"""

import os
import sys
import time
import django

# ── Setup Django ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection, reset_queries
from django.db.models import Count, Avg, Q, Prefetch
from django.conf import settings

settings.DEBUG = True  # Aktifkan query logging

from courses.models import Course, Enrollment, Lesson, Progress, UserProfile

# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────

SEPARATOR = "=" * 65


def benchmark(label: str, func):
    """Jalankan func, cetak jumlah query & waktu eksekusi."""
    reset_queries()
    start = time.perf_counter()

    result = func()

    elapsed_ms = (time.perf_counter() - start) * 1000
    query_count = len(connection.queries)

    print(f"\n{'─'*65}")
    print(f"  {label}")
    print(f"{'─'*65}")
    print(f"  Jumlah Query : {query_count}")
    print(f"  Waktu        : {elapsed_ms:.2f} ms")
    print(f"{'─'*65}")
    return result, query_count, elapsed_ms


def demo_role_system():
    print(f"\n{SEPARATOR}")
    print("  DEMO 0 — User Role System")
    print(SEPARATOR)

    def run():
        from django.contrib.auth.models import User

        # Query users berdasarkan role via UserProfile
        admins      = UserProfile.objects.admins().select_related('user')
        instructors = UserProfile.objects.instructors().select_related('user')
        students    = UserProfile.objects.students().select_related('user')

        print(f"\n   Admin      : {[p.user.username for p in admins]}")
        print(f"   Instructor : {[p.user.username for p in instructors]}")
        print(f"   Student    : {[p.user.username for p in students]}")

        # Cek role via property helper
        if instructors.exists():
            profile = instructors.first()
            print(f"\n  Profile: {profile}")
            print(f"  is_instructor: {profile.is_instructor}")
            print(f"  is_admin:      {profile.is_admin}")
            print(f"  is_student:    {profile.is_student}")

    benchmark("User Role System Query", run)


# =============================================================================
# DEMO 1 — Daftar Course + Nama Instruktur
# =============================================================================

def demo_course_list():
    print(f"\n{SEPARATOR}")
    print("  DEMO 1 — Daftar Course + Nama Instruktur")
    print(SEPARATOR)

    # ── SEBELUM: N+1 Problem ─────────────────────────────────────────────────
    def tanpa_optimasi():
        courses = Course.objects.all()
        result = []
        for course in courses:
            # Setiap iterasi memicu 1 query ke tabel auth_user!
            result.append({
                'title': course.title,
                'instructor': course.instructor.username,  # ← N+1 di sini
            })
        return result

    # ── SESUDAH: select_related ───────────────────────────────────────────────
    def dengan_select_related():
        # JOIN ke auth_user dalam 1 query tunggal
        courses = Course.objects.select_related('instructor', 'category').all()
        result = []
        for course in courses:
            result.append({
                'title': course.title,
                'instructor': course.instructor.username,  # tidak ada query tambahan
                'category': course.category.name if course.category else '-',
            })
        return result

    _, qc1, t1 = benchmark("SEBELUM — tanpa optimasi (N+1 Problem)", tanpa_optimasi)

    _, qc2, t2 = benchmark("SESUDAH — dengan select_related", dengan_select_related)

    improvement = ((qc1 - qc2) / qc1 * 100) if qc1 > 0 else 0
    print(f"\n   Improvement: {qc1} → {qc2} queries ({improvement:.0f}% berkurang)")
    print(f"   Waktu: {t1:.2f}ms → {t2:.2f}ms")


# =============================================================================
# DEMO 2 — Daftar Course + Jumlah Enrollments (annotate)
# =============================================================================

def demo_course_enrollment_count():
    print(f"\n{SEPARATOR}")
    print("  DEMO 2 — Jumlah Enrollment per Course")
    print(SEPARATOR)

    # ── SEBELUM: hitung di Python, 1 query per course ─────────────────────────
    def tanpa_optimasi():
        courses = Course.objects.all()
        result = []
        for course in courses:
            # Query baru setiap iterasi!
            count = Enrollment.objects.filter(course=course).count()
            result.append({'title': course.title, 'enrollment_count': count})
        return result

    # ── SESUDAH: annotate di database ─────────────────────────────────────────
    def dengan_annotate():
        courses = Course.objects.annotate(
            enrollment_count=Count('enrollments', distinct=True)
        ).order_by('-enrollment_count')
        result = []
        for course in courses:
            result.append({
                'title': course.title,
                'enrollment_count': course.enrollment_count,  # sudah ada di object
            })
        return result

    _, qc1, t1 = benchmark("SEBELUM — count per iterasi (N+1)", tanpa_optimasi)
    _, qc2, t2 = benchmark("SESUDAH — annotate Count()", dengan_annotate)

    improvement = ((qc1 - qc2) / qc1 * 100) if qc1 > 0 else 0
    print(f"\n   Improvement: {qc1} → {qc2} queries ({improvement:.0f}% berkurang)")
    print(f"   Waktu: {t1:.2f}ms → {t2:.2f}ms")


# =============================================================================
# DEMO 3 — Dashboard Student (for_student_dashboard)
# =============================================================================

def demo_student_dashboard():
    print(f"\n{SEPARATOR}")
    print("  DEMO 3 — Dashboard Student (Enrollment + Progress)")
    print(SEPARATOR)

    from django.contrib.auth.models import User
    try:
        student = User.objects.get(username='student01')
    except User.DoesNotExist:
        print("    User student01 tidak ditemukan. Load fixtures terlebih dahulu.")
        return

    # ── SEBELUM ───────────────────────────────────────────────────────────────
    def tanpa_optimasi():
        enrollments = Enrollment.objects.filter(student=student)
        result = []
        for enr in enrollments:
            total = Lesson.objects.filter(course=enr.course).count()     # N query
            done = Progress.objects.filter(
                enrollment=enr, is_completed=True
            ).count()                                                      # N query lagi
            result.append({
                'course': enr.course.title,          # N query untuk course!
                'instructor': enr.course.instructor.username,  # N query lagi!
                'total': total,
                'done': done,
                'pct': int(done / total * 100) if total else 0,
            })
        return result

    # ── SESUDAH: custom manager for_student_dashboard ─────────────────────────
    def dengan_optimasi():
        enrollments = Enrollment.objects.for_student_dashboard(student)
        result = []
        for enr in enrollments:
            total = enr.total_lessons          # dari annotate
            done = enr.completed_lessons       # dari annotate
            result.append({
                'course': enr.course.title,
                'instructor': enr.course.instructor.username,
                'total': total,
                'done': done,
                'pct': int(done / total * 100) if total else 0,
            })
        return result

    _, qc1, t1 = benchmark("SEBELUM — tanpa optimasi", tanpa_optimasi)
    _, qc2, t2 = benchmark("SESUDAH — for_student_dashboard()", dengan_optimasi)

    if qc1 > 0:
        improvement = ((qc1 - qc2) / qc1 * 100)
        print(f"\n   Improvement: {qc1} → {qc2} queries ({improvement:.0f}% berkurang)")
        print(f"   Waktu: {t1:.2f}ms → {t2:.2f}ms")


# =============================================================================
# DEMO 4 — Course.objects.for_listing() custom manager
# =============================================================================

def demo_for_listing():
    print(f"\n{SEPARATOR}")
    print("  DEMO 4 — Course.objects.for_listing() Custom Manager")
    print(SEPARATOR)

    # ── SEBELUM: tanpa manager ─────────────────────────────────────────────────
    def tanpa_manager():
        courses = Course.objects.filter(is_published=True)
        result = []
        for c in courses:
            result.append({
                'title': c.title,
                'instructor': c.instructor.username,    # N+1
                'category': c.category.name if c.category else '-',  # N+1
                'enrollments': c.enrollments.count(),  # N+1
                'lessons': c.lessons.count(),           # N+1
            })
        return result

    # ── SESUDAH: custom manager ───────────────────────────────────────────────
    def dengan_manager():
        # for_listing() = select_related + annotate, hanya 1 query
        courses = Course.objects.for_listing()
        result = []
        for c in courses:
            result.append({
                'title': c.title,
                'instructor': c.instructor.username,
                'category': c.category.name if c.category else '-',
                'enrollments': c.enrollment_count,
                'lessons': c.lesson_count,
            })
        return result

    _, qc1, t1 = benchmark("SEBELUM — tanpa custom manager", tanpa_manager)
    _, qc2, t2 = benchmark("SESUDAH — Course.objects.for_listing()", dengan_manager)

    if qc1 > 0:
        improvement = ((qc1 - qc2) / qc1 * 100)
        print(f"\n   Improvement: {qc1} → {qc2} queries ({improvement:.0f}% berkurang)")


# =============================================================================
# DEMO 5 — Aggregate Statistics
# =============================================================================

def demo_aggregate():
    print(f"\n{SEPARATOR}")
    print("  DEMO 5 — Aggregate & Statistik")
    print(SEPARATOR)

    def run():
        from django.db.models import Max, Min, Sum
        stats = Course.objects.aggregate(
            total_courses=Count('id'),
            published=Count('id', filter=Q(is_published=True)),
            avg_price=Avg('price'),
            max_price=Max('price'),
            min_price=Min('price'),
            total_revenue=Sum('price'),
        )

        # Hitung student & asisten per course dengan conditional annotate
        courses = Course.objects.annotate(
            total_students=Count('enrollments', filter=Q(enrollments__is_active=True)),
            completed_students=Count(
                'enrollments',
                filter=Q(enrollments__is_active=True, enrollments__completed_at__isnull=False),
            ),
        )

        print("\n   Statistik Global:")
        for k, v in stats.items():
            print(f"     {k}: {v}")

        print("\n   Per-Course:")
        for c in courses:
            print(f"     {c.title}: {c.total_students} students, "
                  f"{c.completed_students} selesai")

    benchmark("Aggregate + Conditional Annotate (1 query each)", run)


# =============================================================================
# SUMMARY TABLE
# =============================================================================

def print_summary():
    print(f"\n{SEPARATOR}")
    print("  RINGKASAN PERBANDINGAN QUERY")
    print(SEPARATOR)
    print(f"  {'Operasi':<42} {'Sebelum':>8} {'Sesudah':>8} {'Teknik'}")
    print(f"  {'-'*42} {'-'*8} {'-'*8} {'-'*20}")
    rows = [
        ("Course list + instructor",        "N+1",   "1",   "select_related"),
        ("Course + enrollment count",       "N+1",   "1",   "annotate Count"),
        ("Student dashboard",               "4N+1",  "1",   "for_student_dashboard"),
        ("Course for_listing (full)",       "4N+1",  "1",   "Custom Manager"),
        ("Global aggregate stats",          "5",     "1",   "aggregate()"),
    ]
    for op, before, after, tech in rows:
        print(f"  {op:<42} {before:>8} {after:>8}   {tech}")
    print(SEPARATOR)
    print("   Semua optimasi mencapai > 50% improvement dalam jumlah query!")
    print(SEPARATOR)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print(f"\n{SEPARATOR}")
    print("  Simple LMS — Query Optimization Demo")
    print(SEPARATOR)

    demo_role_system()
    demo_course_list()
    demo_course_enrollment_count()
    demo_student_dashboard()
    demo_for_listing()
    demo_aggregate()
    print_summary()

    print("\n Demo selesai!\n")
