# importer.py
import csv
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms.settings')
django.setup()

from courses.models import Course, User, Enrollment, Category

def import_courses(csv_file):
    print("=== Importing Courses ===")
    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        category, _ = Category.objects.get_or_create(name="Umum")
        
        for row in reader:
            teacher, _ = User.objects.get_or_create(
                username=row['teacher_username'],
                defaults={'role': 'INSTRUCTOR'}
            )
            
            course, created = Course.objects.get_or_create(
                title=row['name'], 
                defaults={
                    'description': row['description'],
                    'instructor': teacher, 
                    'category': category,
                }
            )
            if created:
                print(f"[CREATED] Course: {course.title}")
            else:
                print(f"[EXISTS]  Course: {course.title}")

def import_members(csv_file):
    print("\n=== Importing Members ===")
    if not os.path.exists(csv_file):
        print("File members.csv tidak ditemukan, skip...")
        return

    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                course = Course.objects.get(title=row['course_name'])
                user, _ = User.objects.get_or_create(
                    username=row['username'],
                    defaults={'role': 'STUDENT'}
                )
                
                # Enrollment adalah pengganti CourseMember
                member, created = Enrollment.objects.get_or_create(
                    course=course,
                    student=user
                )
                if created:
                    print(f"[CREATED] Member: {user.username} -> {course.title}")
                else:
                    print(f"[EXISTS]  Member: {user.username} -> {course.title}")
            except Course.DoesNotExist:
                print(f"[ERROR] Course {row['course_name']} tidak ditemukan.")

if __name__ == '__main__':
    import_courses('fixtures/courses.csv') 
    import_members('fixtures/members.csv')
    print("\nImport selesai!")