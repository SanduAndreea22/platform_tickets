from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import qrcode
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=[('buyer', 'Cumpărător de bilete'), ('organizer', 'Organizator de evenimente')])

    def __str__(self):
        return f"{self.user.username} - {self.role}"

# models.py
from django.db import models

class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    location = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    tickets_available = models.IntegerField(default=0)
    tickets_sold = models.IntegerField(default=0)  # Câmpul care va salva numărul de bilete vândute
    image = models.ImageField(upload_to='events/', null=True, blank=True)
    theme = models.CharField(max_length=255, blank=True, null=True)
    decorations = models.TextField(blank=True, null=True)
    playlist = models.FileField(upload_to='playlists/', null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Verifică dacă numărul de bilete vândute depășește numărul de bilete disponibile
        if self.tickets_sold > self.tickets_available:
            raise ValidationError("Numărul de bilete vândute nu poate depăși numărul de bilete disponibile.")
        super().save(*args, **kwargs)

    def available_tickets(self):
        """ Returnează numărul de bilete rămase disponibile. """
        return self.tickets_available - self.tickets_sold

    def sell_ticket(self, number_of_tickets=1):
        """ Vinde bilete și actualizează numărul de bilete vândute. """
        if self.available_tickets() >= number_of_tickets:
            self.tickets_sold += number_of_tickets
            self.save()
            return True
        return False


class Ticket(models.Model):
    TICKET_TYPES = [
        ('standard', 'Standard'),
        ('vip', 'VIP'),
        ('early_bird', 'Early Bird'),
        ('student', 'Student'),
    ]

    PAYMENT_STATUSES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tickets')
    ticket_type = models.CharField(max_length=20, choices=TICKET_TYPES)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Prețul total fără discount
    discount = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Discount în procente
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUSES, default='pending')
    payment_method = models.CharField(max_length=100, null=True, blank=True)
    purchased_at = models.DateTimeField(auto_now_add=True)  # Data achiziției
    qr_code = models.ImageField(upload_to='ticket_qrs/', null=True,
                                blank=True)  # Câmp pentru stocarea codului QR generat

    def apply_discount(self):
        """Aplică discountul la prețul biletului."""
        if self.discount:
            return self.price - (self.price * (self.discount / 100))
        return self.price

    def generate_qr_code(self):
        """Generează un cod QR pentru biletul achiziționat."""
        qr = qrcode.make(f"Ticket for {self.event.name} - {self.id}")
        qr_image = BytesIO()
        qr.save(qr_image, format='PNG')
        qr_image.seek(0)

        # Salvează imaginea QR în modelul Ticket
        self.qr_code.save(f"ticket_{self.id}.png",
                          InMemoryUploadedFile(qr_image, None, f"ticket_{self.id}.png", 'image/png',
                                               qr_image.getbuffer().nbytes, None))
        self.save()  # Salvează imaginea QR generată

    def __str__(self):
        return f"{self.user.username} - {self.ticket_type} - {self.event.name}"

    class Meta:
        verbose_name = _('Bilet')
        verbose_name_plural = _('Bilete')



from django.db import models
from django.contrib.auth.models import User
from .models import Event

class Review(models.Model):
    RATING_CHOICES = [
        (1, '★☆☆☆☆'),
        (2, '★★☆☆☆'),
        (3, '★★★☆☆'),
        (4, '★★★★☆'),
        (5, '★★★★★'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=RATING_CHOICES)  # Rating-ul cu stele
    comment = models.TextField(blank=True, null=True)  # Comentariul utilizatorului
    created_at = models.DateTimeField(auto_now_add=True)  # Data creării recenziei

    def __str__(self):
        return f"Recenzie pentru {self.event.name} de {self.user.username}"

    class Meta:
        verbose_name = 'Recenzie'
        verbose_name_plural = 'Recenzii'
        ordering = ['-created_at']  # Ordinea descrescătoare a recenziilor

