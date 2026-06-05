from django.db.models import Avg, Count, Max, Min, Q, F
from django.http import JsonResponse

from .models import Comment, Course, CourseContent, CourseMember


def course_list_baseline(request):
  courses = Course.objects.all()
  data = []
  for c in courses:
    data.append({
      'course': c.name,
      'teacher': c.teacher.username,
    })
  return JsonResponse({'data': data})

def course_list_optimized(request):
  courses = Course.objects.select_related('teacher').all()
  data = []
  for c in courses:
    data.append({
      'course': c.name,
      'teacher': c.teacher.username,
    })
  return JsonResponse({'data': data})

def course_members_baseline(request):
  courses = Course.objects.all()
  payload = []
  for c in courses:
    payload.append({
      'course': c.name,
      'member_count': c.coursemember_set.count(),
    })
  return JsonResponse({'data': payload})

def course_members_optimized(request):
  courses = Course.objects.select_related('teacher').prefetch_related(
    'coursemember_set',
    'coursemember_set__comment_set'
    ).all()
  payload = []
  for c in courses:
    payload.append({
      'course': c.name,
      'member_count': c.coursemember_set.count(),
    })
  return JsonResponse({'data': payload})

def course_dashboard_baseline(request):
  courses = Course.objects.all()
  for c in courses:
    members = CourseMember.objects.filter(course_id=c).count()  
  return JsonResponse({'data': members})

def course_dashboard_optimized(request):
  stats = Course.objects.aggregate(
    total=Count('id'),
    max_price=Max('price'),
    min_price=Min('price'),
    avg_price=Avg('price'),
  )
  for c in stats:
    members = CourseMember.objects.count()  
  return JsonResponse({'data': members})
  
def bulk_insert_baseline(request, course_id):
  course = Course.objects.get(id=course_id)
  for i in range(1000):
    content = CourseContent(name=f'Content Baseline {i}', course_id=course)
    content.save()
  return JsonResponse({'status': 'success'})

def bulk_insert_optimized(request, course_id):
  course = Course.objects.get(id=course_id)
  contents = [
    CourseContent(name=f'Content Optimized {i}', course_id=course)
    for i in range(1000)
  ]
  CourseContent.objects.bulk_create(contents, batch_size=500)
  return JsonResponse({'status': 'success'})

def bulk_update_baseline(request):
    courses = Course.objects.all()
    for c in courses:
        c.price = c.price * 1.1
        c.save()
    return JsonResponse({'status': 'success'})

def bulk_update_optimized(request):
    Course.objects.all().update(price=F('price') * 1.1)
    return JsonResponse({'status': 'success'})