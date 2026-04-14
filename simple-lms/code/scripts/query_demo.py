import os
import sys
import django
from django.db import connection, reset_queries
    
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms.settings')
django.setup()

from courses.models import Course

def run_demo():
    print("--- DEMO N+1 PROBLEM ---")
    reset_queries()
    courses = Course.objects.all() # Tanpa optimasi
    for course in courses:
        print(f"Course: {course.title} by {course.instructor.username}")
    print(f"Total Query (Tanpa Optimasi): {len(connection.queries)}")

    print("\n--- DEMO OPTIMIZED QUERY ---")
    reset_queries()
    optimized_courses = Course.objects.for_listing() # Dengan select_related
    for course in optimized_courses:
        print(f"Course: {course.title} by {course.instructor.username}")
    print(f"Total Query (Dengan Optimasi): {len(connection.queries)}")

if __name__ == "__main__":
    run_demo()