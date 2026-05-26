from django.shortcuts import render, redirect, get_object_or_404
from .models import Resume, ResumeScore
from .forms import (
    ResumeUploadForm,
    BulkUploadForm,
    SecureProfileUploadForm,
    CandidateStatusUpdateForm,
    JDResumeAnalysisForm,
    AIFilterBatchForm,
    MatchStoredForm,
)
from jobs.models import JobRequirement
from ai_engine.parser import extract_resume_text, extract_jd_text_from_upload, extract_jd_text_raw
from ai_engine.screener import calculate_resume_score, extract_keywords
from django.contrib.auth.decorators import login_required
from .models import ResumeScore, CandidateProfile, ProfileVersion, SubmissionActivity, ScanRun, ScanResult
import os
import re
import zipfile
import tempfile
from django.core.files.base import ContentFile

@login_required
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
                        semantic_score=scores['semantic_score'],
                        missing_skills=scores['missing_skills'],
                        matched_skills=scores['matched_skills'],
                        classification=scores['classification'],
                        ai_explanation=scores.get('ai_explanation', '')
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

@login_required
def bulk_upload(request):
    if request.method == 'POST':
        upload_mode = request.POST.get('upload_mode', 'folder')

        # ── URL import mode ──────────────────────────────────────────
        if upload_mode == 'url':
            import urllib.request
            import urllib.parse
            raw_urls = request.POST.get('resume_urls', '')
            urls = [u.strip() for u in raw_urls.splitlines() if u.strip()]
            uploaded_count = 0
            url_errors = []
            allowed_exts = ('.pdf', '.docx', '.jpg', '.jpeg', '.png')

            for url in urls:
                try:
                    parsed_path = urllib.parse.urlparse(url).path
                    ext = os.path.splitext(parsed_path)[1].lower()
                    if ext not in allowed_exts:
                        url_errors.append(f"{url} — unsupported file type '{ext}' (use PDF, DOCX, JPG, PNG).")
                        continue

                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp_path = tmp.name
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        data = resp.read()
                    with open(tmp_path, 'wb') as fh:
                        fh.write(data)

                    url_fname = os.path.basename(parsed_path) or f"url_resume{ext}"
                    candidate_name = os.path.splitext(url_fname)[0].replace('_', ' ').replace('-', ' ').title()

                    resume = Resume()
                    with open(tmp_path, 'rb') as fh:
                        resume.file.save(url_fname, ContentFile(fh.read()), save=False)
                    resume.candidate_name = candidate_name
                    resume.save()

                    try:
                        resume.parsed_content = extract_resume_text(resume.file.path)
                        resume.save()
                    except Exception as e:
                        print(f"Parse error for URL {url}: {e}")

                    uploaded_count += 1
                except Exception as e:
                    url_errors.append(f"{url} — {e}")
                    print(f"URL import error for {url}: {e}")
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            return render(request, 'resumes/bulk_upload.html', {
                'form': BulkUploadForm(),
                'uploaded_count': uploaded_count,
                'url_errors': url_errors,
                'active_tab': 'url',
            })

        # ── Folder / file upload mode ─────────────────────────────────
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            job = form.cleaned_data.get('job')
            files = request.FILES.getlist('resumes')
            uploaded_count = 0

            for f in files:
                try:
                    if not f.name.lower().endswith(('.pdf', '.docx', '.jpg', '.jpeg', '.png')):
                        continue
                    resume = Resume()
                    resume.file = f
                    fname = os.path.basename(f.name)
                    resume.candidate_name = os.path.splitext(fname)[0].replace('_', ' ').title()
                    resume.save()
                    try:
                        resume.parsed_content = extract_resume_text(resume.file.path)
                        resume.save()
                    except Exception as e:
                        print(f"Error processing content for {f.name}: {e}")

                    if job and resume.parsed_content:
                        try:
                            scores = calculate_resume_score(resume.parsed_content, job.description, job.required_skills)
                            ResumeScore.objects.create(
                                resume=resume, job=job,
                                match_percentage=scores['final_score'],
                                skill_match_score=scores['skill_score'],
                                semantic_score=scores['semantic_score'],
                                missing_skills=scores['missing_skills'],
                                matched_skills=scores['matched_skills'],
                                classification=scores['classification'],
                                ai_explanation=scores.get('ai_explanation', '')
                            )
                        except Exception as e:
                            print(f"Scoring error for {f.name}: {e}")
                    uploaded_count += 1
                except Exception as e:
                    print(f"Error handling file {f.name}: {e}")

            success_form = BulkUploadForm()
            return render(request, 'resumes/bulk_upload.html', {
                'form': success_form,
                'uploaded_count': uploaded_count,
                'selected_job': job,
            })
                
    else:
        form = BulkUploadForm()

    return render(request, 'resumes/bulk_upload.html', {'form': form})

def clear_all_resumes(request):
    if request.method == 'POST':
        # Delete all resumes (cascades to scores)
        count, _ = Resume.objects.all().delete()
        # Also clean up the media folder if needed, but Django delete might handle file cleanup 
        # depending on setup. For now, database clear is the priority.
    return redirect('resume_list')




@login_required
def secure_dashboard(request):
    profiless = CandidateProfile.objects.all().order_by('-updated_at')

    analysis_result = None
    if request.method == 'POST':
        analysis_form = JDResumeAnalysisForm(request.POST, request.FILES)
        if analysis_form.is_valid():
            # Resolve JD text: file upload takes priority over pasted text
            jd_file = request.FILES.get('jd_file')
            jd_text = (analysis_form.cleaned_data.get('job_description') or '').strip()
            if jd_file:
                extracted = extract_jd_text_from_upload(jd_file)
                if extracted:
                    jd_text = extracted
            uploaded_file = analysis_form.cleaned_data['candidate_file']

            # 1. Store resume in DB (persisted)
            resume = Resume()
            resume.file = uploaded_file
            fname = os.path.basename(uploaded_file.name)
            resume.candidate_name = os.path.splitext(fname)[0].replace('_', ' ').title()
            resume.save()

            try:
                resume.parsed_content = extract_resume_text(resume.file.path) or ""
                resume.save(update_fields=['parsed_content'])
            except Exception:
                pass

            resume_text = resume.parsed_content or ""

            # 2. Run full QA: JD match + certs + compliance + risk
            required_skills = extract_keywords(jd_text) or []
            base_scores = calculate_resume_score(resume_text, jd_text, required_skills)
            experience_score, experience_notes, resume_exp_years, jd_exp_years = compute_experience_match(jd_text, resume_text)
            cert_status, cert_details = analyze_certifications(jd_text, resume_text)
            compliance_issues = detect_compliance_issues(jd_text, resume_text)
            risk_flags = detect_risk_flags(jd_text, resume_text)
            nursing_compliance = verify_nursing_credentials(jd_text, resume_text)
            final_score, recommendation = compute_final_score_and_recommendation(
                base_scores['semantic_score'],
                base_scores['skill_score'],
                experience_score,
                len(compliance_issues),
                len(risk_flags),
                nursing_compliance,
            )
            improvement_suggestions = generate_improvement_suggestions(
                recommendation, base_scores.get('matched_skills', []), base_scores.get('missing_skills', []),
                resume_exp_years, jd_exp_years, cert_status, cert_details,
                compliance_issues, risk_flags, nursing_compliance,
            )
            qa_grade, qa_verdict = compute_qa_grade_and_verdict(
                final_score,
                cert_status,
                len(compliance_issues),
                len(risk_flags),
                recommendation,
                nursing_compliance,
            )

            analysis_result = {
                "stored_resume_id": resume.pk,
                "stored_resume_name": resume.candidate_name or fname,
                "stored_file_name": fname,
                "skill_match_percentage": base_scores['skill_score'],
                "matched_skills": base_scores.get('matched_skills', []),
                "missing_skills": base_scores.get('missing_skills', []),
                "experience_match_score": experience_score,
                "experience_notes": experience_notes,
                "resume_experience_years": resume_exp_years,
                "jd_experience_years": jd_exp_years,
                "certification_status": cert_status,
                "certification_details": cert_details,
                "compliance_issues": compliance_issues,
                "risk_flags": risk_flags,
                "final_weighted_score": final_score,
                "recommendation": recommendation,
                "improvement_suggestions": improvement_suggestions,
                "qa_grade": qa_grade,
                "qa_verdict": qa_verdict,
            }
    else:
        analysis_form = JDResumeAnalysisForm()

    return render(
        request,
        'resumes/secure_dashboard.html',
        {
            'profiles': profiless,
            'analysis_form': analysis_form,
            'analysis_result': analysis_result,
        },
    )

@login_required
def upload_profile(request):
    if request.method == 'POST':
        form = SecureProfileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            profile_file = request.FILES['file']
            
            # Create Candidate Profile
            profile = form.save(commit=False)
            profile.created_by = request.user
            profile.current_status = 'SUBMITTED'
            profile.save()
            
            # Create Initial Version (Encrypted automatically by model)
            version = ProfileVersion.objects.create(
                profile=profile,
                version_number=1,
                file=profile_file,
                created_by=request.user,
                changelog="Initial submission"
            )
            
            # Log Activity
            SubmissionActivity.objects.create(
                profile=profile,
                actor=request.user,
                action="Submitted Profile",
                details=f"Uploaded version 1: {profile_file.name}"
            )
            
            return redirect('secure_dashboard')
    else:
        form = SecureProfileUploadForm()
    
    return render(request, 'resumes/upload_profile.html', {'form': form})

@login_required
def profile_detail(request, pk):
    profile = get_object_or_404(CandidateProfile, pk=pk)
    versions = profile.versions.all()
    activities = profile.activity_logs.all()
    
    if request.method == 'POST':
        status_form = CandidateStatusUpdateForm(request.POST, instance=profile)
        if status_form.is_valid():
            old_status = profile.current_status
            new_profile = status_form.save()
            
            if old_status != new_profile.current_status:
                SubmissionActivity.objects.create(
                    profile=profile,
                    actor=request.user,
                    action="Updated Status",
                    details=f"Changed status from {old_status} to {new_profile.current_status}"
                )
            return redirect('profile_detail', pk=pk)
    else:
        status_form = CandidateStatusUpdateForm(instance=profile)

    return render(request, 'resumes/profile_detail.html', {
        'profile': profile,
        'versions': versions,
        'activities': activities,
        'status_form': status_form
    })


@login_required
def ai_filter_page(request):
    """AI-based filter & quality check: paste JD, upload multiple resumes, scan and get best candidates + reports."""
    if request.method == 'POST':
        form = AIFilterBatchForm(request.POST, request.FILES)
        if form.is_valid():
            # Resolve JD text: file upload takes priority over pasted text
            jd_file = request.FILES.get('jd_file')
            jd_text = (form.cleaned_data.get('job_description') or '').strip()
            if jd_file:
                extracted = extract_jd_text_from_upload(jd_file)
                if extracted:
                    jd_text = extracted
            if not jd_text:
                form.add_error(None, 'Could not extract text from the uploaded JD file. Please paste the JD manually.')
                return render(request, 'resumes/ai_filter.html', {'form': form})
            files = request.FILES.getlist('resume_files')
            if not files:
                form.add_error(None, 'Upload at least one resume (PDF, DOCX, PNG or JPG).')
            else:
                jd_title = request.POST.get('jd_title', '').strip()
                scan_run = ScanRun.objects.create(created_by=request.user, jd_text=jd_text, jd_title=jd_title)
                allowed = ('.pdf', '.docx', '.png', '.jpg', '.jpeg')
                for f in files:
                    if not f.name.lower().endswith(allowed):
                        continue
                    resume = Resume()
                    resume.file = f
                    fname = os.path.basename(f.name)
                    resume.candidate_name = os.path.splitext(fname)[0].replace('_', ' ').title()
                    resume.save()
                    try:
                        resume.parsed_content = extract_resume_text(resume.file.path) or ""
                        resume.save(update_fields=['parsed_content'])
                    except Exception:
                        pass
                    resume_text = resume.parsed_content or ""
                    required_skills = extract_keywords(jd_text) or []
                    base_scores = calculate_resume_score(resume_text, jd_text, required_skills)
                    experience_score, experience_notes, resume_exp_years, jd_exp_years = compute_experience_match(jd_text, resume_text)
                    cert_status, cert_details = analyze_certifications(jd_text, resume_text)
                    compliance_issues = detect_compliance_issues(jd_text, resume_text)
                    risk_flags = detect_risk_flags(jd_text, resume_text)
                    nursing_compliance = verify_nursing_credentials(jd_text, resume_text)
                    final_score, recommendation = compute_final_score_and_recommendation(
                        base_scores['semantic_score'], base_scores['skill_score'], experience_score,
                        len(compliance_issues), len(risk_flags), nursing_compliance,
                    )
                    improvement_suggestions = generate_improvement_suggestions(
                        recommendation, base_scores.get('matched_skills', []), base_scores.get('missing_skills', []),
                        resume_exp_years, jd_exp_years, cert_status, cert_details,
                        compliance_issues, risk_flags, nursing_compliance,
                    )
                    qa_grade, qa_verdict = compute_qa_grade_and_verdict(
                        final_score, cert_status,
                        len(compliance_issues), len(risk_flags), recommendation, nursing_compliance,
                    )
                    ScanResult.objects.create(
                        scan_run=scan_run,
                        resume=resume,
                        candidate_name=resume.candidate_name or fname,
                        skill_match_percentage=base_scores['skill_score'],
                        matched_skills=base_scores.get('matched_skills', []),
                        missing_skills=base_scores.get('missing_skills', []),
                        experience_match_score=experience_score,
                        experience_notes=experience_notes,
                        resume_experience_years=resume_exp_years,
                        jd_experience_years=jd_exp_years,
                        certification_status=cert_status,
                        certification_details=cert_details,
                        compliance_issues=compliance_issues,
                        risk_flags=risk_flags,
                        final_weighted_score=final_score,
                        recommendation=recommendation,
                        improvement_suggestions=improvement_suggestions,
                        nursing_compliance=nursing_compliance,
                        qa_grade=qa_grade,
                        qa_verdict=qa_verdict,
                    )
                return redirect('filter_results', scan_run_id=scan_run.pk)
    else:
        form = AIFilterBatchForm()
    return render(request, 'resumes/ai_filter.html', {'form': form})


@login_required
def filter_results(request, scan_run_id):
    """List of candidates from a scan run, sorted by score (best first)."""
    scan_run = get_object_or_404(ScanRun, pk=scan_run_id, created_by=request.user)
    results = scan_run.results.select_related('resume').all()
    return render(request, 'resumes/filter_results.html', {'scan_run': scan_run, 'results': results})


@login_required
def clear_scan_run(request, scan_run_id):
    """Clear all results for a given scan run (does not delete resumes)."""
    scan_run = get_object_or_404(ScanRun, pk=scan_run_id, created_by=request.user)
    if request.method == 'POST':
        scan_run.results.all().delete()
    return redirect('filter_results', scan_run_id=scan_run.pk)


@login_required
def scan_report(request, result_id):
    """Full QA report for one candidate (print-friendly)."""
    result = get_object_or_404(ScanResult, pk=result_id, scan_run__created_by=request.user)
    return render(request, 'resumes/scan_report.html', {'result': result})


def _run_qa_and_create_scan_result(scan_run, resume, jd_text):
    """Run full QA for one resume vs JD and create ScanResult. Uses resume.parsed_content; re-parses if empty."""
    resume_text = resume.parsed_content or ""
    if not resume_text.strip() and resume.file:
        try:
            resume.parsed_content = extract_resume_text(resume.file.path) or ""
            resume.save(update_fields=['parsed_content'])
            resume_text = resume.parsed_content or ""
        except Exception:
            pass
    fname = resume.file.name and os.path.basename(resume.file.name) or f"Resume {resume.pk}"
    required_skills = extract_keywords(jd_text) or []
    base_scores = calculate_resume_score(resume_text, jd_text, required_skills)
    experience_score, experience_notes, resume_exp_years, jd_exp_years = compute_experience_match(jd_text, resume_text)
    cert_status, cert_details = analyze_certifications(jd_text, resume_text)
    compliance_issues = detect_compliance_issues(jd_text, resume_text)
    risk_flags = detect_risk_flags(jd_text, resume_text)
    nursing_compliance = verify_nursing_credentials(jd_text, resume_text)
    final_score, recommendation = compute_final_score_and_recommendation(
        base_scores['semantic_score'], base_scores['skill_score'], experience_score,
        len(compliance_issues), len(risk_flags), nursing_compliance,
    )
    improvement_suggestions = generate_improvement_suggestions(
        recommendation, base_scores.get('matched_skills', []), base_scores.get('missing_skills', []),
        resume_exp_years, jd_exp_years, cert_status, cert_details,
        compliance_issues, risk_flags, nursing_compliance,
    )
    qa_grade, qa_verdict = compute_qa_grade_and_verdict(
        final_score, cert_status,
        len(compliance_issues), len(risk_flags), recommendation, nursing_compliance,
    )
    ScanResult.objects.create(
        scan_run=scan_run,
        resume=resume,
        candidate_name=resume.candidate_name or os.path.splitext(fname)[0].replace('_', ' ').title(),
        skill_match_percentage=base_scores['skill_score'],
        matched_skills=base_scores.get('matched_skills', []),
        missing_skills=base_scores.get('missing_skills', []),
        experience_match_score=experience_score,
        experience_notes=experience_notes,
        resume_experience_years=resume_exp_years,
        jd_experience_years=jd_exp_years,
        certification_status=cert_status,
        certification_details=cert_details,
        compliance_issues=compliance_issues,
        risk_flags=risk_flags,
        final_weighted_score=final_score,
        recommendation=recommendation,
        improvement_suggestions=improvement_suggestions,
        nursing_compliance=nursing_compliance,
        qa_grade=qa_grade,
        qa_verdict=qa_verdict,
    )


@login_required
def match_stored_resumes(request):
    """Match stored (bulk-uploaded) resumes with a JD: run quality check, specs, certificates, and show best candidates."""
    if request.method == 'POST':
        form = MatchStoredForm(request.POST, request.FILES)
        # Bulk delete: action=delete with selected resume IDs
        if request.POST.get('action') == 'delete':
            pks = request.POST.getlist('resumes')
            if pks:
                Resume.objects.filter(pk__in=pks).delete()
                return redirect('match_stored')
            form = MatchStoredForm()
            form.add_error('resumes', 'Select at least one resume to delete.')
        elif form.is_valid():
            # Resolve JD text: pasted text (textarea) > saved JD > uploaded file
            saved_jd = form.cleaned_data.get('saved_jd')
            jd_text = None
            jd_title = request.POST.get('jd_title', '').strip()
            pasted_text = (form.cleaned_data.get('job_description') or '').strip()

            jd_file = request.FILES.get('jd_file')

            if pasted_text:
                jd_text = pasted_text

            if not jd_text and saved_jd:
                jd_text = saved_jd.description
                if not jd_title:
                    jd_title = saved_jd.title

            if not jd_text and jd_file:
                extracted = extract_jd_text_from_upload(jd_file)
                if extracted:
                    jd_text = extracted

            if not jd_text:
                jd_text = (form.cleaned_data.get('job_description') or '').strip()

            selected_resumes = form.cleaned_data['resumes']
            if not selected_resumes:
                form.add_error('resumes', 'Select at least one stored resume.')
            elif not jd_text:
                form.add_error(None, 'Could not extract text from the uploaded JD file. Please paste the JD manually.')
            else:
                # Save new JD as template for reuse
                if not saved_jd:
                    try:
                        first_line = jd_text.strip().split('\n')[0][:80]
                        save_title = jd_title or first_line or 'Saved JD'
                        JobRequirement.objects.get_or_create(
                            title=save_title,
                            defaults={
                                'description': jd_text,
                                'required_skills': extract_keywords(jd_text) or [],
                                'is_template': True,
                            }
                        )
                    except Exception as e:
                        print(f"Error saving JD template: {e}")

                scan_run = ScanRun.objects.create(created_by=request.user, jd_text=jd_text, jd_title=jd_title or 'Match Stored')
                for resume in selected_resumes:
                    _run_qa_and_create_scan_result(scan_run, resume, jd_text)
                return redirect('filter_results', scan_run_id=scan_run.pk)
    else:
        form = MatchStoredForm()
    stored_resumes = Resume.objects.all().order_by('-uploaded_at')
    all_jobs = JobRequirement.objects.all().order_by('-created_at')
    saved_jds = JobRequirement.objects.filter(is_template=True).order_by('-created_at')
    return render(request, 'resumes/match_stored.html', {
        'form': form,
        'stored_resumes': stored_resumes,
        'all_jobs': all_jobs,
        'saved_jds': saved_jds,
    })


@login_required
def delete_resume(request, pk):
    """Delete a stored resume and redirect back to match stored."""
    if request.method != 'POST':
        return redirect('match_stored')
    resume = get_object_or_404(Resume, pk=pk)
    resume.delete()
    return redirect('match_stored')


@login_required
def scan_history(request):
    """List all past ScanRuns for the current user, grouped by JD title."""
    from collections import defaultdict
    runs = (
        ScanRun.objects.filter(created_by=request.user)
        .prefetch_related('results')
        .order_by('-created_at')
    )

    # Build per-run summary and group by jd_title
    grouped = defaultdict(list)  # jd_title -> list of run summaries
    for run in runs:
        results = run.results.all()
        total = results.count()
        hired = results.filter(recommendation='Hire').count()
        held = results.filter(recommendation='Hold').count()
        rejected = total - hired - held
        avg_score = (
            round(sum(r.final_weighted_score for r in results) / total, 1)
            if total else 0
        )
        top = results.order_by('-final_weighted_score').first()
        key = run.jd_title or f'Untitled Scan #{run.pk}'
        grouped[key].append({
            'run': run,
            'total': total,
            'hired': hired,
            'held': held,
            'rejected': rejected,
            'avg_score': avg_score,
            'top_candidate': top,
        })

    # Convert to list of (jd_title, runs_list) sorted by most-recent scan first
    grouped_list = [
        (title, items)
        for title, items in grouped.items()
    ]

    return render(request, 'resumes/scan_history.html', {
        'grouped_list': grouped_list,
        'total_runs': runs.count(),
    })


@login_required
def delete_scan_run(request, scan_run_id):
    """Permanently delete a scan run and all its results."""
    scan_run = get_object_or_404(ScanRun, pk=scan_run_id, created_by=request.user)
    if request.method == 'POST':
        scan_run.delete()
    return redirect('scan_history')


@login_required
def bulk_delete_scan_runs(request):
    """Delete multiple scan runs at once (POST with list of IDs)."""
    if request.method == 'POST':
        pks = request.POST.getlist('scan_run_ids')
        if pks:
            ScanRun.objects.filter(pk__in=pks, created_by=request.user).delete()
    return redirect('scan_history')


@login_required
def extract_jd_title_ajax(request):
    """
    AJAX endpoint: receives a JD file upload, extracts text, returns the job title as JSON.
    POST param: jd_file (the uploaded file)
    Returns: { "title": "...", "source": "label|heading" } or { "title": "", "error": "..." }
    """
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'title': '', 'error': 'POST required'}, status=405)

    uploaded = request.FILES.get('jd_file')
    if not uploaded:
        return JsonResponse({'title': '', 'error': 'No file provided'}, status=400)

    try:
        text = extract_jd_text_raw(uploaded)
    except Exception as e:
        return JsonResponse({'title': '', 'error': str(e)}, status=500)

    if not text:
        return JsonResponse({'title': '', 'error': 'Could not extract text from file'})

    title = ''
    source = ''

    # pdfminer reads two-column PDFs left-column-first:
    # ALL left labels come first ("Job Title:", "Job Description:", etc.)
    # then ALL right column values ("Human Resources Assistant", "This position...", etc.)
    # So "Human Resources Assistant" may be 10-20 lines away from "Job Title:"
    raw_lines = [l.strip() for l in text.replace('\r', '').split('\n')]
    # If everything collapsed to one line, try splitting on large whitespace gaps
    if len([l for l in raw_lines if l]) <= 3 and len(text) > 100:
        raw_lines = [l.strip() for l in re.split(r'(?<=[.!?])\s{2,}|\s{4,}', text)]

    non_empty = [l for l in raw_lines if l]

    # Label patterns
    label_with_value = re.compile(
        r'^(?:job\s*title|position\s*title|role\s*title)\s*[:\-–]\s*(.+)',
        re.IGNORECASE
    )
    label_only = re.compile(
        r'^(?:job\s*title|position\s*title|role\s*title)\s*[:\-–]\s*$',
        re.IGNORECASE
    )

    def is_section_label(line):
        """Returns True if this line is a section header / label, not a job title value."""
        # Ends with colon → it's a label like "Job Description:" or "Qualifications:"
        if line.endswith(':'):
            return True
        bad = re.compile(
            r'^(sample|job\s*description|job\s*title|company|location|salary|'
            r'date|about|overview|responsibilities|requirements|qualifications|'
            r'benefits|who\s*we\s*are|the\s+intern|this\s+position|'
            r'hr\s+information|employee|specific|what\s+skills)',
            re.IGNORECASE
        )
        return bool(bad.match(line))

    for idx, line in enumerate(non_empty[:60]):
        # Case A: "Job Title: Human Resources Assistant" — value on same line
        m = label_with_value.match(line)
        if m:
            candidate = m.group(1).strip()
            if 3 < len(candidate) < 120 and not is_section_label(candidate):
                title = candidate
                source = 'label_inline'
                break

        # Case B: "Job Title:" standalone — scan UP TO 30 lines ahead
        # skipping other section labels (they end with ':')
        if label_only.match(line):
            for next_line in non_empty[idx + 1: idx + 30]:
                if not next_line:
                    continue
                if is_section_label(next_line):
                    continue          # skip other left-column labels
                if 3 < len(next_line) < 120:
                    title = next_line
                    source = 'label_next_line'
                    break
            if title:
                break

    # Fallback: first substantial heading that isn't a section label
    if not title:
        for line in non_empty[:25]:
            clean = re.sub(r'^#+\s*', '', line)
            if not clean or is_section_label(clean):
                continue
            if 3 < len(clean) < 120:
                title = clean
                source = 'heading'
                break

    return JsonResponse({'title': title, 'source': source})


@login_required
def fetch_jd_by_id_ajax(request):
    """
    AJAX endpoint: fetches a JobRequirement by ID and returns its JD text + metadata.

    GET /resumes/ajax/fetch-jd-by-id/?job_id=<id>
      → { "ok": true, "id": 3, "title": "...", "description": "...",
          "required_skills": [...], "experience_years": 3, "location": "...", "domain": "..." }

    GET /resumes/ajax/fetch-jd-by-id/  (no job_id param)
      → { "ok": true, "jobs": [ { "id":..., "title":... }, ... ] }
    """
    from django.http import JsonResponse

    job_id = request.GET.get('job_id', '').strip()

    # No ID → return list of all jobs for the dropdown
    if not job_id:
        jobs = JobRequirement.objects.all().order_by('-created_at').values(
            'id', 'title', 'location', 'industry_domain', 'experience_years', 'is_template'
        )
        return JsonResponse({'ok': True, 'jobs': list(jobs)})

    # Validate ID is integer
    try:
        job_id_int = int(job_id)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid Job ID — must be a number.'}, status=400)

    try:
        job = JobRequirement.objects.get(pk=job_id_int)
    except JobRequirement.DoesNotExist:
        return JsonResponse({'ok': False, 'error': f'No job found with ID {job_id_int}.'}, status=404)

    return JsonResponse({
        'ok': True,
        'id': job.pk,
        'title': job.title,
        'description': job.description,
        'required_skills': job.required_skills or [],
        'preferred_skills': job.preferred_skills or [],
        'experience_years': job.experience_years,
        'location': job.location or '',
        'domain': job.industry_domain or '',
        'is_template': job.is_template,
        'mandatory_certifications': job.mandatory_certifications or [],
        'compliance_requirements': job.compliance_requirements or [],
    })


@login_required
def fetch_jd_from_url_ajax(request):
    """
    AJAX endpoint: fetches a job description from an external URL.
    POST param: jd_url (the URL to fetch)
    Returns: { "ok": true, "title": "...", "description": "..." } or { "ok": false, "error": "..." }
    """
    from django.http import JsonResponse
    import requests as http_requests
    from bs4 import BeautifulSoup

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    url = request.POST.get('jd_url', '').strip()
    if not url:
        return JsonResponse({'ok': False, 'error': 'No URL provided.'}, status=400)

    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    html_content = ""
    fetch_success = False
    error_message = ""

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        resp = http_requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        html_content = resp.text
        fetch_success = True
    except http_requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            try:
                import cloudscraper
                scraper = cloudscraper.create_scraper()
                scraper_resp = scraper.get(url, timeout=15)
                if scraper_resp.status_code == 200:
                    html_content = scraper_resp.text
                    fetch_success = True
                else:
                    error_message = (
                        "Security Block (403 Forbidden): Indeed, LinkedIn, and Glassdoor aggressively block automated scraping. "
                        "To proceed, please copy and paste the job description directly into the 'Paste Text' tab, or upload a JD document."
                    )
            except Exception:
                error_message = (
                    "Security Block (403 Forbidden): Indeed, LinkedIn, and Glassdoor aggressively block automated scraping. "
                    "To proceed, please copy and paste the job description directly into the 'Paste Text' tab, or upload a JD document."
                )
        else:
            error_message = f"HTTP error: {e.response.status_code}"
    except http_requests.exceptions.Timeout:
        error_message = "Request timed out. The site may be slow or blocking requests."
    except http_requests.exceptions.ConnectionError:
        error_message = "Could not connect to the URL. Please check the link."
    except Exception as e:
        error_message = f"Failed to fetch URL: {str(e)}"

    if not fetch_success:
        return JsonResponse({'ok': False, 'error': error_message})

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove unwanted elements
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header',
                                   'iframe', 'noscript', 'svg', 'form', 'button']):
            tag.decompose()

        # Try to extract the page title
        title = ''
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Clean common suffixes like " | LinkedIn", " - Indeed.com"
            for sep in [' | ', ' - ', ' – ', ' — ', ' :: ']:
                if sep in title:
                    title = title.split(sep)[0].strip()

        # Try to find structured job description content
        # Priority order: specific job description containers, then main/article, then body
        jd_text = ''

        # Look for common JD container selectors
        selectors = [
            # LinkedIn
            {'class_': re.compile(r'description|job-description|jobDescription', re.I)},
            {'class_': re.compile(r'job.?details|job.?content|job.?body', re.I)},
            # Indeed / Glassdoor
            {'id': re.compile(r'jobDescription|job-description|job.?details', re.I)},
            # Generic
            {'class_': re.compile(r'posting.?body|listing.?content|vacancy.?description', re.I)},
            {'role': 'main'},
        ]

        for sel in selectors:
            container = soup.find(**sel)
            if container:
                text = container.get_text(separator='\n', strip=True)
                if len(text) > 100:
                    jd_text = text
                    break

        # Fallback: try <article> or <main> tags
        if not jd_text:
            for tag_name in ['article', 'main']:
                tag = soup.find(tag_name)
                if tag:
                    text = tag.get_text(separator='\n', strip=True)
                    if len(text) > 100:
                        jd_text = text
                        break

        # Last fallback: get all text from body
        if not jd_text:
            body = soup.find('body')
            if body:
                jd_text = body.get_text(separator='\n', strip=True)

        if not jd_text or len(jd_text.strip()) < 50:
            return JsonResponse({
                'ok': False,
                'error': 'Could not extract meaningful job description text from this URL. '
                         'The site may require login or block automated access.'
            })

        # Clean up: collapse excessive blank lines
        lines = jd_text.split('\n')
        cleaned_lines = []
        prev_blank = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not prev_blank:
                    cleaned_lines.append('')
                prev_blank = True
            else:
                cleaned_lines.append(stripped)
                prev_blank = False
        jd_text = '\n'.join(cleaned_lines).strip()

        # Truncate if extremely long (some pages have tons of boilerplate)
        if len(jd_text) > 15000:
            jd_text = jd_text[:15000] + '\n\n[... truncated — please edit as needed ...]'

        return JsonResponse({
            'ok': True,
            'title': title or '',
            'description': jd_text,
            'source_url': url,
        })

    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Error parsing page content: {str(e)}'})


def extract_years_of_experience(text):
    """
    Extracts years of experience from text using context-aware patterns.
    Prioritizes phrases like '5 years of experience' over bare 'N years'
    to avoid picking up non-experience numbers (company age, team size, etc.).
    """
    if not text:
        return None
    text_lower = text.lower()

    # Priority patterns — each anchors 'years' to experience-related context
    experience_patterns = [
        r'(\d+)\s*\+?\s*years?\s+(?:of\s+)?experience',       # "5 years of experience"
        r'(?:minimum|at\s+least|min)[\s.:]+(\d+)\s*\+?\s*years?',  # "minimum 5 years"
        r'experience[:\s]+(\d+)\s*\+?\s*years?',               # "experience: 5+ years"
        r'(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:related|professional|practical|progressive|relevant|industry)\s+experience',  # "5+ years of professional experience"
        r'(\d+)\s*\+?\s*-?\s*year\s',                          # "5-year" or "5+ year" (handles hyphen)
    ]

    for pattern in experience_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            values = [int(m) for m in matches if 1 <= int(m) <= 40]
            if values:
                return max(values)

    # Fallback: any bare "N years/yrs" pattern filtered to 1-20 range
    matches = re.findall(r'(\d+)\s*\+?\s*(?:years?|yrs?)', text_lower)
    if matches:
        try:
            values = [int(m) for m in matches if 1 <= int(m) <= 20]
            if values:
                return max(values)
        except ValueError:
            pass

    return None


def compute_experience_match(jd_text, resume_text):
    jd_years = extract_years_of_experience(jd_text)
    resume_years = extract_years_of_experience(resume_text)

    if jd_years is None or resume_years is None:
        return 50.0, "Insufficient explicit experience data in JD or resume.", resume_years, jd_years

    ratio = resume_years / jd_years if jd_years > 0 else 1
    score = max(0.0, min(100.0, ratio * 100))
    notes = f"JD requires approximately {jd_years}+ years; resume indicates about {resume_years} years."
    return round(score, 2), notes, resume_years, jd_years


KNOWN_CERT_KEYWORDS = [
    # IT / general
    "aws certified", "azure", "gcp", "pmp", "cissp",
    "cisa", "cism", "scrum master", "csm", "salesforce",
    # Healthcare / nursing
    "bls", "basic life support",
    "acls", "advanced cardiac life support",
    "nihss", "national institutes of health stroke scale",
    "pals", "pediatric advanced life support",
    "rn", "registered nurse",
    "lpn", "licensed practical nurse",
    "cna", "certified nursing assistant",
    "ccrn", "critical care registered nurse",
    "tncc", "trauma nursing core course",
    "enpc", "emergency nursing pediatric course",
    "cpan", "certified perianesthesia nurse",
    "capa", "certified ambulatory perianesthesia nurse",
    "cmsrn", "certified medical-surgical registered nurse",
]


def analyze_certifications(jd_text, resume_text):
    jd_lower = jd_text.lower()
    resume_lower = resume_text.lower()

    jd_certs = [c for c in KNOWN_CERT_KEYWORDS if c in jd_lower]
    resume_certs = [c for c in KNOWN_CERT_KEYWORDS if c in resume_lower]

    if not jd_certs:
        return "Not Specified", "Job description does not specify mandatory certifications."

    missing = [c for c in jd_certs if c not in resume_certs]
    if not missing:
        return "All Mandatory Certifications Present", "All key certifications mentioned in JD are present in the resume."

    details = f"Missing certifications: {', '.join(missing)}."
    return "Missing Mandatory Certifications", details


COMPLIANCE_KEYWORDS = [
    # General
    "background check", "drug test",
    "security clearance", "work authorization", "work permit",
    # Nursing / healthcare
    "license verification", "nursys", "credentialing",
    "compact license", "compact state",
    "rn license", "nursing license",
    "malpractice insurance", "professional liability",
    "physical exam", "titers", "immunization",
    "fit test", "respirator fit",
    "hipaa", "osha", "infection control",
    "state license", "license expiration",
    "sanctions check", "excluded parties",
    "oig", "gao", "federal exclusion",
    "references verified", "employment verification",
    "skills checklist", "competency validation",
    "orientation", "ehr training",
    "pay package", "weekly stipend", "overtime rate",
    "rto", "requested time off", "start date",
    "work history", "employment gap",
]


def detect_compliance_issues(jd_text, resume_text):
    jd_lower = jd_text.lower()
    resume_lower = resume_text.lower()
    issues = []

    for kw in COMPLIANCE_KEYWORDS:
        if kw in jd_lower and kw not in resume_lower:
            issues.append(f"JD mentions '{kw}' but the resume does not explicitly address it.")

    return issues


RISK_KEYWORDS = [
    # General
    "terminated", "fired", "layoff", "disciplinary",
    "probation", "criminal", "conviction", "warning letter",
    # Nursing / healthcare
    "license suspended", "license revocation", "board action",
    "malpractice", "negligence", "patient harm",
    "excluded", "sanctioned", "debarred",
    "substance abuse", "diversion", "impairment",
    "abandonment", "patient abandonment",
    "fraud", "medicare fraud", "false claims",
    "disciplinary action", "board of nursing",
    "consent agreement", "consent order",
    "reprimand", "fine", "penalty",
    "license probation", "supervision requirement",
]


def detect_risk_flags(jd_text, resume_text):
    resume_lower = resume_text.lower()
    flags = []

    for kw in RISK_KEYWORDS:
        if kw in resume_lower:
            flags.append(f"Resume contains potential risk term: '{kw}'.")

    return flags


# ── Nursing compliance helpers ──────────────────────────────────────────────────

NURSING_LICENSE_PATTERNS = [
    r'(?:rn|registered\s*nurse)\s*(?:\#|lic|license|no)[:\s]*([a-z0-9\-]+)',
    r'(?:nursing\s*license|license\s*\#)[:\s]*([a-z0-9\-]+)',
    r'(?:compact|multi[\-\s]state)\s*(?:rn|license)',
    r'(?:state|board)\s*(?:of\s+)?nursing',
]

HEALTHCARE_CERT_PATTERNS = {
    'bls': r'bls|basic\s+life\s+support',
    'acls': r'acls|advanced\s+cardiac\s+life\s+support',
    'nihss': r'nihss|national\s+institutes\s+of\s+health\s+stroke\s+scale',
    'pals': r'pals|pediatric\s+advanced\s+life\s+support',
}

SANCTIONS_PATTERNS = [
    r'sanction', r'excluded\s*part(y|ies)', r'oig', r'gao',
    r'disciplinary\s*action', r'board\s*action',
    r'consent\s*order', r'consent\s*agreement',
    r'license\s*(suspended|revoked|probation)',
    r'malpractice', r'negligence', r'fraud',
]


def verify_nursing_credentials(jd_text, resume_text):
    """
    Analyze nursing-specific credentials from resume & JD text.
    Returns a dict structured for the nursing_compliance JSONField.
    Mimics what Nursys / CredentialMyDoc / Symplr would return via API.
    """
    jd_lower = jd_text.lower() if jd_text else ''
    resume_lower = resume_text.lower() if resume_text else ''

    nursing = {
        'license': {
            'status': 'unchecked',
            'state': '',
            'compact_eligible': False,
            'expiry': '',
            'number': '',
        },
        'sanctions': {
            'clear': True,
            'details': '',
            'alert': False,
        },
        'discipline_history': {
            'clear': True,
            'details': '',
            'alert': False,
        },
        'certifications': {},
        'skills_checklist': {
            'complete': False,
            'details': '',
        },
        'work_history': {
            'clean': True,
            'gaps': '',
        },
        'references': {
            'complete': False,
            'details': '',
        },
        'pay_package': {
            'aligned': True,
            'details': '',
        },
        'start_date': {
            'conflict': False,
            'details': '',
        },
        'rto': {
            'conflicts': '',
        },
        'nursys_verified': False,
        'credentialmydoc_verified': False,
        'symplr_verified': False,
    }

    # ── License detection ──
    for pat in NURSING_LICENSE_PATTERNS:
        m = re.search(pat, resume_lower)
        if m:
            nursing['license']['status'] = 'found'
            if m.lastindex and m.group(1):
                nursing['license']['number'] = m.group(1)
            break

    # Compact state check
    if re.search(r'compact|multi[\-\s]state', resume_lower):
        nursing['license']['compact_eligible'] = True

    # State detection (look for "RN in <state>" or similar)
    state_match = re.search(r'(?:rn|licensed)\s*(?:in|for|state\s*of?)[:\s]*([a-z]{2})', resume_lower)
    if state_match:
        nursing['license']['state'] = state_match.group(1).upper()

    # Expiry date detection
    expiry_match = re.search(r'(?:license|expir|expires?|valid\s*(?:through|until))[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', resume_lower)
    if expiry_match:
        nursing['license']['expiry'] = expiry_match.group(1)

    # ── Certification detection ──
    for cert_name, pattern in HEALTHCARE_CERT_PATTERNS.items():
        found = bool(re.search(pattern, resume_lower))
        jd_requires = bool(re.search(pattern, jd_lower))
        nursing['certifications'][cert_name] = {
            'present': found,
            'jd_requires': jd_requires,
            'status': 'valid' if found else ('missing' if jd_requires else 'not_required'),
        }

    # ── Sanctions / discipline ──
    for pat in SANCTIONS_PATTERNS:
        if re.search(pat, resume_lower):
            nursing['sanctions']['clear'] = False
            nursing['sanctions']['alert'] = True
            nursing['sanctions']['details'] = 'Potential sanction/discipline term detected in resume.'
            break

    # ── Skills checklist ──
    if re.search(r'skills?\s*checklist|competency\s*validation', resume_lower):
        nursing['skills_checklist']['complete'] = True
    if re.search(r'skills?\s*checklist|competency\s*validation', jd_lower):
        nursing['skills_checklist']['details'] = 'JD requires skills checklist completion.'

    # ── Work history gaps ──
    if re.search(r'employment\s*gap|work\s*history\s*gap', resume_lower):
        nursing['work_history']['gaps'] = 'Potential work history gap detected.'
        nursing['work_history']['clean'] = False

    # ── References ──
    if re.search(r'references?\s*(?:complete|available|attached|upon\s*request)', resume_lower):
        nursing['references']['complete'] = True
        nursing['references']['details'] = 'References mentioned in resume.'
    elif re.search(r'reference', jd_lower):
        nursing['references']['details'] = 'JD requests references; not mentioned in resume.'

    # ── Pay package alignment ──
    if re.search(r'pay\s*package|weekly\s*(?:rate|stipend|pay)|overtime', resume_lower):
        nursing['pay_package']['aligned'] = True
        nursing['pay_package']['details'] = 'Pay preferences discussed in resume.'

    # ── Start date / RTO ──
    if re.search(r'start\s*date|available\s*(?:immediately)?|availability', resume_lower):
        nursing['start_date']['details'] = 'Start date mentioned in resume.'
    if re.search(r'rto|requested\s*time\s*off|time\s*off\s*requested', resume_lower):
        nursing['rto']['conflicts'] = 'RTO mentioned in resume.'
        nursing['start_date']['conflict'] = True

    return nursing


def generate_nursing_compliance_summary(nursing):
    """Generate human-readable summary lines from nursing compliance data."""
    lines = []
    lic = nursing.get('license', {})
    if lic.get('status') == 'found':
        s = f"License: found"
        if lic.get('state'):
            s += f" ({lic['state']})"
        if lic.get('compact_eligible'):
            s += " — Compact eligible"
        if lic.get('expiry'):
            s += f" — Expires: {lic['expiry']}"
        lines.append(s)
    elif lic.get('status') == 'unchecked':
        lines.append("License: Not verified — Nursys check recommended.")

    for cert_name, cert_data in nursing.get('certifications', {}).items():
        if cert_data.get('jd_requires') and not cert_data.get('present'):
            lines.append(f"Cert missing ({cert_name.upper()}): Required by JD, not found in resume.")

    if not nursing.get('sanctions', {}).get('clear'):
        lines.append("⚠ Sanctions/Discipline alert triggered — manual review required.")

    if not nursing.get('references', {}).get('complete'):
        lines.append("References: Not confirmed as complete.")

    if nursing.get('rto', {}).get('conflicts'):
        lines.append(f"RTO: {nursing['rto']['conflicts']}")

    if not nursing.get('start_date', {}).get('conflict'):
        if not nursing.get('start_date', {}).get('details'):
            lines.append("Start date: Not mentioned in resume.")

    return "\n".join(lines) if lines else "Nursing compliance checks passed."


def generate_improvement_suggestions(
    recommendation,
    matched_skills,
    missing_skills,
    resume_years,
    jd_years,
    cert_status,
    cert_details,
    compliance_issues,
    risk_flags,
    nursing_compliance=None,
):
    """Generate specific improvement suggestions based on gaps found."""
    suggestions = []

    if missing_skills:
        suggestions.append(
            f"Resume is missing these key skills: {', '.join(missing_skills[:5])}"
            + (f" and {len(missing_skills)-5} more." if len(missing_skills) > 5 else ".")
        )

    if jd_years and resume_years and resume_years < jd_years:
        suggestions.append(
            f"JD requires {jd_years}+ years of experience; resume shows {resume_years} years. "
            "Highlight any relevant experience that demonstrates seniority."
        )

    if cert_details and 'missing' in cert_status.lower():
        suggestions.append(f"Missing certifications: {cert_details}. Consider obtaining relevant certifications.")

    for issue in compliance_issues:
        suggestions.append(f"Compliance gap: {issue}")

    # Nursing-specific suggestions
    if nursing_compliance:
        nc = nursing_compliance
        if nc.get('license', {}).get('status') == 'unchecked':
            suggestions.append("Nursing license not verified. Run Nursys/CredentialMyDoc check.")
        for cert_name, cert_data in nc.get('certifications', {}).items():
            if cert_data.get('jd_requires') and not cert_data.get('present'):
                suggestions.append(f"Nursing cert missing ({cert_name.upper()}): required by JD, not found in resume.")
        if not nc.get('sanctions', {}).get('clear'):
            suggestions.append("Sanctions/discipline alert: manual review of board of nursing records required.")
        if not nc.get('references', {}).get('complete'):
            suggestions.append("References not confirmed as complete.")
        if nc.get('rto', {}).get('conflicts'):
            suggestions.append(f"RTO conflict: {nc['rto']['conflicts']}")

    if recommendation == 'Reject':
        if not suggestions:
            suggestions.append("Overall score too low. Improve resume to better match JD keywords and requirements.")
        else:
            suggestions.insert(0, "Resume was rejected due to the following gaps:")
    elif recommendation == 'Hold':
        if not suggestions:
            suggestions.append("Score is borderline. Strengthen resume sections that align with JD priorities.")
        else:
            suggestions.insert(0, "Resume is on hold. Address these areas to improve:")

    if not suggestions:
        suggestions.append("Resume meets key requirements. No major gaps detected.")

    return "\n".join(suggestions)


def compute_final_score_and_recommendation(
    semantic_score,
    skill_score,
    experience_score,
    compliance_issue_count,
    risk_flag_count,
    nursing_compliance=None,
):
    base_score = (0.4 * semantic_score) + (0.35 * skill_score) + (0.25 * experience_score)
    penalty = (compliance_issue_count * 5) + (risk_flag_count * 7)

    # Nursing compliance penalty
    if nursing_compliance:
        nc = nursing_compliance
        if nc.get('license', {}).get('status') == 'unchecked':
            penalty += 5
        missing_nursing_certs = sum(
            1 for c in nc.get('certifications', {}).values()
            if c.get('jd_requires') and not c.get('present')
        )
        penalty += missing_nursing_certs * 4
        if not nc.get('sanctions', {}).get('clear'):
            penalty += 10

    final = max(0.0, min(100.0, base_score - penalty))

    nursing_ok = True
    if nursing_compliance:
        nc = nursing_compliance
        nursing_ok = (
            nc.get('license', {}).get('status') != 'unchecked'
            and nc.get('sanctions', {}).get('clear', True)
        )

    if final >= 80 and compliance_issue_count == 0 and risk_flag_count == 0 and nursing_ok:
        recommendation = "Hire"
    elif final >= 55:
        recommendation = "Hold"
    else:
        recommendation = "Reject"

    return round(final, 2), recommendation


def compute_qa_grade_and_verdict(
    final_score,
    cert_status,
    compliance_count,
    risk_count,
    recommendation,
    nursing_compliance=None,
):
    """
    Best QA style: letter grade (A/B/C/D) replaced with empty string and short verdict.
    """
    cert_ok = "missing" not in cert_status.lower() and "not specified" not in cert_status.lower()
    cert_ok = cert_ok or "all mandatory" in cert_status.lower()

    nursing_note = ""
    if nursing_compliance:
        nc = nursing_compliance
        lic_ok = nc.get('license', {}).get('status') != 'unchecked'
        sanctions_ok = nc.get('sanctions', {}).get('clear', True)
        if not lic_ok:
            nursing_note = " License not verified."
        elif not sanctions_ok:
            nursing_note = " Sanctions check triggered."

    if final_score >= 80 and compliance_count == 0 and risk_count == 0:
        grade = ""
        verdict = "Best QA – Strong match, document and checks passed. Ready for next stage."
    elif final_score >= 65 and compliance_count == 0 and risk_count == 0:
        grade = ""
        verdict = "Good QA – Meets requirements. Minor gaps (e.g. certs) can be clarified."
    elif final_score >= 50 or (compliance_count == 0 and risk_count == 0):
        grade = ""
        verdict = "Hold – Some criteria met. Review experience, certs or compliance before deciding."
    else:
        grade = ""
        verdict = "Does not meet QA – Significant gaps, compliance or risk issues. Not recommended."

    if nursing_note:
        verdict += nursing_note
    return grade, verdict
