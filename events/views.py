from decimal import Decimal
import stripe
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from .models import Event, TicketType, Reservation, Payment

def events_list(request):
    query = request.GET.get("q", "")
    date = request.GET.get("date", "")

    events = Event.objects.all().order_by("start_date")

    if query:
        events = events.filter(
            Q(title__icontains=query) | Q(location__icontains=query)
        )

    if date:
        events = events.filter(start_date__date=date)

    return render(request, "events/events_list.html", {
        "events": events,
        "query": query,
        "date": date,
    })


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Trebuie să fii autentificat.")
            return redirect("users:login")

        if not getattr(request.user, "is_participant", False):
            messages.error(request, "Doar participanții pot rezerva bilete.")
            return redirect("events:events_list")

        ticket_id = request.POST.get("ticket_id")
        try:
            quantity = int(request.POST.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1

        if quantity <= 0:
            messages.error(request, "Cantitate invalidă.")
            return redirect("events:event_detail", pk=pk)

        ticket_type = get_object_or_404(TicketType, id=ticket_id, event=event)

        try:
            with transaction.atomic():
                ticket_type.refresh_from_db()
                if not ticket_type.has_stock(quantity):
                    messages.error(request, "Nu sunt suficiente bilete disponibile.")
                    return redirect("events:event_detail", pk=pk)

                Reservation.objects.create(
                    user=request.user,
                    ticket_type=ticket_type,
                    quantity=quantity,
                    confirmed=False,
                )
                ticket_type.reserve(quantity)

        except ValidationError:
            messages.error(request, "Nu sunt suficiente bilete disponibile.")
            return redirect("events:event_detail", pk=pk)

        messages.success(request, "Rezervare creată! Finalizează plata.")
        return redirect("events:my_reservations")

    return render(request, "events/event_detail.html", {"event": event})


@login_required
def my_tickets(request):
    if not request.user.is_participant:
        messages.error(request, "Doar participanții pot vedea biletele.")
        return redirect("pages:home")

    tickets = Reservation.objects.filter(
        user=request.user,
        confirmed=True
    ).select_related("ticket_type", "ticket_type__event")

    return render(request, "events/my_tickets.html", {"tickets": tickets})


@login_required
def my_reservations(request):
    if not request.user.is_participant:
        messages.error(request, "Doar participanții pot accesa această pagină.")
        return redirect("pages:home")

    reservations = Reservation.objects.filter(
        user=request.user
    ).select_related("ticket_type", "ticket_type__event")

    if request.method == "POST":
        res_id = request.POST.get("reservation_id")
        reservation = Reservation.objects.filter(id=res_id, user=request.user).first()

        if reservation:
            if reservation.confirmed:
                messages.error(request, "Nu poți anula o rezervare plătită.")
            else:
                reservation.ticket_type.release(reservation.quantity)
                reservation.delete()
                messages.success(request, "Rezervarea a fost anulată.")

        return redirect("events:my_reservations")

    return render(request, "events/my_reservations.html", {"reservations": reservations})


@login_required
def create_event(request):
    if not request.user.is_organizer:
        messages.error(request, "Nu ai permisiunea.")
        return redirect("pages:home")

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        location = request.POST.get("location")
        start_date = parse_datetime(request.POST.get("start_date"))
        end_date = parse_datetime(request.POST.get("end_date"))
        image = request.FILES.get("image")

        if not all([title, description, location, start_date, end_date]):
            messages.error(request, "Completează toate câmpurile.")
            return redirect("events:create_event")

        if end_date < start_date:
            messages.error(request, "Perioadă invalidă.")
            return redirect("events:create_event")

        event = Event.objects.create(
            organizer=request.user,
            title=title,
            description=description,
            location=location,
            start_date=start_date,
            end_date=end_date,
            image=image,
        )

        names = request.POST.getlist("ticket_name")
        prices = request.POST.getlist("ticket_price")
        quantities = request.POST.getlist("ticket_quantity")

        for name, price, qty in zip(names, prices, quantities):
            if not name or not price or not qty:
                continue
            TicketType.objects.create(
                event=event,
                name=name,
                price=price,
                total_quantity=int(qty),
                available_quantity=int(qty),
            )

        messages.success(request, "Eveniment creat!")
        return redirect("events:events_list")

    return render(request, "events/create_event.html")

@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    if request.method == "POST":
        event.title = request.POST.get("title")
        event.description = request.POST.get("description")
        event.location = request.POST.get("location")

        start_date = parse_datetime(request.POST.get("start_date"))
        end_date = parse_datetime(request.POST.get("end_date"))

        if not start_date or not end_date:
            messages.error(request, "Date invalide.")
            return redirect("events:edit_event", event_id=event.id)

        if end_date < start_date:
            messages.error(request, "Date invalide.")
            return redirect("events:edit_event", event_id=event.id)

        event.start_date = start_date
        event.end_date = end_date

        if request.FILES.get("image"):
            event.image = request.FILES.get("image")

        event.save()
        messages.success(request, "Eveniment actualizat!")
        return redirect("events:event_detail", pk=event.id)

    return render(request, "events/edit_event.html", {"event": event})

@login_required
def ticket_management(request, event_id):
    event = get_object_or_404(Event, id=event_id, organizer=request.user)
    reservations = Reservation.objects.filter(
        ticket_type__event=event
    ).select_related("user", "ticket_type")

    return render(request, "events/ticket_management.html", {
        "event": event,
        "reservations": reservations,
    })

@login_required
def customize_event(request, event_id):
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    if request.method == "POST":
        event.theme_color = request.POST.get("theme_color") or event.theme_color
        event.banner_text = request.POST.get("banner_text")
        event.promo_message = request.POST.get("promo_message")

        if request.FILES.get("image"):
            event.image = request.FILES.get("image")

        event.save()
        messages.success(request, "Personalizare salvată!")
        return redirect("events:event_detail", pk=event.id)

    return render(request, "events/customize_event.html", {"event": event})

@login_required
def my_events(request):
    events = Event.objects.filter(organizer=request.user)
    return render(request, "events/my_events.html", {"events": events})

@login_required
def payment_page(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    payment, _ = Payment.objects.get_or_create(
        reservation=reservation,
        defaults={"amount": reservation.total_price}
    )

    return render(request, "events/payment_page.html", {
        "reservation": reservation,
        "payment": payment,
        "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
        "CURRENCY": settings.STRIPE_CURRENCY,
    })

@login_required
def create_payment_intent(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    amount_cents = int(reservation.total_price * Decimal("100"))

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=settings.STRIPE_CURRENCY,
        metadata={"reservation_id": reservation.id},
    )

    payment = reservation.payment
    payment.stripe_payment_intent = intent.id
    payment.stripe_client_secret = intent.client_secret
    payment.save()

    return JsonResponse({"clientSecret": intent.client_secret})

@login_required
def payment_success(request):
    payment_intent_id = request.GET.get("payment_intent")

    if not payment_intent_id:
        messages.error(request, "Nu am putut confirma plata.")
        return redirect("events:my_reservations")

    payment = Payment.objects.filter(stripe_payment_intent=payment_intent_id).first()

    if not payment:
        messages.error(request, "Plata nu a fost găsită.")
        return redirect("events:my_reservations")

    payment.status = Payment.STATUS_COMPLETED
    payment.save()

    reservation = payment.reservation
    reservation.confirmed = True
    reservation.save()

    messages.success(request, "✅ Plata a fost efectuată cu succes!")
    return redirect("events:my_tickets")


@login_required
def payment_cancel(request):
    messages.warning(request, "Plata a fost anulată.")
    return redirect("events:my_reservations")

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        pi_id = intent["id"]

        payment = Payment.objects.filter(stripe_payment_intent=pi_id).first()
        if payment:
            payment.status = Payment.STATUS_COMPLETED
            payment.save()

            reservation = payment.reservation
            reservation.confirmed = True
            reservation.save()

    return HttpResponse(status=200)



