from django.shortcuts import render, redirect, get_object_or_404
from .models import JobRequirement
from .forms import JobRequirementForm

def job_list(request):
    jobs = JobRequirement.objects.all().order_by('-created_at')
    return render(request, 'jobs/job_list.html', {'jobs': jobs})

def job_create(request):
    if request.method == 'POST':
        form = JobRequirementForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('job_list')
    else:
        form = JobRequirementForm()
    return render(request, 'jobs/job_form.html', {'form': form})

def job_detail(request, pk):
    job = get_object_or_404(JobRequirement, pk=pk)
    # Get associated resumes/scores later
    return render(request, 'jobs/job_detail.html', {'job': job})
