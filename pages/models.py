from django.db import models
from django.utils import timezone


class SupportMessage(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Full name"
    )

    email = models.EmailField(
        verbose_name="Email address"
    )

    message = models.TextField(
        verbose_name="User message"
    )

    response = models.TextField(
        blank=True,
        null=True,
        verbose_name="Support response",
        help_text="Optional reply written by support staff."
    )

    is_support = models.BooleanField(
        default=False,
        verbose_name="Is support reply",
        help_text="Mark as true if this message was sent by support."
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Created at"
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Support message"
        verbose_name_plural = "Support messages"

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.created_at:%Y-%m-%d %H:%M}"



