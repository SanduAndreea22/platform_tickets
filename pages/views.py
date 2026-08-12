import uuid

from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ContactForm
from .models import SupportMessage
from django.utils import timezone
from events.models import Event

SESSION_THREAD_KEY = "contact_thread_id"


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)

        if form.is_valid():
            # Fiecare vizitator are propriul "thread" legat de sesiune, ca
            # sa nu vada mesajele altor persoane (vezi si get_or_create de mai jos).
            thread_id = request.session.get(SESSION_THREAD_KEY)
            if not thread_id:
                thread_id = str(uuid.uuid4())
                request.session[SESSION_THREAD_KEY] = thread_id

            support_message = form.save(commit=False)
            support_message.thread_id = thread_id
            support_message.save()

            messages.success(request, "Your message has been sent successfully! ✨")
            return redirect("pages:contact")
        else:
            messages.error(request, "The form contains errors. Please check your input.")
    else:
        form = ContactForm()

    thread_id = request.session.get(SESSION_THREAD_KEY)
    if thread_id:
        support_messages = SupportMessage.objects.filter(
            thread_id=thread_id
        ).order_by("created_at")[:200]
    else:
        support_messages = SupportMessage.objects.none()

    return render(request, "pages/contact.html", {
        "form": form,
        "support_messages": support_messages,
    })


def about(request):
    return render(request, "pages/about.html")


def terms(request):
    return render(request, "pages/terms.html")


def privacy(request):
    return render(request, "pages/privacy.html")


def partners(request):
    return render(request, "pages/partners.html")


def how_it_works(request):
    return render(request, "pages/how_it_works.html")

def home(request):
    now = timezone.now()

    featured_events = (
        Event.objects
        .filter(end_date__gte=now)
        .select_related("organizer")
        .prefetch_related("ticket_types")
        .order_by("start_date")[:6]
    )

    return render(request, "pages/home.html", {
        "featured_events": featured_events,
    })

