from django.shortcuts import render, redirect, get_object_or_404
from .models import Resume, ResumeScore
from .forms import ResumeUploadForm, BulkUploadForm
from jobs.models import JobRequirement
from ai_engine.parser import extract_resume_text
from ai_engine.screener import calculate_resume_score
import os
import zipfile
from django.core.files.base import ContentFile

def upload_resume(request):
    if request.method == 'POST':
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            resume = form.save()
            
            # 1. Parse content
            # Ensure file is saved before accessing path
            try:
                resume.parsed_content = extract_resume_text(resume.file.path)
                resume.save()
            except Exception as e:
                print(f"Parsing error: {e}")
            
            # 2. Trigger AI Scoring for all active Jobs (Simple MVP)
            # In production, this would be a background task (Celery)
            jobs = JobRequirement.objects.all()
            for job in jobs:
                try:
                    scores = calculate_resume_score(resume.parsed_content, job.description, job.required_skills)
                    
                    ResumeScore.objects.create(
                        resume=resume,
                        job=job,
                        match_percentage=scores['final_score'],
                        skill_match_score=scores['skill_score'],
                        missing_skills=scores['missing_skills'],
                        matched_skills=scores['matched_skills'],
                        classification=scores['classification'],
                        ai_explanation=f"Semantic Score: {scores['semantic_score']}%. Skills Found: {len(scores['matched_skills'])}/{len(scores['matched_skills']) + len(scores['missing_skills'])}."
                    )
                except Exception as e:
                    print(f"Scoring error for job {job.id}: {e}")
            
            return redirect('resume_list')
    else:
        form = ResumeUploadForm()
    return render(request, 'resumes/upload.html', {'form': form})

def resume_list(request):
    # Show all scores, or group by job? 
    # For now, simplistic list of all applications
    scores = ResumeScore.objects.all().select_related('resume', 'job').order_by('-match_percentage')
    return render(request, 'resumes/resume_list.html', {'scores': scores})

def resume_detail(request, pk):
    score = get_object_or_404(ResumeScore, pk=pk)
    return render(request, 'resumes/resume_detail.html', {'score': score})

def bulk_upload(request):
    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            job = form.cleaned_data['job']
            files = request.FILES.getlist('resumes')
            
            for f in files:
                try:
                    # Filter only PDF/DOCX
                    if not f.name.lower().endswith(('.pdf', '.docx')):
                        continue
                        
                    # Create Resume object
                    resume = Resume()
                    resume.file = f 
                    # Extract simple name from path if directory upload sends paths
                    fname = os.path.basename(f.name) 
                    resume.candidate_name = os.path.splitext(fname)[0].replace('_', ' ').title()
                    resume.save()
                    
                    # Parse and Score
                    try:
                        resume.parsed_content = extract_resume_text(resume.file.path)
                        resume.save()
                        
                        scores = calculate_resume_score(resume.parsed_content, job.description, job.required_skills)
                        
                        ResumeScore.objects.create(
                            resume=resume,
                            job=job,
                            match_percentage=scores['final_score'],
                            skill_match_score=scores['skill_score'],
                            missing_skills=scores['missing_skills'],
                            matched_skills=scores['matched_skills'],
                            classification=scores['classification'],
                            ai_explanation=f"Semantic Score: {scores['semantic_score']}%. Skills Found: {len(scores['matched_skills'])}/{len(scores['matched_skills']) + len(scores['missing_skills'])}."
                        )
                    except Exception as e:
                        print(f"Error processing content for {f.name}: {e}")
                        
                except Exception as e:
                    print(f"Error handling file {f.name}: {e}")
                    
            return redirect('resume_list') # Redirect to dashboard to see results
                
    else:
        form = BulkUploadForm()
        print("Bulk Upload GET")
    
    if request.method == 'POST' and not form.is_valid():
        print(f"Form Errors: {form.errors}")

    return render(request, 'resumes/bulk_upload.html', {'form': form})

def clear_all_resumes(request):
    print(f"DEBUG: clear_all_resumes called. Method: {request.method}")
    if request.method == 'POST':
        # Delete all resumes (cascades to scores)
        count, _ = Resume.objects.all().delete()
        print(f"DEBUG: Deleted {count} resumes.")
        # Also clean up the media folder if needed, but Django delete might handle file cleanup 
        # depending on setup. For now, database clear is the priority.
    return redirect('resume_list')



