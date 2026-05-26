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
    # AI Filter & Quality Check (batch scan + reports)
    path('ai-filter/', views.ai_filter_page, name='ai_filter'),
    path('ai-filter/results/<int:scan_run_id>/clear/', views.clear_scan_run, name='clear_scan_run'),
    path('ai-filter/results/<int:scan_run_id>/', views.filter_results, name='filter_results'),
    path('ai-filter/report/<int:result_id>/', views.scan_report, name='scan_report'),
    # Match stored resumes with JD (quality check, specs, certificates)
    path('match-stored/', views.match_stored_resumes, name='match_stored'),
    path('delete/<int:pk>/', views.delete_resume, name='delete_resume'),
    # Scan history - JD-wise grouped results
    path('scan-history/', views.scan_history, name='scan_history'),
    path('scan-history/delete/<int:scan_run_id>/', views.delete_scan_run, name='delete_scan_run'),
    path('scan-history/bulk-delete/', views.bulk_delete_scan_runs, name='bulk_delete_scan_runs'),
    # AJAX: extract job title from uploaded JD file
    path('ajax/extract-jd-title/', views.extract_jd_title_ajax, name='extract_jd_title_ajax'),
    # AJAX: fetch JD text + title by internal Job ID
    path('ajax/fetch-jd-by-id/', views.fetch_jd_by_id_ajax, name='fetch_jd_by_id_ajax'),
    # AJAX: fetch JD from external URL
    path('ajax/fetch-jd-from-url/', views.fetch_jd_from_url_ajax, name='fetch_jd_from_url_ajax'),
]
