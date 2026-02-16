from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    is_participant = models.BooleanField(default=True)
    is_organizer = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Utilizator"
        verbose_name_plural = "Utilizatori"
        ordering = ["username"]

    def __str__(self):
        return self.username
