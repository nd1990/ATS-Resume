from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import SignUpForm

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('bulk_upload')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})



def home(request):
    if request.user.is_authenticated:
        return redirect('bulk_upload')
    return render(request, 'core/home.html')

def pricing(request):
    return render(request, 'core/pricing.html')

