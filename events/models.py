from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models
from django.utils import timezone


# ====================================
# 🎟️ MODEL: Event
# ====================================

hex_color_validator = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
    message="Culoarea trebuie să fie un cod hex valid (ex: #4f46e5).",
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

    # Personalizare UI
    theme_color = models.CharField(
        max_length=20,
        default="#4f46e5",
        validators=[hex_color_validator],
        help_text="Culoare temă pentru eveniment (hex, ex: #4f46e5).",
    )
    banner_text = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Text scurt afișat pe banner."
    )
    promo_message = models.TextField(
        blank=True,
        null=True,
        help_text="Mesaj promoțional pentru pagină."
    )

    class Meta:
        ordering = ["start_date"]
        verbose_name = "Eveniment"
        verbose_name_plural = "Evenimente"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),  # Aici am schimbat!
                name="event_end_after_start",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Data de final nu poate fi înaintea datei de început.")

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


# ====================================
# 🎫 MODEL: TicketType
# ====================================

class TicketType(models.Model):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="ticket_types"
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
        verbose_name = "Tip bilet"
        verbose_name_plural = "Tipuri de bilete"
        ordering = ["event", "price"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_quantity__gt=0),  # Modificat aici
                name="ticket_total_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(available_quantity__gte=0),  # Modificat aici
                name="ticket_available_quantity_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(available_quantity__lte=models.F("total_quantity")),  # Modificat aici
                name="ticket_available_not_exceed_total",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.event.title}"

    def clean(self):
        if self.available_quantity > self.total_quantity:
            raise ValidationError(
                "Numărul de bilete disponibile nu poate depăși cantitatea totală."
            )

    def has_stock(self, quantity: int) -> bool:
        return quantity > 0 and self.available_quantity >= quantity

    def reserve(self, quantity: int):
        if quantity <= 0:
            raise ValueError("Cantitatea trebuie să fie mai mare decât 0.")
        if quantity > self.available_quantity:
            raise ValidationError("Nu sunt suficiente bilete disponibile.")
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
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Rezervare"
        verbose_name_plural = "Rezervări"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),  # Modificat aici
                name="reservation_quantity_positive",
            ),
        ]

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
            raise ValidationError("Cantitatea trebuie să fie cel puțin 1.")


# ====================================
# 💳 MODEL: Payment
# ====================================

class Payment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "În așteptare"),
        (STATUS_COMPLETED, "Finalizată"),
        (STATUS_FAILED, "Eșuată"),
    ]

    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="payment"
    )
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    stripe_payment_intent = models.CharField(
        max_length=255, blank=True, null=True, db_index=True
    )
    stripe_client_secret = models.CharField(
        max_length=255, blank=True, null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plată"
        verbose_name_plural = "Plăți"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),  # AICI era "greșeala" de vocabular
                name="payment_amount_non_negative",
            ),
        ]

    def __str__(self):
        return f"Plată {self.id} - {self.reservation.user.username} ({self.status})"

    @property
    def is_successful(self):
        return self.status == self.STATUS_COMPLETED