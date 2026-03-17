from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.db.models import Sum
import uuid


# ====================================
# 🎟️ MODEL: Event
# ====================================

hex_color_validator = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
    message="Color must be a valid hex code (example: #4f46e5).",
)


class Event(models.Model):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organized_events",
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=255)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    image = models.ImageField(upload_to="events/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # UI customization
    theme_color = models.CharField(
        max_length=20,
        default="#4f46e5",
        validators=[hex_color_validator],
        help_text="Event theme color (hex format, example: #4f46e5).",
    )

    banner_text = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Short banner text displayed on the event page.",
    )

    promo_message = models.TextField(
        blank=True,
        null=True,
        help_text="Promotional message displayed on the event page.",
    )

    class Meta:
        ordering = ["start_date"]
        verbose_name = "Event"
        verbose_name_plural = "Events"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="event_end_after_start",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

    @property
    def is_past(self):
        return self.end_date < timezone.now()

    @property
    def is_active(self):
        now = timezone.now()
        return self.start_date <= now <= self.end_date

    @property
    def available_tickets(self):
        return sum(t.available_quantity for t in self.ticket_types.all())

    @property
    def total_capacity(self):
        return sum(t.total_quantity for t in self.ticket_types.all())

    @property
    def tickets_sold(self):
        return self.ticket_types.aggregate(
            sold=Sum(models.F("total_quantity") - models.F("available_quantity"))
        )["sold"] or 0

    @property
    def total_revenue(self):
        return sum(
            res.total_price
            for res in Reservation.objects.filter(
                ticket_type__event=self,
                confirmed=True,
            )
        )


# ====================================
# 🎫 MODEL: TicketType
# ====================================

class TicketType(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="ticket_types"
    )

    name = models.CharField(max_length=100)

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    total_quantity = models.PositiveIntegerField()
    available_quantity = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Ticket type"
        verbose_name_plural = "Ticket types"
        ordering = ["event", "price"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_quantity__gt=0),
                name="ticket_total_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(available_quantity__gte=0),
                name="ticket_available_quantity_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(available_quantity__lte=models.F("total_quantity")),
                name="ticket_available_not_exceed_total",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.event.title}"

    def clean(self):
        if self.available_quantity > self.total_quantity:
            raise ValidationError(
                "Available tickets cannot exceed total tickets."
            )

    def has_stock(self, quantity: int) -> bool:
        return quantity > 0 and self.available_quantity >= quantity

    def reserve(self, quantity: int):

        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0.")

        if quantity > self.available_quantity:
            raise ValidationError("Not enough tickets available.")

        self.available_quantity -= quantity
        self.save(update_fields=["available_quantity"])

    def release(self, quantity: int):

        if quantity <= 0:
            return

        self.available_quantity = min(
            self.total_quantity,
            self.available_quantity + quantity
        )

        self.save(update_fields=["available_quantity"])


# ====================================
# 📦 MODEL: Reservation
# ====================================

class Reservation(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )

    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField(default=1)

    confirmed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    ticket_code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Reservation"
        verbose_name_plural = "Reservations"
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="reservation_quantity_positive",
            ),
        ]

    def save(self, *args, **kwargs):

        if not self.ticket_code:
            self.ticket_code = f"ET-{uuid.uuid4().hex[:10].upper()}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.ticket_type.name}"

    @property
    def unit_price(self):
        return self.ticket_type.price

    @property
    def total_price(self):
        return self.ticket_type.price * self.quantity

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Quantity must be at least 1.")


# ====================================
# 💳 MODEL: Payment
# ====================================

class Payment(models.Model):

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name="payment",
    )

    amount = models.DecimalField(max_digits=9, decimal_places=2)

    stripe_payment_intent = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )

    stripe_client_secret = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="payment_amount_non_negative",
            ),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.reservation.user.username} ({self.status})"

    @property
    def is_successful(self):
        return self.status == self.STATUS_COMPLETED