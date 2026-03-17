from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()


# ============================
# 🔹 Register (User Create)
# ============================
def register(request):
    if request.user.is_authenticated:
        messages.info(request, "You are already logged in.")
        return redirect("users:profile")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        role = request.POST.get("role")

        # Improved manual validations
        if len(username) < 4:
            messages.error(request, "Username must be at least 4 characters long.")
            return redirect("users:register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "This username is already taken.")
            return redirect("users:register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "This email is already in use.")
            return redirect("users:register")

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return redirect("users:register")

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
        return redirect("users:login")

    return render(request, "users/register.html")


# ============================
# 🔹 Login
# ============================
def user_login(request):
    if request.user.is_authenticated:
        return redirect("users:profile")

    if request.method == "POST":
        username = request.POST.get("username").strip()
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("users:profile")
        else:
            messages.error(request, "Incorrect username or password.")

    return render(request, "users/login.html")


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