from django.contrib import admin
from django.urls import path, include
from core.apiv1 import apiv1

urlpatterns = [
    path('admin/', admin.site.urls),
    path('silk/', include('silk.urls', namespace='silk')),
    path('', include('courses.urls')),
    path('api/v1/', apiv1.urls),

]
