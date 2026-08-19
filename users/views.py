import logging
from urllib.parse import quote

from django.core.cache import cache
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CaptchaForm

User = get_user_model()
logger = logging.getLogger(__name__)

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300


def _login_attempts_key(request):
    return f"login_attempts:{request.META.get('REMOTE_ADDR', 'unknown')}"


def _safe_next_url(request, next_url):
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


def _redirect_with_next(url_name, next_url):
    if next_url:
        return redirect(f"{reverse(url_name)}?next={quote(next_url)}")
    return redirect(url_name)


# ============================
# 🔹 Register (User Create)
# ============================
def register(request):
    if request.user.is_authenticated:
        messages.info(request, "You are already logged in.")
        return redirect("users:profile")

    next_url = _safe_next_url(request, request.POST.get("next") or request.GET.get("next"))

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        password_confirm = request.POST.get("password_confirm") or ""
        role = request.POST.get("role")

        # Improved manual validations
        if len(username) < 4:
            messages.error(request, "Username must be at least 4 characters long.")
            return _redirect_with_next("users:register", next_url)

        if not email:
            messages.error(request, "Email is required.")
            return _redirect_with_next("users:register", next_url)

        if User.objects.filter(username=username).exists():
            messages.error(request, "This username is already taken.")
            return _redirect_with_next("users:register", next_url)

        if User.objects.filter(email=email).exists():
            messages.error(request, "This email is already in use.")
            return _redirect_with_next("users:register", next_url)

        if password != password_confirm:
            messages.error(request, "Passwords don't match.")
            return _redirect_with_next("users:register", next_url)

        captcha_form = CaptchaForm(request.POST)
        if not captcha_form.is_valid():
            messages.error(request, "Please confirm you're not a robot.")
            return _redirect_with_next("users:register", next_url)

        try:
            validate_password(password, user=User(username=username, email=email))
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
            return _redirect_with_next("users:register", next_url)

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # User role
        if role == "organizer":
            user.is_organizer = True
            user.is_participant = False
        else:
            user.is_participant = True
            user.is_organizer = False

        user.save()

        messages.success(request, "Account created successfully! You can now log in.")
        return _redirect_with_next("users:login", next_url)

    return render(request, "users/register.html", {"next": next_url, "captcha_form": CaptchaForm()})


# ============================
# 🔹 Login
# ============================
def user_login(request):
    if request.user.is_authenticated:
        return redirect("users:profile")

    next_url = _safe_next_url(request, request.POST.get("next") or request.GET.get("next"))

    if request.method == "POST":
        attempts_key = _login_attempts_key(request)
        attempts = cache.get(attempts_key, 0)

        if attempts >= LOGIN_MAX_ATTEMPTS:
            logger.warning("Login rate-limited for IP %s", request.META.get("REMOTE_ADDR"))
            messages.error(request, "Too many failed attempts. Please try again in a few minutes.")
            return render(request, "users/login.html", {"next": next_url})

        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        user = authenticate(request, username=username, password=password)

        if user is not None:
            cache.delete(attempts_key)
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(next_url) if next_url else redirect("users:profile")
        else:
            cache.set(attempts_key, attempts + 1, timeout=LOGIN_LOCKOUT_SECONDS)
            messages.error(request, "Incorrect username or password.")

    return render(request, "users/login.html", {"next": next_url})


# ============================
# 🔹 Profile Page
# ============================
@login_required(login_url="users:login")
def profile(request):
    return render(request, "users/profile.html", {
        "user": request.user
    })


# ============================
# 🔹 Logout
# ============================
@login_required
def user_logout(request):
    logout(request)
    messages.info(request, "You have logged out successfully.")
    return redirect("users:login")