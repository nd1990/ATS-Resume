from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_resume, name='upload_resume'),
    path('bulk-upload/', views.bulk_upload, name='bulk_upload'),
    path('dashboard/', views.resume_list, name='resume_list'),
    path('clear-all/', views.clear_all_resumes, name='clear_all_resumes'),
    path('<int:pk>/', views.resume_detail, name='resume_detail'),
]
