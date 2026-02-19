from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_resume, name='upload_resume'),
    path('bulk-upload/', views.bulk_upload, name='bulk_upload'),
    path('dashboard/', views.resume_list, name='resume_list'),
    path('clear-all/', views.clear_all_resumes, name='clear_all_resumes'),
    path('<int:pk>/', views.resume_detail, name='resume_detail'),
    path('secure/dashboard/', views.secure_dashboard, name='secure_dashboard'),
    path('secure/upload/', views.upload_profile, name='upload_profile'),
    path('secure/profile/<int:pk>/', views.profile_detail, name='profile_detail'),
]
