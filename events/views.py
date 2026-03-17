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
from django.utils import timezone

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
            messages.error(request, "You must be authenticated.")
            return redirect("users:login")

        if not getattr(request.user, "is_participant", False):
            messages.error(request, "Only participants can reserve tickets.")
            return redirect("events:events_list")

        ticket_id = request.POST.get("ticket_id")
        try:
            quantity = int(request.POST.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1

        if quantity <= 0:
            messages.error(request, "Invalid quantity.")
            return redirect("events:event_detail", pk=pk)

        ticket_type = get_object_or_404(TicketType, id=ticket_id, event=event)

        try:
            with transaction.atomic():
                ticket_type.refresh_from_db()
                if not ticket_type.has_stock(quantity):
                    messages.error(request, "Not enough tickets available.")
                    return redirect("events:event_detail", pk=pk)

                Reservation.objects.create(
                    user=request.user,
                    ticket_type=ticket_type,
                    quantity=quantity,
                    confirmed=False,
                )
                ticket_type.reserve(quantity)

        except ValidationError:
            messages.error(request, "Not enough tickets available.")
            return redirect("events:event_detail", pk=pk)

        messages.success(request, "Reservation created! Please complete your payment.")
        return redirect("events:my_reservations")

    return render(request, "events/event_detail.html", {"event": event})


@login_required
def my_tickets(request):
    if not request.user.is_participant:
        messages.error(request, "Only participants can view tickets.")
        return redirect("pages:home")

    tickets = Reservation.objects.filter(
        user=request.user,
        confirmed=True
    ).select_related("ticket_type", "ticket_type__event")

    return render(request, "events/my_tickets.html", {"tickets": tickets})


@login_required
def my_reservations(request):
    if not request.user.is_participant:
        messages.error(request, "Only participants can access this page.")
        return redirect("pages:home")

    reservations = Reservation.objects.filter(
        user=request.user
    ).select_related("ticket_type", "ticket_type__event")

    if request.method == "POST":
        res_id = request.POST.get("reservation_id")
        reservation = Reservation.objects.filter(id=res_id, user=request.user).first()

        if reservation:
            if reservation.confirmed:
                messages.error(request, "You cannot cancel a paid reservation.")
            else:
                reservation.ticket_type.release(reservation.quantity)
                reservation.delete()
                messages.success(request, "Reservation has been cancelled.")

        return redirect("events:my_reservations")

    return render(request, "events/my_reservations.html", {"reservations": reservations})


@login_required
def create_event(request):
    if not request.user.is_organizer:
        messages.error(request, "You do not have permission.")
        return redirect("pages:home")

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        location = request.POST.get("location")
        start_date = parse_datetime(request.POST.get("start_date"))
        end_date = parse_datetime(request.POST.get("end_date"))
        image = request.FILES.get("image")

        if not all([title, description, location, start_date, end_date]):
            messages.error(request, "Please fill in all fields.")
            return redirect("events:create_event")

        if end_date < start_date:
            messages.error(request, "Invalid time period.")
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

        messages.success(request, "Event created!")
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
            messages.error(request, "Invalid dates.")
            return redirect("events:edit_event", event_id=event.id)

        if end_date < start_date:
            messages.error(request, "Invalid dates.")
            return redirect("events:edit_event", event_id=event.id)

        event.start_date = start_date
        event.end_date = end_date

        if request.FILES.get("image"):
            event.image = request.FILES.get("image")

        event.save()
        messages.success(request, "Event updated!")
        return redirect("events:event_detail", pk=event.id)

    return render(request, "events/edit_event.html", {"event": event})

@login_required
def ticket_management(request, event_id):
    # Fetch event and pre-fetch ticket types for performance (Analytics)
    event = get_object_or_404(
        Event.objects.prefetch_related("ticket_types"),
        id=event_id,
        organizer=request.user
    )

    # Fetch all reservations and user data in a single query
    reservations = Reservation.objects.filter(
        ticket_type__event=event
    ).select_related("user", "ticket_type")

    # Here we use properties created in the Event model:
    # event.total_revenue -> comes directly from model calculation
    # event.tickets_sold -> comes from model aggregate
    # event.total_capacity -> comes from the sum of total_quantity

    return render(request, "events/ticket_management.html", {
        "event": event,
        "reservations": reservations,
        # No need to calculate anything here,
        # as the template will directly call {{ event.total_revenue }}
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
        messages.success(request, "Customization saved!")
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
    reservation = get_object_or_404(
        Reservation.objects.select_for_update(),
        id=reservation_id,
        user=request.user
    )

    if reservation.confirmed:
        return JsonResponse({"error": "Already paid"}, status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Creează sau recuperează plata
    payment, _ = Payment.objects.get_or_create(
        reservation=reservation,
        defaults={"amount": reservation.total_price}
    )

    # Dacă deja există un PaymentIntent, îl reutilizăm
    if payment.stripe_payment_intent:
        intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent)
    else:
        amount_cents = int(reservation.total_price * Decimal("100"))

        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=settings.STRIPE_CURRENCY,
            metadata={
                "reservation_id": reservation.id,
                "user_id": request.user.id,
            },
        )

        payment.stripe_payment_intent = intent.id
        payment.stripe_client_secret = intent.client_secret
        payment.save()

    return JsonResponse({"clientSecret": intent.client_secret})

@login_required
def payment_success(request):
    payment_intent_id = request.GET.get("payment_intent")

    if not payment_intent_id:
        messages.error(request, "Could not confirm payment.")
        return redirect("events:my_reservations")

    with transaction.atomic():
        # Blocăm în baza de date plata pentru a evita concurența
        payment = (
            Payment.objects
            .select_for_update()
            .select_related("reservation")
            .filter(stripe_payment_intent=payment_intent_id)
            .first()
        )

        if not payment:
            messages.error(request, "Payment not found.")
            return redirect("events:my_reservations")

        if payment.status != Payment.STATUS_COMPLETED:
            payment.status = Payment.STATUS_COMPLETED
            payment.save()

            reservation = payment.reservation
            reservation.confirmed = True
            reservation.save()
        else:
            reservation = payment.reservation

    messages.success(request, "✅ Payment completed successfully!")

    return render(request, "events/payment_success.html", {
        "reservation": reservation,
    })


@login_required
def payment_cancel(request):
    messages.warning(request, "Payment was cancelled.")
    return render(request, "events/payment_cancel.html")

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

        payment = Payment.objects.select_related("reservation").filter(
            stripe_payment_intent=pi_id
        ).first()
        if payment and payment.status != Payment.STATUS_COMPLETED:
            payment.status = Payment.STATUS_COMPLETED
            payment.save()

            reservation = payment.reservation
            reservation.confirmed = True
            reservation.save()

    return HttpResponse(status=200)


import io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader


@login_required
def download_ticket_pdf(request, reservation_id):
    # Verifică dacă rezervarea există și e confirmată
    reservation = get_object_or_404(
        Reservation,
        id=reservation_id,
        user=request.user,
        confirmed=True
    )

    # 1️⃣ Creează QR Code
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(reservation.ticket_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e3a8a", back_color="#f3f4f6")  # QR albastru pe fundal deschis

    # 2️⃣ Creează PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Background color (optional)
    p.setFillColorRGB(0.95, 0.95, 0.97)
    p.rect(0, 0, width, height, fill=1, stroke=0)

    # Header
    p.setFont("Helvetica-Bold", 28)
    p.setFillColor("#2563eb")
    p.drawCentredString(width/2, height - 80, f"🎫 {reservation.ticket_type.event.title}")

    # Subheader
    p.setFont("Helvetica-Bold", 16)
    p.setFillColor("#1f2937")
    p.drawString(50, height - 130, f"Ticket Type: {reservation.ticket_type.name}")
    p.drawString(50, height - 155, f"Attendee: {reservation.user.get_full_name() or reservation.user.username}")
    p.drawString(50, height - 180, f"Unique Code: {reservation.ticket_code}")
    p.drawString(50, height - 205, f"Event Location: {reservation.ticket_type.event.location}")
    # Convertim la ora locală
    event_start = timezone.localtime(reservation.ticket_type.event.start_date)

    # Afișăm în PDF
    p.drawString(50, height - 230, f"Event Date: {event_start.strftime('%d %b %Y %H:%M')}")
    # Draw a line separator
    p.setStrokeColor("#2563eb")
    p.setLineWidth(2)
    p.line(50, height - 245, width - 50, height - 245)

    # Insert QR Code
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    qr_size = 180
    p.drawImage(ImageReader(img_buffer), width - qr_size - 50, height - qr_size - 300, width=qr_size, height=qr_size)

    # Footer / Instructions
    p.setFont("Helvetica-Oblique", 12)
    p.setFillColor("#374151")
    p.drawString(50, 50, "Please present this ticket at the event entrance.")
    p.drawString(50, 35, "QR code will be scanned for validation.")

    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="ticket_{reservation.ticket_code}.pdf"'
    return response