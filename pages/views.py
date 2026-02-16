from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ContactForm
from .models import SupportMessage


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Your message has been sent successfully! ✨")
            return redirect("pages:contact")
        else:
            messages.error(request, "The form contains errors. Please check your input.")
    else:
        form = ContactForm()

    support_messages = SupportMessage.objects.order_by("created_at")[:200]

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


from django.shortcuts import render
from django.utils import timezone
from events.models import Event



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

