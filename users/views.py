from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import secrets

from .models import UserProfile, PasswordReset
from .forms import (
    UserRegistrationForm, 
    UserLoginForm, 
    UserProfileForm,
    ExtendedProfileForm,
    PasswordChangeForm,
    PasswordResetForm,
    CVUploadForm
)


@require_http_methods(["GET", "POST"])
def register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                role = form.cleaned_data.get('role')
                user.profile.role = role
                user.profile.save()
                messages.success(request, 'Registration successful! Please log in.')
                return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()
    
    context = {'form': form}
    return render(request, 'user/register.html', context)


@require_http_methods(["GET", "POST"])
def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data.get('username_or_email')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me')
            
            # Try to authenticate with username or email
            user = authenticate(request, username=username_or_email, password=password)
            
            if user is None:
                # Try with email
                try:
                    user_obj = User.objects.get(email=username_or_email)
                    user = authenticate(request, username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None
            
            if user is not None:
                login(request, user)
                
                if remember_me:
                    request.session.set_expiry(timedelta(days=30))
                else:
                    request.session.set_expiry(0)
                
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username/email or password.')
    else:
        form = UserLoginForm()
    
    context = {'form': form}
    return render(request, 'user/login.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def profile_view(request):
    """User profile view"""
    user_profile = request.user.profile
    
    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, instance=request.user)
        profile_form = ExtendedProfileForm(request.POST, request.FILES, instance=user_profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        user_form = UserProfileForm(instance=request.user)
        profile_form = ExtendedProfileForm(instance=user_profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'profile': user_profile
    }
    return render(request, 'user/profile.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def change_password(request):
    """Change password view"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            user = request.user
            old_password = form.cleaned_data.get('old_password')
            new_password1 = form.cleaned_data.get('new_password1')
            
            if not user.check_password(old_password):
                messages.error(request, 'Current password is incorrect.')
                return redirect('change_password')
            
            user.set_password(new_password1)
            user.save()
            messages.success(request, 'Password changed successfully!')
            return redirect('login')
    else:
        form = PasswordChangeForm()
    
    context = {'form': form}
    return render(request, 'user/change_password.html', context)


@require_http_methods(["GET", "POST"])
def password_reset_request(request):
    """Password reset request view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            user = User.objects.get(email=email)
            
            # Generate reset token
            token = secrets.token_urlsafe(32)
            expires_at = timezone.now() + timedelta(hours=24)
            
            PasswordReset.objects.create(
                user=user,
                token=token,
                expires_at=expires_at
            )
            
            # TODO: Send email with reset link
            reset_link = request.build_absolute_uri(f'/auth/reset-password/{token}/')
            
            messages.success(request, 'Password reset link has been sent to your email.')
            return redirect('login')
    else:
        form = PasswordResetForm()
    
    context = {'form': form}
    return render(request, 'user/password_reset_request.html', context)


@require_http_methods(["GET", "POST"])
def password_reset_confirm(request, token):
    """Password reset confirmation view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    try:
        reset_obj = PasswordReset.objects.get(token=token, is_used=False)
        
        if reset_obj.expires_at < timezone.now():
            messages.error(request, 'Password reset link has expired.')
            return redirect('password_reset_request')
        
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            if password1 and password2 and password1 == password2:
                user = reset_obj.user
                user.set_password(password1)
                user.save()
                
                reset_obj.is_used = True
                reset_obj.save()
                
                messages.success(request, 'Password has been reset successfully. Please log in.')
                return redirect('login')
            else:
                messages.error(request, 'Passwords do not match.')
    
    except PasswordReset.DoesNotExist:
        messages.error(request, 'Invalid password reset link.')
        return redirect('password_reset_request')
    
    return render(request, 'user/password_reset_confirm.html', {'token': token})


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def upload_cv(request):
    """CV upload view"""
    user_profile = request.user.profile
    
    if request.method == 'POST':
        form = CVUploadForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            user_profile.cv_uploaded_at = timezone.now()
            user_profile.save()
            messages.success(request, 'CV uploaded successfully!')
            return redirect('profile')
    else:
        form = CVUploadForm(instance=user_profile)
    
    context = {'form': form}
    return render(request, 'user/upload_cv.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def dashboard(request):
    """User dashboard view"""
    user_profile = request.user.profile
    context = {
        'profile': user_profile,
        'has_cv': bool(user_profile.cv),
        'role': user_profile.role
    }
    return render(request, 'user/dashboard.html', context)