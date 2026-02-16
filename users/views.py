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
        messages.info(request, "Ești deja autentificat.")
        return redirect("users:profile")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        role = request.POST.get("role")

        # Validări manuale îmbunătățite
        if len(username) < 4:
            messages.error(request, "Numele de utilizator trebuie să aibă minim 4 caractere.")
            return redirect("users:register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Acest nume de utilizator este deja folosit.")
            return redirect("users:register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Acest email este deja folosit.")
            return redirect("users:register")

        if len(password) < 6:
            messages.error(request, "Parola trebuie să aibă minim 6 caractere.")
            return redirect("users:register")

        # Crearea utilizatorului
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Rolul utilizatorului
        if role == "organizer":
            user.is_organizer = True
            user.is_participant = False
        else:
            user.is_participant = True
            user.is_organizer = False

        user.save()

        messages.success(request, "Cont creat cu succes! Te poți autentifica acum.")
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
            messages.success(request, f"Bine ai revenit, {user.username}!")
            return redirect("users:profile")
        else:
            messages.error(request, "Nume de utilizator sau parolă incorectă.")

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
    messages.info(request, "Te-ai deconectat cu succes.")
    return redirect("users:login")

