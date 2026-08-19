import io
import logging
from decimal import Decimal, InvalidOperation

import qrcode
import stripe
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from .models import Event, TicketType, Reservation, Payment

logger = logging.getLogger(__name__)


def events_list(request):
    query = request.GET.get("q", "")
    date = request.GET.get("date", "")

    events = Event.objects.prefetch_related("ticket_types").order_by("start_date")

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
    event = get_object_or_404(Event.objects.prefetch_related("ticket_types"), pk=pk)

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to continue.")
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
            messages.error(request, "Please enter a valid number of tickets.")
            return redirect("events:event_detail", pk=pk)

        try:
            with transaction.atomic():
                # select_for_update() locks this row for the duration of the
                # transaction, so two concurrent requests for the same last
                # ticket can't both pass the stock check before either commits.
                ticket_type = get_object_or_404(
                    TicketType.objects.select_for_update(), id=ticket_id, event=event
                )
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

        with transaction.atomic():
            # Lock the reservation row before checking/acting on `confirmed`,
            # so a webhook confirming payment concurrently can't slip in
            # between the check and the delete (see audit-cod).
            reservation = Reservation.objects.select_for_update().filter(
                id=res_id, user=request.user
            ).first()

            if reservation:
                if reservation.confirmed:
                    messages.error(request, "You cannot cancel a paid reservation.")
                else:
                    ticket_type = TicketType.objects.select_for_update().get(
                        id=reservation.ticket_type_id
                    )
                    ticket_type.release(reservation.quantity)
                    reservation.delete()
                    messages.success(request, "Reservation has been cancelled.")

        return redirect("events:my_reservations")

    return render(request, "events/my_reservations.html", {"reservations": reservations})


@login_required
def create_event(request):
    if not request.user.is_organizer:
        messages.error(request, "You don't have permission to do that.")
        return redirect("pages:home")

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        location = request.POST.get("location")
        image = request.FILES.get("image")

        try:
            start_date = parse_datetime(request.POST.get("start_date") or "")
            end_date = parse_datetime(request.POST.get("end_date") or "")
        except ValueError:
            start_date = end_date = None

        if not all([title, description, location, start_date, end_date]):
            messages.error(request, "Please fill in all fields.")
            return redirect("events:create_event")

        if len(title) > 200 or len(location) > 255:
            messages.error(request, "Title or location is too long.")
            return redirect("events:create_event")

        if end_date < start_date:
            messages.error(request, "The end date must be after the start date.")
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

            try:
                price = Decimal(price)
                qty = int(qty)
            except (InvalidOperation, ValueError):
                continue

            if qty <= 0 or price < 0 or len(name) > 100:
                continue

            TicketType.objects.create(
                event=event,
                name=name,
                price=price,
                total_quantity=qty,
                available_quantity=qty,
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
            messages.error(request, "Please double-check your event dates.")
            return redirect("events:edit_event", event_id=event.id)

        if end_date < start_date:
            messages.error(request, "The end date must be after the start date.")
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
    })

@login_required
def create_payment_intent(request, reservation_id):
    # select_for_update() necesita un bloc atomic activ, altfel Django
    # ridica TransactionManagementError la fiecare apel.
    with transaction.atomic():
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
            try:
                intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent)
            except stripe.error.StripeError:
                logger.exception("Stripe retrieve failed for payment %s", payment.id)
                return JsonResponse({"error": "Payment provider error."}, status=502)
        else:
            amount_cents = int(reservation.total_price * Decimal("100"))

            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=settings.STRIPE_CURRENCY,
                    metadata={
                        "reservation_id": reservation.id,
                        "user_id": request.user.id,
                    },
                )
            except stripe.error.StripeError:
                logger.exception("Stripe create failed for reservation %s", reservation.id)
                return JsonResponse({"error": "Payment provider error."}, status=502)

            payment.stripe_payment_intent = intent.id
            payment.stripe_client_secret = intent.client_secret
            payment.save()

    return JsonResponse({"clientSecret": intent.client_secret})

@login_required
def payment_success(request):
    payment_intent_id = request.GET.get("payment_intent")

    if not payment_intent_id:
        messages.error(
            request,
            "We couldn't confirm your payment. If you were charged, don't worry — "
            "contact us and we'll sort it out.",
        )
        return redirect("events:my_reservations")

    # Confirmarea se face DOAR pe baza statusului real din Stripe, nu pe
    # simpla prezenta a parametrului in URL (altfel oricine ar putea
    # "confirma" o plata nefacuta navigand direct la acest link).
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.error.StripeError:
        logger.warning("Stripe retrieve failed for intent %s (user %s)", payment_intent_id, request.user.id)
        messages.error(
            request,
            "We couldn't confirm your payment. If you were charged, don't worry — "
            "contact us and we'll sort it out.",
        )
        return redirect("events:my_reservations")

    if intent.status != "succeeded":
        logger.warning(
            "payment_success called with non-succeeded intent %s (status=%s, user=%s)",
            payment_intent_id, intent.status, request.user.id,
        )
        messages.error(request, "Payment was not completed.")
        return redirect("events:my_reservations")

    with transaction.atomic():
        # Blocăm în baza de date plata pentru a evita concurența
        payment = (
            Payment.objects
            .select_for_update()
            .select_related("reservation")
            .filter(stripe_payment_intent=payment_intent_id, reservation__user=request.user)
            .first()
        )

        if not payment:
            messages.error(
                request,
                "We couldn't find that payment. Please go back to your "
                "reservations and try again.",
            )
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
        logger.warning("Rejected webhook call with invalid signature.")
        return HttpResponse(status=400)

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        pi_id = intent["id"]

        with transaction.atomic():
            payment = (
                Payment.objects
                .select_for_update()
                .select_related("reservation")
                .filter(stripe_payment_intent=pi_id)
                .first()
            )
            if not payment:
                logger.warning("Webhook: no local Payment found for intent %s", pi_id)
            elif payment.status != Payment.STATUS_COMPLETED:
                payment.status = Payment.STATUS_COMPLETED
                payment.save()

                reservation = payment.reservation
                reservation.confirmed = True
                reservation.save()

    return HttpResponse(status=200)


@login_required
def download_ticket_pdf(request, reservation_id):
    reservation = get_object_or_404(
        Reservation,
        id=reservation_id,
        user=request.user,
        confirmed=True
    )

    event = reservation.ticket_type.event
    attendee_name = reservation.user.get_full_name() or reservation.user.username
    event_start = timezone.localtime(event.start_date)

    # Brand colors
    primary_rgb = (99 / 255, 102 / 255, 241 / 255)      # indigo
    accent_rgb = (236 / 255, 72 / 255, 153 / 255)       # pink
    text_rgb = (17 / 255, 24 / 255, 39 / 255)           # slate-900
    muted_rgb = (107 / 255, 114 / 255, 128 / 255)       # gray-500
    border_rgb = (229 / 255, 231 / 255, 235 / 255)      # gray-200
    bg_rgb = (248 / 255, 250 / 255, 252 / 255)          # slate-50
    white_rgb = (1, 1, 1)

    # Create QR
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(reservation.ticket_code)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1e1b4b", back_color="white")

    # PDF
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Background
    pdf.setFillColorRGB(*bg_rgb)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    # Main card
    card_x = 42
    card_y = 70
    card_w = width - 84
    card_h = height - 140

    pdf.setFillColorRGB(*white_rgb)
    pdf.setStrokeColorRGB(*border_rgb)
    pdf.roundRect(card_x, card_y, card_w, card_h, 18, fill=1, stroke=1)

    # Top gradient-ish bands
    pdf.setFillColorRGB(*primary_rgb)
    pdf.roundRect(card_x, height - 150, card_w, 60, 18, fill=1, stroke=0)

    pdf.setFillColorRGB(*accent_rgb)
    pdf.roundRect(card_x + card_w - 180, height - 150, 180, 60, 18, fill=1, stroke=0)

    # Title
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(card_x + 24, height - 118, "Event Ticket")

    # Event name
    pdf.setFillColorRGB(*text_rgb)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(card_x + 24, height - 195, event.title[:55])

    # Subtitle
    pdf.setFont("Helvetica", 11)
    pdf.setFillColorRGB(*muted_rgb)
    pdf.drawString(card_x + 24, height - 215, "Present this PDF at the event entrance for validation.")

    # Divider
    pdf.setStrokeColorRGB(*border_rgb)
    pdf.setLineWidth(1)
    pdf.line(card_x + 24, height - 232, card_x + card_w - 24, height - 232)

    # Left info
    label_x = card_x + 24
    value_x = card_x + 24
    current_y = height - 270

    def draw_field(label, value, y):
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColorRGB(*muted_rgb)
        pdf.drawString(label_x, y, label.upper())

        pdf.setFont("Helvetica-Bold", 14)
        pdf.setFillColorRGB(*text_rgb)
        pdf.drawString(value_x, y - 18, str(value))
        return y - 48

    current_y = draw_field("Ticket Type", reservation.ticket_type.name, current_y)
    current_y = draw_field("Attendee", attendee_name, current_y)
    current_y = draw_field("Unique Code", reservation.ticket_code, current_y)
    current_y = draw_field("Location", event.location, current_y)
    current_y = draw_field("Event Date", event_start.strftime("%d %b %Y, %H:%M"), current_y)
    current_y = draw_field("Quantity", reservation.quantity, current_y)

    # QR area
    qr_size = 170
    qr_x = card_x + card_w - qr_size - 36
    qr_y = height - 470

    pdf.setFillColorRGB(*bg_rgb)
    pdf.setStrokeColorRGB(*border_rgb)
    pdf.roundRect(qr_x - 12, qr_y - 12, qr_size + 24, qr_size + 24, 16, fill=1, stroke=1)

    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf.drawImage(
        ImageReader(qr_buffer),
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size
    )

    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColorRGB(*primary_rgb)
    pdf.drawCentredString(qr_x + qr_size / 2, qr_y - 24, "SCAN FOR VALIDATION")

    # Bottom note box
    note_x = card_x + 24
    note_y = card_y + 34
    note_w = card_w - 48
    note_h = 62

    pdf.setFillColorRGB(248 / 255, 250 / 255, 252 / 255)
    pdf.setStrokeColorRGB(*border_rgb)
    pdf.roundRect(note_x, note_y, note_w, note_h, 14, fill=1, stroke=1)

    pdf.setFont("Helvetica", 11)
    pdf.setFillColorRGB(*muted_rgb)
    pdf.drawString(note_x + 16, note_y + 38, "Please arrive a few minutes before the event starts.")
    pdf.drawString(note_x + 16, note_y + 20, "Your QR code will be scanned at check-in.")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="ticket_{reservation.ticket_code}.pdf"'
    return response