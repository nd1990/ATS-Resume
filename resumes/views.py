from django.shortcuts import render, redirect, get_object_or_404
from .models import Resume, ResumeScore
from .forms import (
    ResumeUploadForm,
    BulkUploadForm,
    SecureProfileUploadForm,
    CandidateStatusUpdateForm,
    JDResumeAnalysisForm,
    AIFilterBatchForm,
)
from jobs.models import JobRequirement
from ai_engine.parser import extract_resume_text
from ai_engine.screener import calculate_resume_score, extract_keywords
from django.contrib.auth.decorators import login_required
from .models import ResumeScore, CandidateProfile, ProfileVersion, SubmissionActivity, ScanRun, ScanResult
import os
import re
import zipfile
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
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            job = form.cleaned_data['job']
            files = request.FILES.getlist('resumes')
            
            for f in files:
                try:
                    # Filter supported files
                    if not f.name.lower().endswith(('.pdf', '.docx', '.jpg', '.jpeg', '.png')):
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
                            semantic_score=scores['semantic_score'],
                            missing_skills=scores['missing_skills'],
                            matched_skills=scores['matched_skills'],
                            classification=scores['classification'],
                            ai_explanation=scores.get('ai_explanation', '')
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




@login_required
def secure_dashboard(request):
    profiless = CandidateProfile.objects.all().order_by('-updated_at')

    analysis_result = None
    if request.method == 'POST':
        analysis_form = JDResumeAnalysisForm(request.POST, request.FILES)
        if analysis_form.is_valid():
            jd_text = analysis_form.cleaned_data['job_description']
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

            # 2. Run full QA: JD match + document quality + certs + compliance + risk
            required_skills = extract_keywords(jd_text) or []
            base_scores = calculate_resume_score(resume_text, jd_text, required_skills)
            experience_score, experience_notes = compute_experience_match(jd_text, resume_text)
            cert_status, cert_details = analyze_certifications(jd_text, resume_text)
            compliance_issues = detect_compliance_issues(jd_text, resume_text)
            risk_flags = detect_risk_flags(jd_text, resume_text)
            doc_quality_score, doc_quality_label = compute_document_quality(resume_text)
            final_score, recommendation = compute_final_score_and_recommendation(
                base_scores['semantic_score'],
                base_scores['skill_score'],
                experience_score,
                len(compliance_issues),
                len(risk_flags),
            )
            qa_grade, qa_verdict = compute_qa_grade_and_verdict(
                final_score,
                doc_quality_score,
                cert_status,
                len(compliance_issues),
                len(risk_flags),
                recommendation,
            )

            analysis_result = {
                "stored_resume_id": resume.pk,
                "stored_resume_name": resume.candidate_name or fname,
                "stored_file_name": fname,
                "skill_match_percentage": base_scores['skill_score'],
                "experience_match_score": experience_score,
                "experience_notes": experience_notes,
                "certification_status": cert_status,
                "certification_details": cert_details,
                "compliance_issues": compliance_issues,
                "risk_flags": risk_flags,
                "document_quality_score": doc_quality_score,
                "document_quality_label": doc_quality_label,
                "final_weighted_score": final_score,
                "recommendation": recommendation,
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
            jd_text = form.cleaned_data['job_description'].strip()
            files = request.FILES.getlist('resume_files')
            if not files:
                form.add_error(None, 'Upload at least one resume (PDF, DOCX, PNG or JPG).')
            else:
                scan_run = ScanRun.objects.create(created_by=request.user, jd_text=jd_text)
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
                    experience_score, experience_notes = compute_experience_match(jd_text, resume_text)
                    cert_status, cert_details = analyze_certifications(jd_text, resume_text)
                    compliance_issues = detect_compliance_issues(jd_text, resume_text)
                    risk_flags = detect_risk_flags(jd_text, resume_text)
                    doc_quality_score, doc_quality_label = compute_document_quality(resume_text)
                    final_score, recommendation = compute_final_score_and_recommendation(
                        base_scores['semantic_score'], base_scores['skill_score'], experience_score,
                        len(compliance_issues), len(risk_flags),
                    )
                    qa_grade, qa_verdict = compute_qa_grade_and_verdict(
                        final_score, doc_quality_score, cert_status,
                        len(compliance_issues), len(risk_flags), recommendation,
                    )
                    ScanResult.objects.create(
                        scan_run=scan_run,
                        resume=resume,
                        candidate_name=resume.candidate_name or fname,
                        document_quality_score=doc_quality_score,
                        document_quality_label=doc_quality_label,
                        skill_match_percentage=base_scores['skill_score'],
                        experience_match_score=experience_score,
                        experience_notes=experience_notes,
                        certification_status=cert_status,
                        certification_details=cert_details,
                        compliance_issues=compliance_issues,
                        risk_flags=risk_flags,
                        final_weighted_score=final_score,
                        recommendation=recommendation,
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
def scan_report(request, result_id):
    """Full QA report for one candidate (print-friendly)."""
    result = get_object_or_404(ScanResult, pk=result_id, scan_run__created_by=request.user)
    return render(request, 'resumes/scan_report.html', {'result': result})


def extract_years_of_experience(text):
    """
    Very simple regex-based extraction of years of experience from text.
    Looks for patterns like '5 years', '3+ yrs', etc.
    """
    if not text:
        return None
    matches = re.findall(r'(\d+)\s*\+?\s*(?:years?|yrs?)', text.lower())
    if not matches:
        return None
    try:
        return max(int(m) for m in matches)
    except ValueError:
        return None


def compute_experience_match(jd_text, resume_text):
    jd_years = extract_years_of_experience(jd_text)
    resume_years = extract_years_of_experience(resume_text)

    if jd_years is None or resume_years is None:
        return 50.0, "Insufficient explicit experience data in JD or resume."

    ratio = resume_years / jd_years if jd_years > 0 else 1
    score = max(0.0, min(100.0, ratio * 100))
    notes = f"JD requires approximately {jd_years}+ years; resume indicates about {resume_years} years."
    return round(score, 2), notes


KNOWN_CERT_KEYWORDS = [
    "aws certified",
    "azure",
    "gcp",
    "pmp",
    "cissp",
    "cisa",
    "cism",
    "scrum master",
    "csm",
    "salesforce",
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
    "background check",
    "drug test",
    "security clearance",
    "work authorization",
    "work permit",
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
    "terminated",
    "fired",
    "layoff",
    "disciplinary",
    "probation",
    "criminal",
    "conviction",
    "warning letter",
]


def detect_risk_flags(jd_text, resume_text):
    # JD not strictly needed here but kept for signature flexibility
    resume_lower = resume_text.lower()
    flags = []

    for kw in RISK_KEYWORDS:
        if kw in resume_lower:
            flags.append(f"Resume contains potential risk term: '{kw}'.")

    return flags


def compute_final_score_and_recommendation(
    semantic_score,
    skill_score,
    experience_score,
    compliance_issue_count,
    risk_flag_count,
):
    base_score = (0.4 * semantic_score) + (0.35 * skill_score) + (0.25 * experience_score)
    penalty = (compliance_issue_count * 5) + (risk_flag_count * 7)
    final = max(0.0, min(100.0, base_score - penalty))

    if final >= 80 and compliance_issue_count == 0 and risk_flag_count == 0:
        recommendation = "Hire"
    elif final >= 55:
        recommendation = "Hold"
    else:
        recommendation = "Reject"

    return round(final, 2), recommendation


DOCUMENT_QUALITY_KEYWORDS = [
    "experience", "education", "skills", "summary", "objective",
    "work", "employment", "certification", "project", "contact", "email",
]


def compute_document_quality(resume_text):
    """
    Simple QA: completeness of resume (length + presence of common sections).
    Returns (score 0-100, label).
    """
    if not resume_text or len(resume_text.strip()) < 50:
        return 0.0, "Incomplete or unreadable document"
    text_lower = resume_text.lower()
    word_count = len(resume_text.split())
    section_hits = sum(1 for kw in DOCUMENT_QUALITY_KEYWORDS if kw in text_lower)
    # Score: base on word count (cap at 500) + section coverage
    length_score = min(100.0, (word_count / 5.0))  # 500 words = 100
    section_score = min(100.0, (section_hits / len(DOCUMENT_QUALITY_KEYWORDS)) * 100)
    score = (0.5 * length_score) + (0.5 * section_score)
    score = round(min(100.0, score), 2)
    if score >= 80:
        label = "High quality – complete and well-structured"
    elif score >= 55:
        label = "Good – main sections present"
    elif score >= 30:
        label = "Fair – some sections missing or brief"
    else:
        label = "Needs improvement – sparse or unclear content"
    return score, label


def compute_qa_grade_and_verdict(
    final_score,
    doc_quality_score,
    cert_status,
    compliance_count,
    risk_count,
    recommendation,
):
    """
    Best QA style: letter grade (A/B/C/D) and short verdict.
    """
    cert_ok = "missing" not in cert_status.lower() and "not specified" not in cert_status.lower()
    cert_ok = cert_ok or "all mandatory" in cert_status.lower()

    if final_score >= 80 and doc_quality_score >= 60 and compliance_count == 0 and risk_count == 0:
        grade = "A"
        verdict = "Best QA – Strong match, document and checks passed. Ready for next stage."
    elif final_score >= 65 and compliance_count == 0 and risk_count == 0:
        grade = "B"
        verdict = "Good QA – Meets requirements. Minor gaps (e.g. certs) can be clarified."
    elif final_score >= 50 or (compliance_count == 0 and risk_count == 0):
        grade = "C"
        verdict = "Hold – Some criteria met. Review experience, certs or compliance before deciding."
    else:
        grade = "D"
        verdict = "Does not meet QA – Significant gaps, compliance or risk issues. Not recommended."
    return grade, verdict
